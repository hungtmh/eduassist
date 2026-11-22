"""API cho web công khai: không cần đăng nhập, chỉ dữ liệu được phép công khai.

Đọc: có Cache-Control để CDN / trình duyệt giữ 5 phút. Ghi (form tư vấn) và chat: giới hạn theo IP,
form có trường bẫy (honeypot) chặn bot điền tự động.
"""

from collections.abc import AsyncIterator, Callable
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from eduassist.api.fastjson import FastJSONRoute
from eduassist.api.platform import db
from eduassist.api.ratelimit import RateLimiter, client_ip
from eduassist.api.sse import sse_response
from eduassist.cache import cached_json
from eduassist.config import get_settings
from eduassist.services import public

router = APIRouter(prefix="/public", tags=["công khai"], route_class=FastJSONRoute)
CACHE = "public, max-age=60, s-maxage=300"


@lru_cache
def get_public_limiters() -> dict[str, RateLimiter]:
    s = get_settings()
    return {
        "lead": RateLimiter(s.public_lead_per_minute, "public_lead"),
        "chat": RateLimiter(s.public_chat_per_minute, "public_chat"),
        "chat_all": RateLimiter(s.public_chat_global_per_minute, "public_chat_all"),
    }


@lru_cache
def get_public_chat() -> Callable[[list[dict]], AsyncIterator[dict]]:
    from eduassist.public_chat import stream_public

    return stream_public


# Trang công khai: ai cũng xem như nhau, đổi ít -> cache chung mọi tiến trình (Redis) 60 giây, đọc từ bản sao đọc nếu
# có. Lượt khách đông (quảng cáo, mùa tuyển sinh) gần như không chạm database: trúng cache thì không mượn kết nối.
PUBLIC_TTL = 60


def _public(response: Response, key: str, compute):
    from eduassist.db import read_pool

    def load():
        with read_pool().connection() as conn:
            return compute(conn)

    response.headers["Cache-Control"] = CACHE
    return cached_json(f"public:{key}", PUBLIC_TTL, load)


@router.get("/courses")
def courses(
    response: Response,
    danh_muc: str | None = Query(None, max_length=60),
    trinh_do: str | None = Query(None, max_length=30),
):
    return _public(response, f"courses:{danh_muc}:{trinh_do}", lambda c: public.list_courses(c, danh_muc, trinh_do))


@router.get("/courses/{slug}")
def course(slug: str, response: Response):
    if len(slug) > 80:  # khoá cache không phình theo đường dẫn rác
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy khoá học.")
    return _public(response, f"course:{slug}", lambda c: public.course_detail(c, slug))


@router.get("/schedule")
def schedule(response: Response):
    return _public(response, "schedule", public.schedule)


@router.get("/center")
def center(response: Response):
    return _public(response, "center", public.center)


@router.get("/policies")
def policies(response: Response):
    response.headers["Cache-Control"] = CACHE
    return public.policies()


@router.get("/policies/{slug}")
def policy(slug: str, response: Response):
    response.headers["Cache-Control"] = CACHE
    return public.policy(slug)


class LeadIn(BaseModel):
    ho_ten: str = Field(min_length=2, max_length=80)
    so_dien_thoai: str = Field(min_length=9, max_length=20)
    email: str | None = Field(default=None, max_length=254)
    khoa_slug: str | None = Field(default=None, max_length=80)
    nhu_cau: str | None = Field(default=None, max_length=1000)
    dong_y: bool = False
    trang: str | None = Field(default=None, max_length=200)
    website: str | None = Field(default=None, max_length=200)  # bẫy bot: người thật không thấy ô này


@router.post("/leads", status_code=201)
def submit_lead(
    body: LeadIn, request: Request, conn=Depends(db, scope="function"), limiters: dict = Depends(get_public_limiters)
):
    limiters["lead"].check(f"lead:{client_ip(request)}")
    if body.website:  # bot điền cả ô ẩn: trả "thành công" để bot không thử cách khác, nhưng không lưu gì
        return {"ok": True}
    public.submit_lead(conn, body.model_dump())
    return {"ok": True}


class ChatMessage(BaseModel):
    role: str = Field(pattern=r"^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class PublicChatIn(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)


@router.post("/chat")
async def chat(
    body: PublicChatIn,
    request: Request,
    limiters: dict = Depends(get_public_limiters),
    stream: Callable = Depends(get_public_chat),
):
    if not get_settings().public_chat_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trợ lý tư vấn đang tắt.")
    await run_in_threadpool(limiters["chat"].check, f"chat:{client_ip(request)}")
    await run_in_threadpool(limiters["chat_all"].check, "chat:all")
    from eduassist.public_chat import clean_history

    try:
        messages = clean_history([m.model_dump() for m in body.messages])
    except ValueError as e:
        raise HTTPException(422, str(e)) from e

    return sse_response(stream(messages))
