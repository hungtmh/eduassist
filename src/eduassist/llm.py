"""Tạo chat model + middleware chịu lỗi dùng chung cho mọi agent.

Đổi nhà cung cấp LLM chỉ cần sửa file này (và .env), các agent không phụ thuộc Groq.
"""

from functools import lru_cache

from langchain.agents.middleware import ModelFallbackMiddleware, ModelRetryMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_groq import ChatGroq

from eduassist.config import get_settings


@lru_cache
def chat_model(model: str | None = None, temperature: float = 0.0) -> BaseChatModel:
    s = get_settings()
    return ChatGroq(
        model=model or s.llm_model,
        temperature=temperature,
        api_key=s.groq_api_key,
        max_retries=0,  # retry do ModelRetryMiddleware lo (có backoff, có log)
        timeout=60,
    )


def resilience_middleware() -> list:
    """Retry khi lỗi tạm thời (429, timeout...) rồi mới chuyển sang model dự phòng."""
    return [
        ModelFallbackMiddleware(chat_model(get_settings().llm_fallback_model)),
        ModelRetryMiddleware(max_retries=2, initial_delay=2.0, on_failure="error"),
    ]
