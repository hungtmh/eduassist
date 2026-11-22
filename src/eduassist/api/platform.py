"""REST API cho nghiệp vụ. Router MỎNG: mở transaction, dựng Actor từ JWT, gọi tầng Service.

Không có luật nghiệp vụ hay kiểm tra quyền nào ở đây - tất cả nằm trong eduassist.services, để giao diện web và
agent đi qua đúng cùng một chỗ. Mỗi request = một transaction: lỗi giữa chừng thì không có gì được ghi.
"""

from collections.abc import Iterator
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from eduassist.api.auth import AuthUser, current_user, current_user_any
from eduassist.api.fastjson import FastJSONRoute
from eduassist.services import (
    accounts,
    crm,
    enrollment,
    finance,
    notifications,
    proposals,
    reports,
    students,
    training,
    workday,
)
from eduassist.services.core import PERMISSIONS, ROLE_LABEL, Actor, NotFound, Page, paginate, require

router = APIRouter(route_class=FastJSONRoute)


def db() -> Iterator:
    """Một transaction cho cả request. Luôn khai báo Depends(db, scope="function"): COMMIT chạy TRƯỚC khi gửi
    response, nên commit lỗi thì client nhận lỗi, không nhận 200 cho dữ liệu chưa lưu (mặc định của FastAPI là
    commit SAU khi đã gửi response). tests/test_db_scope.py kiểm tra điều này."""
    from eduassist import cache
    from eduassist.db import app_pool

    with app_pool().connection() as conn:
        try:
            with conn.transaction():
                yield conn
        except BaseException:
            cache.discard_pending(conn)
            raise
        # Đã commit: giờ mới xoá cache tài khoản vừa đổi (xem cache.account_changed)
        cache.flush_after_commit(conn)


def read_db() -> Iterator:
    """Kết nối chỉ đọc cho trang công khai / báo cáo: bản sao đọc nếu có DATABASE_READ_URL, không thì DB chính."""
    from eduassist.db import read_pool

    with read_pool().connection() as conn:
        yield conn


def actor(user: AuthUser = Depends(current_user)) -> Actor:
    return user.actor()


# Phân trang: ?limit=&offset=, tổng số dòng trả trong header X-Total-Count (body vẫn là danh sách)
Limit = Query(default=100, ge=1, le=500)
Offset = Query(default=0, ge=0)


def paged(response: Response, page: Page) -> Page:
    response.headers["X-Total-Count"] = str(page.total)
    return page


# ---------------------------------------------------------------- tài khoản
@router.get("/me/profile", tags=["tài khoản"])
def profile(user: AuthUser = Depends(current_user_any)):
    return {
        "must_change_password": user.must_change_password,
        "username": user.username,
        "role": user.role,
        "role_label": ROLE_LABEL[user.role],
        "display_name": user.display_name,
        "hoc_vien_id": user.hoc_vien_id,
        "giang_vien_id": user.giang_vien_id,
        "permissions": sorted(PERMISSIONS[user.role]),
    }


@router.get("/me/today", tags=["tài khoản"])
def my_day(conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return workday.my_day(conn, me)


@router.get("/schedule", tags=["đào tạo"])
def schedule(
    tu: date,
    den: date,
    giang_vien_id: int | None = None,
    phong_hoc_id: int | None = None,
    lop_hoc_id: int | None = None,
    conn=Depends(db, scope="function"),
    me: Actor = Depends(actor),
):
    return workday.schedule(conn, me, tu, den, giang_vien_id, phong_hoc_id, lop_hoc_id)


@router.get("/notifications", tags=["thông báo"])
def list_notifications(conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return notifications.list_notifications(conn, me)


class IdsBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)


@router.post("/notifications/read", tags=["thông báo"])
def read_notifications(body: IdsBody, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    notifications.mark_read(conn, me, body.ids)
    return {"ok": True}


DASHBOARD_TTL = 60


@router.get("/dashboard", tags=["báo cáo"])
def dashboard(me: Actor = Depends(actor)):
    """Bản tin của quản lý giống nhau cho mọi người xem, gồm các phép cộng trên bảng lớn (điểm danh 28 ngày, công nợ):
    cache chung 60 giây. Trúng cache thì không mượn kết nối DB."""
    from eduassist import cache
    from eduassist.db import app_pool

    require(me, "report.read")

    def load():
        with app_pool().connection() as conn:
            return reports.dashboard(conn, me)

    return cache.cached_json("dashboard", DASHBOARD_TTL, load)


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
    response: Response,
    trang_thai: str | None = None,
    phu_trach: str | None = None,
    q: str | None = None,
    limit: int = Limit,
    offset: int = Offset,
    conn=Depends(db, scope="function"),
    me: Actor = Depends(actor),
):
    return paged(response, crm.list_leads(conn, me, trang_thai, phu_trach, q, limit, offset))


@router.get("/leads/counts", tags=["tuyển sinh"])
def lead_counts(conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return crm.lead_counts(conn, me)


@router.post("/leads", tags=["tuyển sinh"], status_code=201)
def create_lead(body: LeadIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return crm.create_lead(conn, me, body.model_dump())


@router.get("/leads/{lead_id}", tags=["tuyển sinh"])
def get_lead(lead_id: int, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return crm.get_lead(conn, me, lead_id)


@router.post("/leads/{lead_id}/transition", tags=["tuyển sinh"])
def transition_lead(lead_id: int, body: TransitionIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return crm.transition(conn, me, lead_id, body.trang_thai, body.ghi_chu)


@router.post("/leads/{lead_id}/contact", tags=["tuyển sinh"])
def contact_lead(lead_id: int, body: NoteIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return crm.log_contact(conn, me, lead_id, body.ghi_chu)


@router.post("/leads/{lead_id}/appointments", tags=["tuyển sinh"])
def book(lead_id: int, body: AppointmentIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return crm.book_appointment(conn, me, lead_id, body.loai, body.thoi_gian, body.lop_hoc_id)


@router.post("/leads/{lead_id}/convert", tags=["tuyển sinh"])
def convert(lead_id: int, body: ConvertIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return crm.convert_to_student(conn, me, lead_id, body.nam_sinh, body.thanh_pho)


@router.get("/tasks", tags=["tuyển sinh"])
def list_tasks(
    response: Response,
    mine: bool = True,
    trang_thai: str = "mo",
    limit: int = Limit,
    offset: int = Offset,
    conn=Depends(db, scope="function"),
    me: Actor = Depends(actor),
):
    return paged(response, crm.list_tasks(conn, me, mine, trang_thai, limit, offset))


@router.post("/tasks/{task_id}/done", tags=["tuyển sinh"])
def task_done(task_id: int, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
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


class CourseIn(BaseModel):
    ma: str = Field(min_length=2, max_length=20)
    ten: str = Field(min_length=3, max_length=150)
    danh_muc: str
    trinh_do: str
    hoc_phi: int
    so_buoi: int
    mo_ta: str = Field(min_length=10, max_length=4000)
    dang_mo_ban: bool = True
    slug: str | None = Field(default=None, max_length=80)
    mo_ta_ngan: str | None = Field(default=None, max_length=200)
    doi_tuong: str | None = Field(default=None, max_length=500)
    ket_qua: str | None = Field(default=None, max_length=500)
    lo_trinh: list[dict] | None = None


class CoursePatch(BaseModel):
    ten: str | None = Field(default=None, min_length=3, max_length=150)
    danh_muc: str | None = None
    trinh_do: str | None = None
    hoc_phi: int | None = None
    so_buoi: int | None = None
    mo_ta: str | None = Field(default=None, min_length=10, max_length=4000)
    dang_mo_ban: bool | None = None
    slug: str | None = Field(default=None, max_length=80)
    mo_ta_ngan: str | None = Field(default=None, max_length=200)
    doi_tuong: str | None = Field(default=None, max_length=500)
    ket_qua: str | None = Field(default=None, max_length=500)
    lo_trinh: list[dict] | None = None


@router.get("/courses", tags=["đào tạo"])
def courses(dang_ban: bool = False, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return training.list_courses(conn, me, dang_ban)


@router.get("/courses/options", tags=["đào tạo"])
def course_options(me: Actor = Depends(actor)):
    return {"danh_muc": training.COURSE_CATEGORIES, "trinh_do": training.COURSE_LEVELS}


@router.post("/courses", tags=["đào tạo"], status_code=201)
def create_course(body: CourseIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return training.create_course(conn, me, body.model_dump(exclude_none=True))


@router.patch("/courses/{course_id}", tags=["đào tạo"])
def update_course(course_id: int, body: CoursePatch, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return training.update_course(conn, me, course_id, body.model_dump(exclude_none=True))


@router.get("/classes", tags=["đào tạo"])
def classes(
    response: Response,
    trang_thai: str | None = None,
    khoa_hoc_id: int | None = None,
    q: str | None = None,
    con_mo: bool = False,
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Offset,
    conn=Depends(db, scope="function"),
    me: Actor = Depends(actor),
):
    """con_mo=true: chỉ lớp đang học / sắp khai giảng. Có limit: phân trang, tổng ở header X-Total-Count."""
    rows = training.list_classes(conn, me, trang_thai, khoa_hoc_id, q, con_mo, limit, offset)
    return paged(response, rows) if limit is not None else rows


@router.post("/classes", tags=["đào tạo"], status_code=201)
def create_class(body: ClassIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return training.create_class(conn, me, body.model_dump())


@router.get("/classes/{class_id}", tags=["đào tạo"])
def get_class(class_id: int, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return training.get_class(conn, me, class_id)


@router.patch("/classes/{class_id}", tags=["đào tạo"])
def patch_class(class_id: int, body: ClassPatch, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return training.update_schedule(conn, me, class_id, body.model_dump(exclude_none=True))


@router.post("/classes/{class_id}/open", tags=["đào tạo"])
def open_class(class_id: int, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return training.open_class(conn, me, class_id)


@router.post("/classes/{class_id}/cancel", tags=["đào tạo"])
def cancel_class(class_id: int, body: ReasonIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return training.cancel_class(conn, me, class_id, body.ly_do)


@router.get("/teachers", tags=["đào tạo"])
def teachers(conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return training.list_teachers(conn, me)


@router.get("/rooms", tags=["đào tạo"])
def rooms(conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return training.list_rooms(conn, me)


class BranchIn(BaseModel):
    ten: str = Field(min_length=2, max_length=100)
    dia_chi: str = Field(min_length=5, max_length=300)


class RoomIn(BaseModel):
    co_so_id: int
    ten: str = Field(min_length=1, max_length=50)
    suc_chua: int


class TeacherIn(BaseModel):
    ho_ten: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    chuyen_mon: str = Field(min_length=2, max_length=200)
    tieu_su: str | None = Field(default=None, max_length=1000)
    hien_thi_cong_khai: bool = True


@router.get("/branches", tags=["đào tạo"])
def branches(conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return training.list_branches(conn, me)


@router.post("/branches", tags=["đào tạo"], status_code=201)
def create_branch(body: BranchIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return training.save_branch(conn, me, None, body.ten, body.dia_chi)


@router.put("/branches/{branch_id}", tags=["đào tạo"])
def update_branch(branch_id: int, body: BranchIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return training.save_branch(conn, me, branch_id, body.ten, body.dia_chi)


@router.post("/rooms", tags=["đào tạo"], status_code=201)
def create_room(body: RoomIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return training.save_room(conn, me, None, body.co_so_id, body.ten, body.suc_chua)


@router.put("/rooms/{room_id}", tags=["đào tạo"])
def update_room(room_id: int, body: RoomIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return training.save_room(conn, me, room_id, body.co_so_id, body.ten, body.suc_chua)


@router.post("/teachers", tags=["đào tạo"], status_code=201)
def create_teacher(body: TeacherIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return training.save_teacher(
        conn, me, None, body.ho_ten, body.email, body.chuyen_mon, body.tieu_su, body.hien_thi_cong_khai
    )


@router.put("/teachers/{teacher_id}", tags=["đào tạo"])
def update_teacher(teacher_id: int, body: TeacherIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return training.save_teacher(
        conn, me, teacher_id, body.ho_ten, body.email, body.chuyen_mon, body.tieu_su, body.hien_thi_cong_khai
    )


@router.get("/sessions/{session_id}", tags=["học vụ"])
def session(session_id: int, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return enrollment.session_roster(conn, me, session_id)


@router.post("/sessions/{session_id}/attendance", tags=["học vụ"])
def attendance(session_id: int, body: AttendanceIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
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
def list_students(
    response: Response,
    q: str | None = None,
    limit: int = Limit,
    offset: int = Offset,
    conn=Depends(db, scope="function"),
    me: Actor = Depends(actor),
):
    return paged(response, students.list_students(conn, me, q, limit, offset))


class StudentAccountIn(BaseModel):
    gui_email: bool = True


@router.get("/students/{student_id}/account", tags=["tài khoản"])
def student_account(student_id: int, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return {"account": accounts.student_account(conn, me, student_id)}


@router.post("/students/{student_id}/account", tags=["tài khoản"], status_code=201)
def create_student_account(
    student_id: int, body: StudentAccountIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)
):
    return accounts.create_student_account(conn, me, student_id, body.gui_email)


@router.get("/students/{student_id}", tags=["học vụ"])
def get_student(student_id: int, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return students.get_student(conn, me, student_id)


@router.post("/enrollments/quote", tags=["học vụ"])
def quote(body: EnrollIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    q = enrollment.quote(conn, me, body.hoc_vien_id, body.lop_hoc_id, body.tra_gop, body.uu_dai, body.voucher)
    return {k: v for k, v in q.items() if not k.startswith("_")}


@router.post("/enrollments", tags=["học vụ"], status_code=201)
def enroll(body: EnrollIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return enrollment.enroll(
        conn, me, body.hoc_vien_id, body.lop_hoc_id, body.tra_gop, body.uu_dai, body.voucher, body.khach_id
    )


@router.post("/enrollments/{enrollment_id}/transfer", tags=["học vụ"])
def transfer(enrollment_id: int, body: TransferIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return enrollment.transfer(conn, me, enrollment_id, body.lop_moi_id, body.ly_do)


@router.post("/enrollments/{enrollment_id}/reserve", tags=["học vụ"])
def reserve(enrollment_id: int, body: ReserveIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return enrollment.reserve(conn, me, enrollment_id, body.so_thang, body.ly_do, body.mien_phi)


@router.post("/enrollments/{enrollment_id}/cancel", tags=["học vụ"])
def cancel_enrollment(
    enrollment_id: int, body: ReasonIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)
):
    return enrollment.cancel_enrollment(conn, me, enrollment_id, body.ly_do)


@router.post("/enrollments/{enrollment_id}/complete", tags=["học vụ"])
def complete(enrollment_id: int, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return enrollment.complete(conn, me, enrollment_id)


@router.post("/enrollments/{enrollment_id}/grades", tags=["học vụ"])
def grade(enrollment_id: int, body: GradeIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
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
    response: Response,
    trang_thai: str | None = None,
    q: str | None = None,
    qua_han: bool = False,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Offset,
    conn=Depends(db, scope="function"),
    me: Actor = Depends(actor),
):
    return paged(response, finance.list_invoices(conn, me, trang_thai, q, qua_han, limit, offset))


@router.get("/invoices/summary", tags=["tài chính"])
def invoice_summary(conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return finance.debt_summary(conn, me)


@router.get("/invoices/{invoice_id}", tags=["tài chính"])
def invoice(invoice_id: int, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return finance.get_invoice(conn, me, invoice_id)


@router.post("/invoices/{invoice_id}/payments", tags=["tài chính"])
def pay(invoice_id: int, body: PaymentIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return finance.record_payment(conn, me, invoice_id, body.so_tien, body.phuong_thuc, body.ghi_chu)


@router.get("/refunds", tags=["tài chính"])
def refunds(trang_thai: str | None = "cho_duyet", conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return finance.list_refunds(conn, me, trang_thai or None)


@router.post("/refunds/{refund_id}/decide", tags=["tài chính"])
def decide_refund(refund_id: int, body: DecideIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return finance.decide_refund(conn, me, refund_id, body.duyet)


@router.post("/vouchers", tags=["tài chính"], status_code=201)
def voucher(body: VoucherIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
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
def portal(conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return students.portal_overview(conn, me)


@router.post("/portal/requests", tags=["cổng học viên"], status_code=201)
def submit_request(body: RequestIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return students.submit_request(conn, me, body.loai, body.noi_dung, body.don_hang_id)


@router.get("/requests", tags=["cổng học viên"])
def requests(
    response: Response,
    trang_thai: str | None = None,
    limit: int = Limit,
    offset: int = Offset,
    conn=Depends(db, scope="function"),
    me: Actor = Depends(actor),
):
    return paged(response, students.list_requests(conn, me, trang_thai, limit, offset))


@router.post("/requests/{request_id}/handle", tags=["cổng học viên"])
def handle_request(request_id: int, body: HandleIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
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
    response: Response,
    trang_thai: str | None = Query(default="can_xu_ly"),
    agent: str | None = None,
    limit: int = Limit,
    offset: int = Offset,
    conn=Depends(db, scope="function"),
    me: Actor = Depends(actor),
):
    return paged(response, proposals.list_proposals(conn, me, trang_thai or None, agent, limit, offset))


@router.get("/proposals/counts", tags=["hộp duyệt"])
def proposal_counts(conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return proposals.counts(conn, me)


@router.get("/proposals/{pid}", tags=["hộp duyệt"])
def get_proposal(pid: int, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return proposals.get(conn, me, pid)


@router.post("/proposals/{pid}/approve", tags=["hộp duyệt"])
def approve(pid: int, body: ApproveIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return proposals.approve(conn, me, pid, body.edits)


@router.post("/proposals/{pid}/reject", tags=["hộp duyệt"])
def reject(pid: int, body: RejectIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return proposals.reject(conn, me, pid, body.ly_do)


@router.post("/proposals/{pid}/dismiss", tags=["hộp duyệt"])
def dismiss(pid: int, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return proposals.dismiss(conn, me, pid)


@router.post("/proposals/bulk", tags=["hộp duyệt"])
def bulk(body: BulkIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return proposals.bulk_decide(conn, me, body.ids, body.duyet, body.ly_do)


@router.get("/autonomy", tags=["agent"])
def policies(conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return proposals.list_policies(conn, me)


@router.put("/autonomy/{action_type}", tags=["agent"])
def set_policy(action_type: str, body: PolicyIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return proposals.update_policy(conn, me, action_type, body.muc, body.han_muc_ngay)


@router.get("/agents", tags=["agent"])
def agents(conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
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


@router.post("/agents/{name}/run", tags=["agent"], status_code=202)
def run_now(name: str, conn=Depends(db, scope="function"), user: AuthUser = Depends(current_user)):
    """Yêu cầu chạy ngay một agent (ngoài lịch). Worker nhận trong vài giây; theo dõi kết quả bằng
    GET /agents/requests/{yeu_cau_id}. Không chạy trong request API: agent có thể gọi LLM vài chục giây."""
    from eduassist.background.agents import AGENTS
    from eduassist.background.runner import request_run

    require(user.actor(), "agent.run")
    if name not in AGENTS:
        raise NotFound("Không có agent này.")
    return request_run(conn, name, user.username)


@router.get("/agents/requests/{request_id}", tags=["agent"])
def run_request(request_id: int, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    from eduassist.background.runner import run_request_status

    require(me, "agent.run")
    st = run_request_status(conn, request_id)
    if st is None:
        raise NotFound("Không có yêu cầu này.")
    return st


@router.get("/agents/runs", tags=["agent"])
def runs(
    agent: str | None = None,
    limit: int = Query(default=50, le=200),
    conn=Depends(db, scope="function"),
    me: Actor = Depends(actor),
):
    require(me, "chat.data")
    return conn.execute(
        """SELECT * FROM lan_chay_agent WHERE %(a)s::text IS NULL OR agent = %(a)s ORDER BY bat_dau DESC LIMIT %(l)s""",
        {"a": agent, "l": limit},
    ).fetchall()


@router.get("/agents/stats", tags=["agent"])
def agent_stats(
    days: int = Query(default=30, ge=1, le=365), conn=Depends(db, scope="function"), me: Actor = Depends(actor)
):
    return proposals.stats(conn, me, days)


@router.get("/audit", tags=["quản trị"])
def audit_log(
    response: Response,
    actor_id: str | None = None,
    doi_tuong: str | None = None,
    chi_agent: bool = False,
    limit: int = Limit,
    offset: int = Offset,
    conn=Depends(db, scope="function"),
    me: Actor = Depends(actor),
):
    require(me, "audit.read")
    page = paginate(
        conn,
        """SELECT * FROM audit_log
           WHERE (%(a)s::text IS NULL OR actor = %(a)s) AND (%(o)s::text IS NULL OR doi_tuong = %(o)s)
             AND (NOT %(ag)s OR actor LIKE 'agent:%%' OR de_xuat_id IS NOT NULL)""",
        {"a": actor_id, "o": doi_tuong, "ag": chi_agent},
        "created_at DESC, id DESC",
        limit,
        offset,
    )
    return paged(response, page)


# ---------------------------------------------------------------- quản trị tài khoản
class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    display_name: str = Field(min_length=2, max_length=80)
    role: Literal["consultant", "academic", "accountant", "teacher", "manager"]
    email: str | None = Field(default=None, max_length=254)
    giang_vien_id: int | None = None
    gui_email: bool = False


class UserPatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    role: Literal["consultant", "academic", "accountant", "teacher", "manager"] | None = None
    email: str | None = Field(default=None, max_length=254)
    active: bool | None = None


class ResetPwIn(BaseModel):
    gui_email: bool = False


@router.get("/users", tags=["quản trị"])
def list_users(
    response: Response,
    q: str | None = None,
    role: str | None = None,
    limit: int = Limit,
    offset: int = Offset,
    conn=Depends(db, scope="function"),
    me: Actor = Depends(actor),
):
    return paged(response, accounts.list_users(conn, me, q, role, limit, offset))


@router.post("/users", tags=["quản trị"], status_code=201)
def create_user(body: UserIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return accounts.create_staff_user(
        conn, me, body.username, body.display_name, body.role, body.email, body.giang_vien_id, body.gui_email
    )


@router.patch("/users/{username}", tags=["quản trị"])
def update_user(username: str, body: UserPatch, conn=Depends(db, scope="function"), me: Actor = Depends(actor)):
    return accounts.update_user(conn, me, username, body.display_name, body.role, body.email, body.active)


@router.post("/users/{username}/reset-password", tags=["quản trị"])
def admin_reset_password(
    username: str, body: ResetPwIn, conn=Depends(db, scope="function"), me: Actor = Depends(actor)
):
    return accounts.admin_reset_password(conn, me, username, body.gui_email)
