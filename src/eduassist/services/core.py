"""Actor, phân quyền, lỗi nghiệp vụ, đồng hồ nghiệp vụ, audit log và outbox."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

Role = Literal["student", "consultant", "academic", "accountant", "teacher", "manager"]
ROLES: tuple[Role, ...] = ("student", "consultant", "academic", "accountant", "teacher", "manager")
ROLE_LABEL = {
    "student": "Học viên",
    "consultant": "Tư vấn viên",
    "academic": "Giáo vụ",
    "accountant": "Kế toán",
    "teacher": "Giảng viên",
    "manager": "Quản lý",
}

# ---------------------------------------------------------------- phân quyền
_STAFF_COMMON = {"student.read", "class.read", "chat.data", "task.read"}
PERMISSIONS: dict[str, set[str]] = {
    "student": {"portal"},
    "consultant": _STAFF_COMMON
    | {"lead.read", "lead.write", "student.write", "enroll.create", "invoice.read", "voucher.issue", "email.send"},
    "academic": _STAFF_COMMON
    | {
        "class.write",
        "attendance.write",
        "grade.write",
        "enroll.create",
        "enroll.change",
        "request.handle",
        "email.send",
        "invoice.read",
        "lead.read",
    },
    "accountant": _STAFF_COMMON
    | {
        "invoice.read",
        "payment.record",
        "refund.handle",
        "enroll.suspend",
        "voucher.issue",
        "email.send",
        "request.handle",
    },
    "teacher": {"class.read_own", "attendance.write", "grade.write"},
}
PERMISSIONS["manager"] = set().union(*PERMISSIONS.values()) - {"portal"} | {
    "autonomy.write",
    "audit.read",
    "report.read",
    "agent.run",
    "user.admin",
    "proposal.decide_any",
    "data.delete",
}

# Mức "Cấm" của đề xuất (mục 6.5): agent KHÔNG BAO GIỜ được làm, kể cả khi người dùng yêu cầu qua chat
AGENT_FORBIDDEN = {
    "payment.record": "ghi nhận đã thu tiền",
    "grade.write": "sửa điểm",
    "user.admin": "đổi quyền người dùng",
    "data.delete": "xoá dữ liệu",
    "autonomy.write": "thay đổi mức tự chủ của agent",
}

VOUCHER_MAX_PERCENT = {"consultant": 15, "accountant": 15, "manager": 30}


@dataclass(frozen=True)
class Actor:
    """Ai đang thao tác. Agent có vai trò như một nhân viên số và bị giới hạn thêm bởi AGENT_FORBIDDEN."""

    id: str  # username, hoặc "agent:<tên>"
    role: Role
    is_agent: bool = False
    hoc_vien_id: int | None = None
    giang_vien_id: int | None = None
    proposal_id: int | None = None  # đang thực thi một đề xuất đã duyệt
    approved_by: str | None = None

    @property
    def is_staff(self) -> bool:
        return self.role != "student"

    def executing(self, proposal_id: int, approved_by: str) -> "Actor":
        return replace(self, proposal_id=proposal_id, approved_by=approved_by)


def agent_actor(name: str, role: Role) -> Actor:
    return Actor(id=f"agent:{name}", role=role, is_agent=True)


SYSTEM = Actor(id="system", role="manager")  # tác vụ nền thuần dữ liệu (đánh dấu quá hạn...), không phải agent


# ---------------------------------------------------------------- lỗi
class ServiceError(Exception):
    status = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(ServiceError):
    status = 404


class Forbidden(ServiceError):
    status = 403


class RuleViolation(ServiceError):
    """Vi phạm luật nghiệp vụ. Thông điệp nói rõ luật nào để người dùng (hoặc LLM) biết cách sửa."""

    status = 422


class Conflict(ServiceError):
    status = 409


def has_perm(actor: Actor, perm: str) -> bool:
    if actor.is_agent and perm in AGENT_FORBIDDEN:
        return False
    return perm in PERMISSIONS.get(actor.role, set())


def require(actor: Actor, perm: str) -> None:
    if actor.is_agent and perm in AGENT_FORBIDDEN:
        raise Forbidden(f"Agent không bao giờ được {AGENT_FORBIDDEN[perm]}. Thao tác này chỉ con người thực hiện.")
    if perm not in PERMISSIONS.get(actor.role, set()):
        raise Forbidden(f"Vai trò {ROLE_LABEL.get(actor.role, actor.role)} không có quyền thực hiện thao tác này.")


def check_transition(kind: str, transitions: dict[str, set[str]], current: str, target: str) -> None:
    if target not in transitions.get(current, set()):
        raise RuleViolation(f"Không thể chuyển {kind} từ '{current}' sang '{target}'.")


# ---------------------------------------------------------------- đồng hồ nghiệp vụ
# Mọi luật dùng ngày nghiệp vụ thay vì date.today(): chạy mô phỏng 30 ngày chỉ cần đặt lại đồng hồ.
_today: ContextVar[date | None] = ContextVar("eduassist_today", default=None)


def today() -> date:
    return _today.get() or date.today()


def now() -> datetime:
    """Thời điểm nghiệp vụ (có múi giờ). Khi mô phỏng: ngày mô phỏng + giờ hiện tại."""
    real = datetime.now().astimezone()
    d = _today.get()
    return real if d is None else real.replace(year=d.year, month=d.month, day=d.day)


@contextmanager
def business_date(d: date) -> Iterator[None]:
    token = _today.set(d)
    try:
        yield
    finally:
        _today.reset(token)


# ---------------------------------------------------------------- audit & outbox
def _json_default(v: Any):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return str(v)


def to_json(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, default=_json_default)


def audit(
    conn,
    actor: Actor,
    action: str,
    obj: str,
    obj_id: Any,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
) -> None:
    """Ai (người hay agent nào) · làm gì · trên đối tượng nào · giá trị trước/sau · vì sao · ai duyệt."""
    conn.execute(
        """INSERT INTO audit_log (actor, actor_role, hanh_dong, doi_tuong, doi_tuong_id, truoc, sau, ly_do,
                                  de_xuat_id, duyet_boi)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            actor.id,
            actor.role,
            action,
            obj,
            None if obj_id is None else str(obj_id),
            None if before is None else to_json(before),
            None if after is None else to_json(after),
            reason,
            actor.proposal_id,
            actor.approved_by,
        ),
    )


def emit_event(conn, kind: str, **payload) -> None:
    """Ghi sự kiện vào outbox TRONG CÙNG transaction với thay đổi dữ liệu -> không mất sự kiện, không có sự kiện ma."""
    conn.execute("INSERT INTO outbox_su_kien (loai, payload) VALUES (%s, %s)", (kind, to_json(payload)))


def one(conn, sql: str, params: Any = None, what: str = "dữ liệu") -> dict:
    row = conn.execute(sql, params).fetchone()
    if row is None:
        raise NotFound(f"Không tìm thấy {what}.")
    return row
