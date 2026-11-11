"""REST API cho nghiệp vụ. Router MỎNG: mở transaction, dựng Actor từ JWT, gọi tầng Service.

Không có luật nghiệp vụ hay kiểm tra quyền nào ở đây - tất cả nằm trong eduassist.services, để giao diện web và
agent đi qua đúng cùng một chỗ. Mỗi request = một transaction: lỗi giữa chừng thì không có gì được ghi.
"""

from collections.abc import Iterator
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from eduassist.api.auth import AuthUser, current_user
from eduassist.services import (
    crm,
    enrollment,
    finance,
    notifications,
    proposals,
    reports,
    students,
    training,
)
from eduassist.services.core import PERMISSIONS, ROLE_LABEL, Actor, NotFound, require

router = APIRouter()


def db() -> Iterator:
    from eduassist.db import app_pool

    with app_pool().connection() as conn, conn.transaction():
        yield conn


def actor(user: AuthUser = Depends(current_user)) -> Actor:
    return user.actor()


# ---------------------------------------------------------------- tài khoản
@router.get("/me/profile", tags=["tài khoản"])
def profile(user: AuthUser = Depends(current_user)):
    return {
        "username": user.username,
        "role": user.role,
        "role_label": ROLE_LABEL[user.role],
        "display_name": user.display_name,
        "hoc_vien_id": user.hoc_vien_id,
        "giang_vien_id": user.giang_vien_id,
        "permissions": sorted(PERMISSIONS[user.role]),
    }


@router.get("/notifications", tags=["thông báo"])
def list_notifications(conn=Depends(db), me: Actor = Depends(actor)):
    return notifications.list_notifications(conn, me)


class IdsBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)


@router.post("/notifications/read", tags=["thông báo"])
def read_notifications(body: IdsBody, conn=Depends(db), me: Actor = Depends(actor)):
    notifications.mark_read(conn, me, body.ids)
    return {"ok": True}


@router.get("/dashboard", tags=["báo cáo"])
def dashboard(conn=Depends(db), me: Actor = Depends(actor)):
    return reports.dashboard(conn, me)


# ---------------------------------------------------------------- tuyển sinh
class LeadIn(BaseModel):
    ho_ten: str = Field(min_length=2, max_length=100)
    so_dien_thoai: str = Field(min_length=9, max_length=20)
    email: str | None = Field(default=None, max_length=120)
    nguon: Literal["facebook", "zalo", "gioi_thieu", "website", "tiktok", "walk_in"]
    nhu_cau: str = Field(default="", max_length=1000)
    khoa_quan_tam_id: int | None = None
    phu_trach: str | None = None


class TransitionIn(BaseModel):
    trang_thai: Literal["moi", "da_lien_he", "hen_hoc_thu", "da_ghi_danh", "khong_tiep_tuc"]
    ghi_chu: str = Field(default="", max_length=500)


class NoteIn(BaseModel):
    ghi_chu: str = Field(min_length=1, max_length=1000)


class AppointmentIn(BaseModel):
    loai: Literal["tu_van", "hoc_thu"]
    thoi_gian: datetime
    lop_hoc_id: int | None = None


class ConvertIn(BaseModel):
    nam_sinh: int = Field(ge=1940, le=2022)
    thanh_pho: str = Field(min_length=2, max_length=60)


@router.get("/leads", tags=["tuyển sinh"])
def list_leads(
    trang_thai: str | None = None,
    phu_trach: str | None = None,
    q: str | None = None,
    conn=Depends(db),
    me: Actor = Depends(actor),
):
    return crm.list_leads(conn, me, trang_thai, phu_trach, q)


@router.post("/leads", tags=["tuyển sinh"], status_code=201)
def create_lead(body: LeadIn, conn=Depends(db), me: Actor = Depends(actor)):
    return crm.create_lead(conn, me, body.model_dump())


@router.get("/leads/{lead_id}", tags=["tuyển sinh"])
def get_lead(lead_id: int, conn=Depends(db), me: Actor = Depends(actor)):
    return crm.get_lead(conn, me, lead_id)


@router.post("/leads/{lead_id}/transition", tags=["tuyển sinh"])
def transition_lead(lead_id: int, body: TransitionIn, conn=Depends(db), me: Actor = Depends(actor)):
    return crm.transition(conn, me, lead_id, body.trang_thai, body.ghi_chu)


@router.post("/leads/{lead_id}/contact", tags=["tuyển sinh"])
def contact_lead(lead_id: int, body: NoteIn, conn=Depends(db), me: Actor = Depends(actor)):
    return crm.log_contact(conn, me, lead_id, body.ghi_chu)


@router.post("/leads/{lead_id}/appointments", tags=["tuyển sinh"])
def book(lead_id: int, body: AppointmentIn, conn=Depends(db), me: Actor = Depends(actor)):
    return crm.book_appointment(conn, me, lead_id, body.loai, body.thoi_gian, body.lop_hoc_id)


@router.post("/leads/{lead_id}/convert", tags=["tuyển sinh"])
def convert(lead_id: int, body: ConvertIn, conn=Depends(db), me: Actor = Depends(actor)):
    return crm.convert_to_student(conn, me, lead_id, body.nam_sinh, body.thanh_pho)


@router.get("/tasks", tags=["tuyển sinh"])
def list_tasks(mine: bool = True, trang_thai: str = "mo", conn=Depends(db), me: Actor = Depends(actor)):
    return crm.list_tasks(conn, me, mine, trang_thai)


@router.post("/tasks/{task_id}/done", tags=["tuyển sinh"])
def task_done(task_id: int, conn=Depends(db), me: Actor = Depends(actor)):
    crm.complete_task(conn, me, task_id)
    return {"ok": True}


# ---------------------------------------------------------------- đào tạo
class ClassIn(BaseModel):
    khoa_hoc_id: int
    ngay_khai_giang: date
    ca_hoc: Literal["sang", "chieu", "toi"]
    lich_hoc: str = Field(pattern=r"^(T[2-7]|CN)(-(T[2-7]|CN))*$")
    hinh_thuc: Literal["offline", "online"]
    si_so_toi_da: int = Field(ge=1, le=60)
    si_so_toi_thieu: int = Field(ge=1, le=60)
    giang_vien_id: int | None = None
    phong_hoc_id: int | None = None


class ClassPatch(BaseModel):
    giang_vien_id: int | None = None
    phong_hoc_id: int | None = None
    ca_hoc: Literal["sang", "chieu", "toi"] | None = None
    lich_hoc: str | None = Field(default=None, pattern=r"^(T[2-7]|CN)(-(T[2-7]|CN))*$")
    si_so_toi_da: int | None = Field(default=None, ge=1, le=60)
    si_so_toi_thieu: int | None = Field(default=None, ge=1, le=60)


class ReasonIn(BaseModel):
    ly_do: str = Field(min_length=3, max_length=500)


class AttendanceEntry(BaseModel):
    don_hang_id: int
    trang_thai: Literal["co_mat", "vang", "vang_co_phep", "di_tre"]
    ghi_chu: str | None = Field(default=None, max_length=300)


class AttendanceIn(BaseModel):
    entries: list[AttendanceEntry] = Field(min_length=1, max_length=80)


@router.get("/courses", tags=["đào tạo"])
def courses(conn=Depends(db), me: Actor = Depends(actor)):
    return training.list_courses(conn, me)


@router.get("/classes", tags=["đào tạo"])
def classes(
    trang_thai: str | None = None,
    khoa_hoc_id: int | None = None,
    q: str | None = None,
    conn=Depends(db),
    me: Actor = Depends(actor),
):
    return training.list_classes(conn, me, trang_thai, khoa_hoc_id, q)


@router.post("/classes", tags=["đào tạo"], status_code=201)
def create_class(body: ClassIn, conn=Depends(db), me: Actor = Depends(actor)):
    return training.create_class(conn, me, body.model_dump())


@router.get("/classes/{class_id}", tags=["đào tạo"])
def get_class(class_id: int, conn=Depends(db), me: Actor = Depends(actor)):
    return training.get_class(conn, me, class_id)


@router.patch("/classes/{class_id}", tags=["đào tạo"])
def patch_class(class_id: int, body: ClassPatch, conn=Depends(db), me: Actor = Depends(actor)):
    return training.update_schedule(conn, me, class_id, body.model_dump(exclude_none=True))


@router.post("/classes/{class_id}/open", tags=["đào tạo"])
def open_class(class_id: int, conn=Depends(db), me: Actor = Depends(actor)):
    return training.open_class(conn, me, class_id)


@router.post("/classes/{class_id}/cancel", tags=["đào tạo"])
def cancel_class(class_id: int, body: ReasonIn, conn=Depends(db), me: Actor = Depends(actor)):
    return training.cancel_class(conn, me, class_id, body.ly_do)


@router.get("/teachers", tags=["đào tạo"])
def teachers(conn=Depends(db), me: Actor = Depends(actor)):
    return training.list_teachers(conn, me)


@router.get("/rooms", tags=["đào tạo"])
def rooms(conn=Depends(db), me: Actor = Depends(actor)):
    return training.list_rooms(conn, me)


@router.get("/sessions/{session_id}", tags=["học vụ"])
def session(session_id: int, conn=Depends(db), me: Actor = Depends(actor)):
    return enrollment.session_roster(conn, me, session_id)


@router.post("/sessions/{session_id}/attendance", tags=["học vụ"])
def attendance(session_id: int, body: AttendanceIn, conn=Depends(db), me: Actor = Depends(actor)):
    return enrollment.mark_attendance(conn, me, session_id, [e.model_dump() for e in body.entries])


# ---------------------------------------------------------------- học viên & ghi danh
class EnrollIn(BaseModel):
    hoc_vien_id: int
    lop_hoc_id: int
    tra_gop: bool = False
    uu_dai: Literal["dang_ky_som", "nhom", "hoc_vien_cu", "hssv"] | None = None
    voucher: str | None = Field(default=None, max_length=20)
    khach_id: int | None = None


class TransferIn(BaseModel):
    lop_moi_id: int
    ly_do: str = Field(default="", max_length=500)


class ReserveIn(BaseModel):
    so_thang: int = Field(ge=1, le=6)
    ly_do: str = Field(min_length=3, max_length=500)
    mien_phi: bool = False


class GradeIn(BaseModel):
    loai: Literal["giua_khoa", "cuoi_khoa"]
    diem: float = Field(ge=0, le=100)
    nhan_xet: str | None = Field(default=None, max_length=500)


@router.get("/students", tags=["học vụ"])
def list_students(q: str | None = None, conn=Depends(db), me: Actor = Depends(actor)):
    return students.list_students(conn, me, q)


@router.get("/students/{student_id}", tags=["học vụ"])
def get_student(student_id: int, conn=Depends(db), me: Actor = Depends(actor)):
    return students.get_student(conn, me, student_id)


@router.post("/enrollments/quote", tags=["học vụ"])
def quote(body: EnrollIn, conn=Depends(db), me: Actor = Depends(actor)):
    q = enrollment.quote(conn, me, body.hoc_vien_id, body.lop_hoc_id, body.tra_gop, body.uu_dai, body.voucher)
    return {k: v for k, v in q.items() if not k.startswith("_")}


@router.post("/enrollments", tags=["học vụ"], status_code=201)
def enroll(body: EnrollIn, conn=Depends(db), me: Actor = Depends(actor)):
    return enrollment.enroll(
        conn, me, body.hoc_vien_id, body.lop_hoc_id, body.tra_gop, body.uu_dai, body.voucher, body.khach_id
    )


@router.post("/enrollments/{enrollment_id}/transfer", tags=["học vụ"])
def transfer(enrollment_id: int, body: TransferIn, conn=Depends(db), me: Actor = Depends(actor)):
    return enrollment.transfer(conn, me, enrollment_id, body.lop_moi_id, body.ly_do)


@router.post("/enrollments/{enrollment_id}/reserve", tags=["học vụ"])
def reserve(enrollment_id: int, body: ReserveIn, conn=Depends(db), me: Actor = Depends(actor)):
    return enrollment.reserve(conn, me, enrollment_id, body.so_thang, body.ly_do, body.mien_phi)


@router.post("/enrollments/{enrollment_id}/cancel", tags=["học vụ"])
def cancel_enrollment(enrollment_id: int, body: ReasonIn, conn=Depends(db), me: Actor = Depends(actor)):
    return enrollment.cancel_enrollment(conn, me, enrollment_id, body.ly_do)


@router.post("/enrollments/{enrollment_id}/complete", tags=["học vụ"])
def complete(enrollment_id: int, conn=Depends(db), me: Actor = Depends(actor)):
    return enrollment.complete(conn, me, enrollment_id)


@router.post("/enrollments/{enrollment_id}/grades", tags=["học vụ"])
def grade(enrollment_id: int, body: GradeIn, conn=Depends(db), me: Actor = Depends(actor)):
    return enrollment.set_grade(conn, me, enrollment_id, body.loai, body.diem, body.nhan_xet)


# ---------------------------------------------------------------- tài chính
class PaymentIn(BaseModel):
    so_tien: int = Field(gt=0)
    phuong_thuc: Literal["chuyen_khoan", "tien_mat", "the"]
    ghi_chu: str | None = Field(default=None, max_length=300)


class DecideIn(BaseModel):
    duyet: bool


class VoucherIn(BaseModel):
    hoc_vien_id: int
    phan_tram: int = Field(ge=1, le=30)
    ly_do: str = Field(min_length=3, max_length=300)
    so_ngay: int = Field(default=30, ge=1, le=90)


@router.get("/invoices", tags=["tài chính"])
def invoices(
    trang_thai: str | None = None,
    q: str | None = None,
    qua_han: bool = False,
    conn=Depends(db),
    me: Actor = Depends(actor),
):
    return finance.list_invoices(conn, me, trang_thai, q, qua_han)


@router.get("/invoices/summary", tags=["tài chính"])
def invoice_summary(conn=Depends(db), me: Actor = Depends(actor)):
    return finance.debt_summary(conn, me)


@router.get("/invoices/{invoice_id}", tags=["tài chính"])
def invoice(invoice_id: int, conn=Depends(db), me: Actor = Depends(actor)):
    return finance.get_invoice(conn, me, invoice_id)


@router.post("/invoices/{invoice_id}/payments", tags=["tài chính"])
def pay(invoice_id: int, body: PaymentIn, conn=Depends(db), me: Actor = Depends(actor)):
    return finance.record_payment(conn, me, invoice_id, body.so_tien, body.phuong_thuc, body.ghi_chu)


@router.get("/refunds", tags=["tài chính"])
def refunds(trang_thai: str | None = "cho_duyet", conn=Depends(db), me: Actor = Depends(actor)):
    return finance.list_refunds(conn, me, trang_thai or None)


@router.post("/refunds/{refund_id}/decide", tags=["tài chính"])
def decide_refund(refund_id: int, body: DecideIn, conn=Depends(db), me: Actor = Depends(actor)):
    return finance.decide_refund(conn, me, refund_id, body.duyet)


@router.post("/vouchers", tags=["tài chính"], status_code=201)
def voucher(body: VoucherIn, conn=Depends(db), me: Actor = Depends(actor)):
    return finance.issue_voucher(conn, me, body.hoc_vien_id, body.phan_tram, body.ly_do, body.so_ngay)


# ---------------------------------------------------------------- cổng học viên & yêu cầu
class RequestIn(BaseModel):
    loai: Literal["bao_luu", "hoan_phi", "chuyen_lop", "khac"]
    noi_dung: str = Field(min_length=5, max_length=2000)
    don_hang_id: int | None = None


class HandleIn(BaseModel):
    duyet: bool
    phan_hoi: str = Field(min_length=2, max_length=1000)
    so_thang: int | None = Field(default=None, ge=1, le=6)
    mien_phi: bool = False
    lop_moi_id: int | None = None


@router.get("/portal", tags=["cổng học viên"])
def portal(conn=Depends(db), me: Actor = Depends(actor)):
    return students.portal_overview(conn, me)


@router.post("/portal/requests", tags=["cổng học viên"], status_code=201)
def submit_request(body: RequestIn, conn=Depends(db), me: Actor = Depends(actor)):
    return students.submit_request(conn, me, body.loai, body.noi_dung, body.don_hang_id)


@router.get("/requests", tags=["cổng học viên"])
def requests(trang_thai: str | None = None, conn=Depends(db), me: Actor = Depends(actor)):
    return students.list_requests(conn, me, trang_thai)


@router.post("/requests/{request_id}/handle", tags=["cổng học viên"])
def handle_request(request_id: int, body: HandleIn, conn=Depends(db), me: Actor = Depends(actor)):
    params = {"so_thang": body.so_thang or 3, "mien_phi": body.mien_phi, "lop_moi_id": body.lop_moi_id}
    return students.handle_request(conn, me, request_id, body.duyet, body.phan_hoi, params)


# ---------------------------------------------------------------- hộp duyệt & agent
class ApproveIn(BaseModel):
    edits: dict | None = None


class RejectIn(BaseModel):
    ly_do: str = Field(default="", max_length=500)


class BulkIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=100)
    duyet: bool
    ly_do: str = Field(default="", max_length=500)


class PolicyIn(BaseModel):
    muc: Literal["L0", "L1", "L2"]
    han_muc_ngay: int = Field(ge=0, le=10_000)


@router.get("/proposals", tags=["hộp duyệt"])
def list_proposals(
    trang_thai: str | None = Query(default="can_xu_ly"),
    agent: str | None = None,
    conn=Depends(db),
    me: Actor = Depends(actor),
):
    return proposals.list_proposals(conn, me, trang_thai or None, agent)


@router.get("/proposals/counts", tags=["hộp duyệt"])
def proposal_counts(conn=Depends(db), me: Actor = Depends(actor)):
    return proposals.counts(conn, me)


@router.get("/proposals/{pid}", tags=["hộp duyệt"])
def get_proposal(pid: int, conn=Depends(db), me: Actor = Depends(actor)):
    return proposals.get(conn, me, pid)


@router.post("/proposals/{pid}/approve", tags=["hộp duyệt"])
def approve(pid: int, body: ApproveIn, conn=Depends(db), me: Actor = Depends(actor)):
    return proposals.approve(conn, me, pid, body.edits)


@router.post("/proposals/{pid}/reject", tags=["hộp duyệt"])
def reject(pid: int, body: RejectIn, conn=Depends(db), me: Actor = Depends(actor)):
    return proposals.reject(conn, me, pid, body.ly_do)


@router.post("/proposals/{pid}/dismiss", tags=["hộp duyệt"])
def dismiss(pid: int, conn=Depends(db), me: Actor = Depends(actor)):
    return proposals.dismiss(conn, me, pid)


@router.post("/proposals/bulk", tags=["hộp duyệt"])
def bulk(body: BulkIn, conn=Depends(db), me: Actor = Depends(actor)):
    return proposals.bulk_decide(conn, me, body.ids, body.duyet, body.ly_do)


@router.get("/autonomy", tags=["agent"])
def policies(conn=Depends(db), me: Actor = Depends(actor)):
    return proposals.list_policies(conn, me)


@router.put("/autonomy/{action_type}", tags=["agent"])
def set_policy(action_type: str, body: PolicyIn, conn=Depends(db), me: Actor = Depends(actor)):
    return proposals.update_policy(conn, me, action_type, body.muc, body.han_muc_ngay)


@router.get("/agents", tags=["agent"])
def agents(conn=Depends(db), me: Actor = Depends(actor)):
    from eduassist.background.agents import AGENTS

    require(me, "chat.data")
    last = {
        r["agent"]: r
        for r in conn.execute(
            """SELECT DISTINCT ON (agent) agent, bat_dau, ket_thuc, trang_thai, so_de_xuat, so_tu_dong, tom_tat, loi
               FROM lan_chay_agent ORDER BY agent, bat_dau DESC"""
        ).fetchall()
    }
    return [
        {
            "name": a.name,
            "label": a.label,
            "role": a.role,
            "role_label": ROLE_LABEL[a.role],
            "schedule": a.schedule,
            "events": list(a.events),
            "description": a.description,
            "last_run": last.get(a.name),
        }
        for a in AGENTS.values()
    ]


@router.post("/agents/{name}/run", tags=["agent"])
def run_now(name: str, user: AuthUser = Depends(current_user)):
    """Chạy ngay một agent (ngoài lịch). Agent chạy trong transaction riêng của nó."""
    from eduassist.background.agents import AGENTS
    from eduassist.background.runner import run_agent

    require(user.actor(), "agent.run")
    if name not in AGENTS:
        raise NotFound("Không có agent này.")
    return run_agent(name, f"thu_cong:{user.username}")


@router.get("/agents/runs", tags=["agent"])
def runs(
    agent: str | None = None, limit: int = Query(default=50, le=200), conn=Depends(db), me: Actor = Depends(actor)
):
    require(me, "chat.data")
    return conn.execute(
        """SELECT * FROM lan_chay_agent WHERE %(a)s::text IS NULL OR agent = %(a)s ORDER BY bat_dau DESC LIMIT %(l)s""",
        {"a": agent, "l": limit},
    ).fetchall()


@router.get("/agents/stats", tags=["agent"])
def agent_stats(days: int = Query(default=30, ge=1, le=365), conn=Depends(db), me: Actor = Depends(actor)):
    return proposals.stats(conn, me, days)


@router.get("/audit", tags=["quản trị"])
def audit_log(
    actor_id: str | None = None,
    doi_tuong: str | None = None,
    chi_agent: bool = False,
    limit: int = Query(default=100, le=500),
    conn=Depends(db),
    me: Actor = Depends(actor),
):
    require(me, "audit.read")
    return conn.execute(
        """SELECT * FROM audit_log
           WHERE (%(a)s::text IS NULL OR actor = %(a)s) AND (%(o)s::text IS NULL OR doi_tuong = %(o)s)
             AND (NOT %(ag)s OR actor LIKE 'agent:%%' OR de_xuat_id IS NOT NULL)
           ORDER BY created_at DESC LIMIT %(l)s""",
        {"a": actor_id, "o": doi_tuong, "ag": chi_agent, "l": limit},
    ).fetchall()
