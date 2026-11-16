"""EduAssist API.

    uv run uvicorn eduassist.api.main:app --reload

Luồng chat: POST /chat (SSE) -> nếu nhận event "interrupt" thì POST /chat/resume với quyết định duyệt.
Chat chạy async (eduassist.chat.astream_turn): chờ LLM không giữ luồng nào, một tiến trình giữ được hàng trăm cuộc chat.
"""

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import lru_cache

import anyio.to_thread
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from psycopg.errors import LockNotAvailable, QueryCanceled
from psycopg_pool import PoolTimeout

from eduassist.agents.context import UserContext
from eduassist.api import metrics as metrics_mod
from eduassist.api import overload
from eduassist.api.account_routes import router as account_router
from eduassist.api.auth import AuthUser, authenticate, create_token, current_user, current_user_any
from eduassist.api.overload import AdmissionControl
from eduassist.api.platform import router as platform_router
from eduassist.api.public_routes import router as public_router
from eduassist.api.ratelimit import RateLimiter, client_ip, get_login_limiter
from eduassist.api.schemas import (
    ChatRequest,
    FeedbackRequest,
    FeedbackResponse,
    LoginRequest,
    LoginResponse,
    ResumeRequest,
    UserInfo,
)
from eduassist.api.sse import sse_response
from eduassist.config import get_settings
from eduassist.observability import init_sentry
from eduassist.services.core import ServiceError


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        payload.update(getattr(record, "extra_fields", {}))
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)
log = logging.getLogger("eduassist.api")


# ---------- Dependencies (tests thay bằng bản giả - không cần LLM hay DB) ----------
@dataclass
class Backend:
    stream_turn: Callable[..., AsyncIterator[dict]]
    pending_actions: Callable[[UserContext], list[dict]]
    thread_history: Callable[[UserContext], list[dict]]
    record_feedback: Callable[..., dict]
    authenticate: Callable[[str, str], AuthUser | None]
    healthcheck: Callable[[], bool]


def _db_ok() -> bool:
    from eduassist.db import app_pool

    with app_pool().connection() as conn:
        return conn.execute("SELECT 1 AS ok").fetchone()["ok"] == 1


@lru_cache
def get_backend() -> Backend:
    from eduassist import chat, learning

    return Backend(
        stream_turn=chat.astream_turn,
        pending_actions=chat.pending_actions,
        thread_history=chat.thread_history,
        record_feedback=learning.record_feedback,
        authenticate=authenticate,
        healthcheck=_db_ok,
    )


@lru_cache
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_settings().rate_limit_per_minute, "chat")


def user_context(user: AuthUser, conversation_id: str, run_id: str | None = None) -> UserContext:
    # thread_id LUÔN gắn username -> không ai đọc/ghi được hội thoại của người khác dù đoán được conversation_id
    return UserContext(
        user_id=user.username,
        role=user.role,
        display_name=user.display_name,
        hoc_vien_id=user.hoc_vien_id,
        run_id=run_id or str(uuid.uuid4()),
        thread_id=f"{user.username}:{conversation_id}",
        giang_vien_id=user.giang_vien_id,
    )


init_sentry("api")

# ---------- App ----------
_prod = get_settings().is_production


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    import asyncio

    from eduassist.agents.persistence import close_async

    s = get_settings()
    # Số luồng chạy hàm def thường (endpoint, dependency). Phải lớn hơn ngăn request thường của AdmissionControl.
    anyio.to_thread.current_default_thread_limiter().total_tokens = s.thread_pool_size
    # Tool lá của chat async (SQL, RAG) chạy trong executor mặc định của event loop; mặc định chỉ min(32, CPU+4) luồng
    asyncio.get_running_loop().set_default_executor(
        ThreadPoolExecutor(max_workers=s.chat_tool_threads, thread_name_prefix="chat-tool")
    )
    yield
    await close_async()


app = FastAPI(
    lifespan=_lifespan,
    title="EduAssist Platform API",
    version="1.0.0",
    description="Nền tảng quản lý trung tâm đào tạo tích hợp hệ đa tác tử AI: REST nghiệp vụ + chat SSE",
    # Production không công khai tài liệu API
    docs_url=None if _prod else "/docs",
    redoc_url=None if _prod else "/redoc",
    openapi_url=None if _prod else "/openapi.json",
)
# Thêm TRƯỚC CORS để CORS bọc ngoài: trình duyệt vẫn đọc được thông báo 503 "quá tải"
_s = get_settings()
app.add_middleware(
    AdmissionControl,
    max_concurrent=_s.max_concurrent_requests,
    max_queue=_s.max_queued_requests,
    queue_timeout=_s.queue_timeout_seconds,
    max_streams=_s.max_concurrent_streams,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Must-Change-Password"],
)
app.include_router(platform_router)
app.include_router(account_router)
app.include_router(public_router)


class AccessLog:
    """Ghi mỗi request một dòng log. ASGI thuần thay cho @app.middleware("http") (BaseHTTPMiddleware):
    rẻ CPU hơn và không chặn luồng SSE. Bọc ngoài cùng để ghi cả 503 do AdmissionControl trả."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            route = scope.get("route")
            # Nhãn theo mẫu đường dẫn (/students/{student_id}), không theo đường dẫn thật: số nhãn không phình
            metrics_mod.observe(
                getattr(route, "path", "khac"), scope["method"], status_code, time.perf_counter() - start
            )
            log.info(
                "request",
                extra={
                    "extra_fields": {
                        "method": scope["method"],
                        "path": scope["path"],
                        "status": status_code,
                        "ms": round((time.perf_counter() - start) * 1000),
                    }
                },
            )


app.add_middleware(AccessLog)


@app.exception_handler(ServiceError)
async def service_error(request: Request, exc: ServiceError):
    # Lỗi nghiệp vụ (vi phạm luật, thiếu quyền...) -> thông điệp tiếng Việt hiện thẳng cho người dùng
    return JSONResponse({"detail": exc.message}, status_code=exc.status)


@app.exception_handler(PoolTimeout)
async def pool_exhausted(request: Request, exc: PoolTimeout):
    # Hết kết nối database trong db_pool_timeout giây: từ chối nhanh để hệ thống không dồn hàng nghìn request chờ.
    # Retry-After cho trình duyệt / load balancer biết khi nào thử lại.
    log.warning("hết kết nối database tại %s: %s", request.url.path, exc)
    return JSONResponse(
        {"detail": "Hệ thống đang quá tải, bạn thử lại sau vài giây."}, status_code=503, headers={"Retry-After": "2"}
    )


@app.exception_handler(QueryCanceled)
async def query_timeout(request: Request, exc: QueryCanceled):
    # Câu SQL vượt db_statement_timeout_ms - Postgres đã huỷ, kết nối đã được trả lại pool
    log.warning("truy vấn quá lâu tại %s: %s", request.url.path, exc)
    return JSONResponse({"detail": "Thao tác mất quá nhiều thời gian, bạn thử lại sau."}, status_code=503)


@app.exception_handler(LockNotAvailable)
async def lock_wait_timeout(request: Request, exc: LockNotAvailable):
    # Chờ khoá quá db_lock_timeout_ms (dữ liệu đang bị thao tác khác giữ): báo bận ngay, không giữ chỗ chạy
    log.warning("chờ khoá quá lâu tại %s: %s", request.url.path, exc)
    return JSONResponse(
        {"detail": "Dữ liệu này đang được cập nhật, bạn thử lại sau vài giây."},
        status_code=503,
        headers={"Retry-After": "2"},
    )


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error at %s", request.url.path)
    return JSONResponse({"detail": "Lỗi hệ thống, vui lòng thử lại sau."}, status_code=500)


@app.get("/health/live")
async def health_live():
    """Tiến trình còn sống. async + không đụng database: vẫn trả lời khi thread pool hoặc DB đang quá tải,
    nên load balancer / Docker không giết nhầm một bản API chỉ đang bận."""
    return {"status": "ok"}


def _admission_stats() -> dict:
    return overload.current.stats() if overload.current else {}


@app.get("/metrics", include_in_schema=False)
def metrics(request: Request):
    """Số liệu vận hành dạng Prometheus. Chỉ cho mạng nội bộ: Caddy không chuyển /api/metrics ra ngoài, và nếu đặt
    METRICS_TOKEN thì phải gửi kèm header Authorization: Bearer <token>."""
    from eduassist.api.metrics import render

    token = get_settings().metrics_token.get_secret_value()
    if token and request.headers.get("authorization") != f"Bearer {token}":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Cần METRICS_TOKEN")
    return PlainTextResponse(render(_admission_stats()), media_type="text/plain; version=0.0.4")


@app.get("/health")
def health(backend: Backend = Depends(get_backend)):
    """Sẵn sàng nhận việc: kiểm tra được database."""
    try:
        ok = backend.healthcheck()
    except Exception:
        ok = False
    if not ok:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable")
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    request: Request,
    backend: Backend = Depends(get_backend),
    limiter: RateLimiter = Depends(get_login_limiter),
):
    limiter.check(f"login:{client_ip(request)}")
    user = backend.authenticate(body.username, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sai tên đăng nhập hoặc mật khẩu")
    return LoginResponse(
        access_token=create_token(user),
        user=UserInfo(username=user.username, role=user.role, display_name=user.display_name),
    )


@app.get("/me", response_model=UserInfo)
def me(user: AuthUser = Depends(current_user_any)):
    return UserInfo(username=user.username, role=user.role, display_name=user.display_name)


@app.post("/chat")
async def chat(
    body: ChatRequest,
    user: AuthUser = Depends(current_user),
    backend: Backend = Depends(get_backend),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    # Bước đồng bộ ngắn (Redis, đọc trạng thái hội thoại) chạy trong thread pool; phần chờ LLM thì không giữ luồng
    await run_in_threadpool(limiter.check, user.username)
    conversation_id = body.conversation_id or uuid.uuid4().hex[:12]
    ctx = user_context(user, conversation_id)
    if await run_in_threadpool(backend.pending_actions, ctx):
        raise HTTPException(status.HTTP_409_CONFLICT, "Còn thao tác đang chờ duyệt. Hãy duyệt hoặc từ chối trước.")
    events = backend.stream_turn(ctx, message=body.message)
    return sse_response(events, {"conversation_id": conversation_id, "run_id": ctx.run_id})


@app.post("/chat/resume")
async def resume(
    body: ResumeRequest,
    user: AuthUser = Depends(current_user),
    backend: Backend = Depends(get_backend),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    await run_in_threadpool(limiter.check, user.username)
    ctx = user_context(user, body.conversation_id, body.run_id)
    pending = await run_in_threadpool(backend.pending_actions, ctx)
    if not pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "Không có thao tác nào đang chờ duyệt.")
    if len(body.decisions) != len(pending):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Cần đúng {len(pending)} quyết định, nhận {len(body.decisions)}."
        )
    decisions = [d.model_dump(exclude_none=True) for d in body.decisions]
    events = backend.stream_turn(ctx, resume=decisions)
    return sse_response(events, {"conversation_id": body.conversation_id, "run_id": ctx.run_id})


@app.get("/conversations/{conversation_id}/pending")
def pending(conversation_id: str, user: AuthUser = Depends(current_user), backend: Backend = Depends(get_backend)):
    return {"actions": backend.pending_actions(user_context(user, _check_id(conversation_id)))}


@app.get("/conversations/{conversation_id}/messages")
def messages(conversation_id: str, user: AuthUser = Depends(current_user), backend: Backend = Depends(get_backend)):
    return {"messages": backend.thread_history(user_context(user, _check_id(conversation_id)))}


@app.post("/feedback", response_model=FeedbackResponse)
def feedback(body: FeedbackRequest, user: AuthUser = Depends(current_user), backend: Backend = Depends(get_backend)):
    ctx = user_context(user, body.conversation_id, body.run_id)
    return backend.record_feedback(ctx, body.run_id, body.score, body.comment)


def _check_id(conversation_id: str) -> str:
    if (
        not conversation_id
        or len(conversation_id) > 64
        or not conversation_id.replace("-", "").replace("_", "").isalnum()
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "conversation_id không hợp lệ")
    return conversation_id
