"""EduAssist API.

    uv run uvicorn eduassist.api.main:app --reload

Luồng chat: POST /chat (SSE) -> nếu nhận event "interrupt" thì POST /chat/resume với quyết định duyệt.
"""

import json
import logging
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from eduassist.agents.context import UserContext
from eduassist.api.auth import AuthUser, authenticate, create_token, current_user
from eduassist.api.platform import router as platform_router
from eduassist.api.ratelimit import RateLimiter
from eduassist.api.schemas import (
    ChatRequest,
    FeedbackRequest,
    FeedbackResponse,
    LoginRequest,
    LoginResponse,
    ResumeRequest,
    UserInfo,
)
from eduassist.config import get_settings
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
    stream_turn: Callable[..., Iterator[dict]]
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
        stream_turn=chat.stream_turn,
        pending_actions=chat.pending_actions,
        thread_history=chat.thread_history,
        record_feedback=learning.record_feedback,
        authenticate=authenticate,
        healthcheck=_db_ok,
    )


@lru_cache
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_settings().rate_limit_per_minute)


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


def sse(events: Iterator[dict], meta: dict) -> StreamingResponse:
    def gen():
        yield f"event: meta\ndata: {json.dumps(meta)}\n\n"
        for ev in events:
            yield f"event: {ev['type']}\ndata: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


# ---------- App ----------
app = FastAPI(
    title="EduAssist Platform API",
    version="1.0.0",
    description="Nền tảng quản lý trung tâm đào tạo tích hợp hệ đa tác tử AI: REST nghiệp vụ + chat SSE",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(platform_router)


@app.middleware("http")
async def access_log(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    log.info(
        "request",
        extra={
            "extra_fields": {
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": round((time.perf_counter() - start) * 1000),
            }
        },
    )
    return response


@app.exception_handler(ServiceError)
async def service_error(request: Request, exc: ServiceError):
    # Lỗi nghiệp vụ (vi phạm luật, thiếu quyền...) -> thông điệp tiếng Việt hiện thẳng cho người dùng
    return JSONResponse({"detail": exc.message}, status_code=exc.status)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error at %s", request.url.path)
    return JSONResponse({"detail": "Lỗi hệ thống, vui lòng thử lại sau."}, status_code=500)


@app.get("/health")
def health(backend: Backend = Depends(get_backend)):
    try:
        ok = backend.healthcheck()
    except Exception:
        ok = False
    if not ok:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable")
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, backend: Backend = Depends(get_backend)):
    user = backend.authenticate(body.username, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sai tên đăng nhập hoặc mật khẩu")
    return LoginResponse(
        access_token=create_token(user),
        user=UserInfo(username=user.username, role=user.role, display_name=user.display_name),
    )


@app.get("/me", response_model=UserInfo)
def me(user: AuthUser = Depends(current_user)):
    return UserInfo(username=user.username, role=user.role, display_name=user.display_name)


@app.post("/chat")
def chat(
    body: ChatRequest,
    user: AuthUser = Depends(current_user),
    backend: Backend = Depends(get_backend),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.check(user.username)
    conversation_id = body.conversation_id or uuid.uuid4().hex[:12]
    ctx = user_context(user, conversation_id)
    if backend.pending_actions(ctx):
        raise HTTPException(status.HTTP_409_CONFLICT, "Còn thao tác đang chờ duyệt. Hãy duyệt hoặc từ chối trước.")
    events = backend.stream_turn(ctx, message=body.message)
    return sse(events, {"conversation_id": conversation_id, "run_id": ctx.run_id})


@app.post("/chat/resume")
def resume(
    body: ResumeRequest,
    user: AuthUser = Depends(current_user),
    backend: Backend = Depends(get_backend),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.check(user.username)
    ctx = user_context(user, body.conversation_id, body.run_id)
    pending = backend.pending_actions(ctx)
    if not pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "Không có thao tác nào đang chờ duyệt.")
    if len(body.decisions) != len(pending):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Cần đúng {len(pending)} quyết định, nhận {len(body.decisions)}."
        )
    decisions = [d.model_dump(exclude_none=True) for d in body.decisions]
    events = backend.stream_turn(ctx, resume=decisions)
    return sse(events, {"conversation_id": body.conversation_id, "run_id": ctx.run_id})


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
