"""Tạo chat model + middleware chịu lỗi dùng chung cho mọi agent.

Đổi nhà cung cấp LLM chỉ cần sửa file này (và .env), các agent không phụ thuộc Groq.
"""

from functools import lru_cache

from langchain.agents.middleware import ModelFallbackMiddleware, ModelRetryMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_groq import ChatGroq

from eduassist.config import get_settings


@lru_cache
def chat_model(model: str | None = None, temperature: float = 0.0, background: bool = False) -> BaseChatModel:
    """background=True: agent chạy nền soạn lời văn - thử một lần, chờ ngắn, lỗi thì dùng bản mẫu do code soạn
    (worker đang mở transaction trong lúc chờ, không được treo lâu)."""
    s = get_settings()
    return ChatGroq(
        model=model or s.llm_model,
        temperature=temperature,
        api_key=s.groq_api_key,
        # SDK tự chờ theo header retry-after khi bị 429 (free tier Groq: 8K token/phút);
        # lỗi khác do ModelRetryMiddleware + model dự phòng xử lý. Tổng một câu chat còn bị chặn bởi
        # chat_turn_timeout_seconds (eduassist.chat), nên các lớp thử lại không cộng dồn thành vài phút.
        max_retries=0 if background else 2,
        timeout=s.background_llm_timeout_seconds if background else s.llm_request_timeout_seconds,
    )


def transient_error(exc: Exception) -> bool:
    """Lỗi thử lại có ích: quá hạn mức (429), máy chủ LLM lỗi (5xx), mất mạng / timeout.
    Khoá sai (401), hết quyền (403), yêu cầu sai (400) thì thử lại bao nhiêu cũng vậy -> báo lỗi ngay.
    (Diễn tập khoá API sai: trước khi lọc, mỗi câu chat chờ 15 giây mới báo lỗi.)"""
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status in (408, 409, 429) or status >= 500
    return isinstance(exc, (TimeoutError, ConnectionError)) or type(exc).__name__ in (
        "APIConnectionError",
        "APITimeoutError",
    )


def resilience_middleware() -> list:
    """Retry khi lỗi tạm thời (429, timeout...) rồi mới chuyển sang model dự phòng."""
    return [
        ModelFallbackMiddleware(chat_model(get_settings().llm_fallback_model)),
        ModelRetryMiddleware(max_retries=2, initial_delay=2.0, on_failure="error", retry_on=transient_error),
    ]
