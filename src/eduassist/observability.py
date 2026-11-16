"""Tracing với Langfuse - TUỲ CHỌN. Không cấu hình key thì trả về [] và hệ thống chạy bình thường.

trace_id của Langfuse = run_id của lượt chat (bỏ dấu gạch) -> feedback 👍/👎 gắn đúng vào trace đó.
Lưu ý quyền riêng tư: trace chứa nội dung hội thoại (có thể có email/SĐT học viên). Với dữ liệu thật,
nên TỰ HOST Langfuse để dữ liệu không rời hạ tầng của trung tâm.
"""

import logging
from functools import lru_cache

from eduassist.config import get_settings

log = logging.getLogger("eduassist.observability")


@lru_cache
def _client():
    s = get_settings()
    if not s.langfuse_enabled:
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=s.langfuse_public_key,
            secret_key=s.langfuse_secret_key.get_secret_value(),
            host=s.langfuse_host,
        )
    except Exception:  # thiếu package (group "obs") hoặc cấu hình sai -> tắt tracing, không làm sập app
        log.warning("Langfuse không khởi tạo được - tắt tracing", exc_info=True)
        return None


def trace_id(run_id: str) -> str:
    return run_id.replace("-", "")


def tracing_callbacks(ctx) -> list:
    if _client() is None:
        return []
    from langfuse.langchain import CallbackHandler

    return [
        CallbackHandler(public_key=get_settings().langfuse_public_key, trace_context={"trace_id": trace_id(ctx.run_id)})
    ]


def tracing_metadata(ctx) -> dict:
    """Langfuse đọc các khoá này từ metadata của LangChain để lọc trace theo user / hội thoại / vai trò."""
    return {"langfuse_user_id": ctx.user_id, "langfuse_session_id": ctx.thread_id, "langfuse_tags": [ctx.role]}


def record_feedback(run_id: str, score: int, comment: str | None) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.create_score(
            name="user_feedback", value=score, trace_id=trace_id(run_id), comment=comment, data_type="NUMERIC"
        )
    except Exception:
        log.warning("Không gửi được feedback lên Langfuse", exc_info=True)


def init_sentry(component: str) -> None:
    """Báo lỗi lên Sentry nếu đặt SENTRY_DSN (tuỳ chọn, cần nhóm dependency obs).
    send_default_pii=False: không gửi IP, cookie, header Authorization, nội dung request."""
    s = get_settings()
    if not s.sentry_dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        log.warning("SENTRY_DSN đã đặt nhưng chưa cài sentry-sdk (uv sync --group obs) - bỏ qua")
        return
    sentry_sdk.init(
        dsn=s.sentry_dsn, environment=s.app_env, send_default_pii=False, traces_sample_rate=0.0, server_name=component
    )
