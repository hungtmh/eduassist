"""Ngữ cảnh của người dùng hiện tại, truyền vào mọi agent và tool qua `context=`.

Thông tin này đến từ JWT đã xác thực ở API - KHÔNG BAO GIỜ lấy từ nội dung chat,
nên người dùng không thể "tự nhận" là nhân viên bằng cách gõ vào ô chat.
"""

from contextlib import suppress
from dataclasses import dataclass

from langgraph.config import get_stream_writer

from eduassist.services.core import ROLE_LABEL as _LABELS
from eduassist.services.core import Actor, Role, has_perm

ROLE_LABEL = {k: v.lower() for k, v in _LABELS.items()}


@dataclass(frozen=True)
class UserContext:
    user_id: str
    role: Role
    display_name: str
    hoc_vien_id: int | None = None
    run_id: str = ""
    thread_id: str = ""
    giang_vien_id: int | None = None

    @property
    def is_staff(self) -> bool:
        return self.role != "student"

    @property
    def can_use_data_agents(self) -> bool:
        """Được dùng agent phân tích + vận hành (quyền chat.data trong tầng Service)."""
        return has_perm(Actor(self.user_id, self.role), "chat.data")


def emit(event_type: str, **data) -> None:
    """Gửi sự kiện tiến trình (stream_mode="custom") để UI hiện "đang chạy SQL...", v.v.
    Không có ai đang stream thì bỏ qua."""
    with suppress(RuntimeError, KeyError):  # gọi ngoài ngữ cảnh graph (VD: unit test, script)
        get_stream_writer()({"type": event_type, **data})
