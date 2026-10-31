"""Tracing với Langfuse - TUỲ CHỌN. Không cấu hình key thì trả về [] và hệ thống chạy bình thường."""

import logging
from functools import lru_cache

from eduassist.config import get_settings

log = logging.getLogger("eduassist.observability")


@lru_cache
def _langfuse_ready() -> bool:
    s = get_settings()
    if not s.langfuse_enabled:
        return False
    try:
        from langfuse import Langfuse

        Langfuse(
            public_key=s.langfuse_public_key,
            secret_key=s.langfuse_secret_key.get_secret_value(),
            host=s.langfuse_host,
        )
        return True
    except Exception:  # thiếu package (group "obs") hoặc cấu hình sai -> tắt tracing, không làm sập app
        log.warning("Langfuse không khởi tạo được - tắt tracing", exc_info=True)
        return False


def tracing_callbacks(ctx) -> list:
    if not _langfuse_ready():
        return []
    from langfuse.langchain import CallbackHandler

    return [CallbackHandler()]


def record_feedback(run_id: str, score: int, comment: str | None) -> None:
    if not _langfuse_ready():
        return
    try:
        from langfuse import get_client

        get_client().create_score(name="user_feedback", value=score, trace_id=_trace_id(run_id), comment=comment)
    except Exception:
        log.warning("Không gửi được feedback lên Langfuse", exc_info=True)


def _trace_id(run_id: str) -> str:
    # Langfuse trace id = 32 ký tự hex; run_id của ta là uuid4 -> bỏ dấu gạch
    return run_id.replace("-", "")
