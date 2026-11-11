"""Tầng Service với Postgres thật: luật nghiệp vụ, phân quyền, hộp duyệt, agent nền.

Mỗi test chạy trong MỘT transaction rồi rollback -> không để lại dữ liệu; email bị bắt lại, không gửi SMTP.
Chạy: uv run pytest -m integration  (cần `uv run eduassist-setup` trước)
"""

from datetime import date, timedelta

import psycopg
import pytest
from psycopg.rows import dict_row

from eduassist.background.runner import run_agent
from eduassist.config import get_settings
from eduassist.evals.background import CLEAN_AGENT_STATE
from eduassist.services import crm, enrollment, finance, proposals, students, training
from eduassist.services.core import Actor, Conflict, Forbidden, RuleViolation, agent_actor, business_date
from eduassist.services.notifications import capture_mail

pytestmark = pytest.mark.integration

MANAGER = Actor("quanly", "manager")
CONSULTANT = Actor("tuvan", "consultant")
ACADEMIC = Actor("giaovu", "academic")
ACCOUNTANT = Actor("ketoan", "accountant")


@pytest.fixture
def conn(monkeypatch):
    monkeypatch.setenv("BACKGROUND_LLM", "false")
    get_settings.cache_clear()
    with psycopg.connect(get_settings().database_url, row_factory=dict_row, autocommit=True) as c:
        tx = c.transaction(force_rollback=True)
        with tx:
            c.execute(CLEAN_AGENT_STATE)  # không phụ thuộc lần chạy agent thật trước đó; rollback sau test
            yield c
    get_settings.cache_clear()


@pytest.fixture
def mails():
    box = []
    token = capture_mail(box)
    yield box
    from eduassist.services.notifications import _capture

    _capture.reset(token)


def _upcoming_class(conn, min_fee=0, seats=True):
    rows = training.list_classes(conn, MANAGER, status="sap_khai_giang")
    for c in rows:
        if c["hoc_phi"] >= min_fee and (not seats or c["si_so"] < c["si_so_toi_da"]):
            return c
    pytest.skip("không có lớp phù hợp trong dữ liệu seed")


def _new_student(conn, n=1):
    row = conn.execute(
        """INSERT INTO hoc_vien (ho_ten, email, so_dien_thoai, nam_sinh, thanh_pho, nguon, ngay_dang_ky)
           VALUES (%s, %s, '0900000000', 2000, 'TP.HCM', 'website', current_date) RETURNING id""",
        (f"Test {n}", f"test.integration.{n}@example.com"),
    ).fetchone()
    return row["id"]


# ---------------------------------------------------------------- ghi danh
def test_enroll_creates_invoice_installments_audit_and_event(conn):
    cls = _upcoming_class(conn, min_fee=5_000_000)
    hv = _new_student(conn)
    r = enrollment.enroll(conn, CONSULTANT, hv, cls["id"], installments=True)
    dots = conn.execute(
        "SELECT so_tien FROM dot_thanh_toan WHERE don_hang_id = %s ORDER BY so_thu_tu", (r["don_hang_id"],)
    ).fetchall()
    assert sum(d["so_tien"] for d in dots) == r["thanh_tien"] and len(dots) == 2
    assert conn.execute(
        "SELECT 1 FROM audit_log WHERE hanh_dong = 'ghi_danh' AND doi_tuong_id = %s", (str(r["don_hang_id"]),)
    ).fetchone()
    assert conn.execute("SELECT 1 FROM outbox_su_kien WHERE loai = 'enrollment.created'").fetchone()


def test_installments_only_for_courses_from_5m(conn):
    cheap = next(
        (
            c
            for c in training.list_classes(conn, MANAGER, status="sap_khai_giang")
            if c["hoc_phi"] < 5_000_000 and c["si_so"] < c["si_so_toi_da"]
        ),
        None,
    )
    if cheap is None:
        pytest.skip("không có lớp rẻ")
    with pytest.raises(RuleViolation, match="5.000.000"):
        enrollment.enroll(conn, CONSULTANT, _new_student(conn), cheap["id"], installments=True)


def test_cannot_exceed_max_class_size(conn):
    cls = _upcoming_class(conn)
    conn.execute("UPDATE lop_hoc SET si_so_toi_da = %s WHERE id = %s", (cls["si_so"] + 1, cls["id"]))
    enrollment.enroll(conn, CONSULTANT, _new_student(conn, 1), cls["id"])
    with pytest.raises(RuleViolation, match="đủ"):
        enrollment.enroll(conn, CONSULTANT, _new_student(conn, 2), cls["id"])


def test_duplicate_enrollment_rejected(conn):
    cls = _upcoming_class(conn)
    hv = _new_student(conn)
    enrollment.enroll(conn, CONSULTANT, hv, cls["id"])
    with pytest.raises(Conflict):
        enrollment.enroll(conn, CONSULTANT, hv, cls["id"])


def test_teacher_cannot_enroll(conn):
    with pytest.raises(Forbidden):
        enrollment.enroll(conn, Actor("giangvien", "teacher"), 1, _upcoming_class(conn)["id"])


# ---------------------------------------------------------------- tài chính
def _fresh_invoice(conn, installments=False):
    cls = _upcoming_class(conn, min_fee=5_000_000 if installments else 0)
    return enrollment.enroll(conn, CONSULTANT, _new_student(conn, 9), cls["id"], installments=installments)


def test_agent_can_never_record_payment_even_with_accountant_role(conn):
    inv = _fresh_invoice(conn)
    with pytest.raises(Forbidden, match="Agent không bao giờ"):
        finance.record_payment(conn, agent_actor("cong_no", "accountant"), inv["don_hang_id"], 1000, "tien_mat")


def test_payment_allocates_installments_and_starts_enrollment(conn):
    inv = _fresh_invoice(conn, installments=True)
    first = inv["dot"][0]["so_tien"]
    out = finance.record_payment(conn, ACCOUNTANT, inv["don_hang_id"], first, "chuyen_khoan")
    assert [d["trang_thai"] for d in out["dot"]] == ["da_thanh_toan", "chua_thanh_toan"]
    assert out["trang_thai"] == "thanh_toan_mot_phan" and out["trang_thai_hoc"] == "dang_hoc"
    with pytest.raises(RuleViolation, match="vượt"):
        finance.record_payment(conn, ACCOUNTANT, inv["don_hang_id"], out["con_no"] + 1, "the")
    done = finance.record_payment(conn, ACCOUNTANT, inv["don_hang_id"], out["con_no"], "the")
    assert done["trang_thai"] == "da_thanh_toan" and done["con_no"] == 0


def test_consultant_cannot_record_payment(conn):
    with pytest.raises(Forbidden):
        finance.record_payment(conn, CONSULTANT, _fresh_invoice(conn)["don_hang_id"], 1000, "tien_mat")


def test_refund_needs_a_second_person(conn):
    inv = _fresh_invoice(conn)
    finance.record_payment(conn, ACCOUNTANT, inv["don_hang_id"], inv["thanh_tien"], "tien_mat")
    with business_date(date.today()):
        res = enrollment.cancel_enrollment(conn, ACADEMIC, inv["don_hang_id"], "Bận việc")
    assert res["hoan_phi"]["ty_le"] in (70, 100)
    conn.execute("UPDATE hoan_phi SET created_by = 'ketoan' WHERE id = %s", (res["hoan_phi"]["id"],))
    with pytest.raises(RuleViolation, match="người thứ hai"):
        finance.decide_refund(conn, ACCOUNTANT, res["hoan_phi"]["id"], True)
    finance.decide_refund(conn, MANAGER, res["hoan_phi"]["id"], True)
    assert finance.get_invoice(conn, MANAGER, inv["don_hang_id"])["trang_thai"] == "da_hoan_tien"


def test_voucher_limit_by_role(conn):
    with pytest.raises(RuleViolation, match="15%"):
        finance.issue_voucher(conn, CONSULTANT, 1, 20, "Học viên thân thiết")
    assert finance.issue_voucher(conn, MANAGER, 1, 20, "Học viên thân thiết")["phan_tram"] == 20


# ---------------------------------------------------------------- học vụ
def test_transfer_free_only_once_and_same_course(conn):
    rows = conn.execute(
        """SELECT a.id AS a, b.id AS b FROM lop_hoc a JOIN lop_hoc b ON a.khoa_hoc_id = b.khoa_hoc_id AND a.id < b.id
           WHERE a.trang_thai = 'sap_khai_giang' AND b.trang_thai = 'sap_khai_giang' LIMIT 1"""
    ).fetchone()
    if not rows:
        pytest.skip("cần 2 lớp cùng khoá")
    conn.execute("UPDATE lop_hoc SET si_so_toi_da = 60 WHERE id = ANY(%s)", ([rows["a"], rows["b"]],))
    inv = enrollment.enroll(conn, CONSULTANT, _new_student(conn), rows["a"])
    enrollment.transfer(conn, ACADEMIC, inv["don_hang_id"], rows["b"])
    with pytest.raises(RuleViolation, match="1 lần"):
        enrollment.transfer(conn, ACADEMIC, inv["don_hang_id"], rows["a"])


def test_reservation_once_max_six_months(conn):
    dh = conn.execute(
        "SELECT d.id FROM don_hang d WHERE d.trang_thai_hoc = 'dang_hoc'"
        " AND NOT EXISTS (SELECT 1 FROM bao_luu b WHERE b.don_hang_id = d.id) LIMIT 1"
    ).fetchone()["id"]
    with pytest.raises(RuleViolation, match="6 tháng"):
        enrollment.reserve(conn, ACADEMIC, dh, 7, "Đi công tác")
    assert enrollment.reserve(conn, ACADEMIC, dh, 3, "Đi công tác")["phi"] == 300_000
    with pytest.raises(RuleViolation):
        enrollment.reserve(conn, ACADEMIC, dh, 1, "Lần nữa")


def test_room_or_teacher_double_booking_rejected(conn):
    cls = conn.execute(
        "SELECT * FROM lop_hoc WHERE trang_thai = 'dang_hoc' AND giang_vien_id IS NOT NULL LIMIT 1"
    ).fetchone()
    data = {
        "khoa_hoc_id": cls["khoa_hoc_id"],
        "ngay_khai_giang": date.today() + timedelta(days=2),
        "ca_hoc": cls["ca_hoc"],
        "lich_hoc": cls["lich_hoc"],
        "hinh_thuc": "online",
        "si_so_toi_da": 20,
        "si_so_toi_thieu": 5,
        "giang_vien_id": cls["giang_vien_id"],
        "phong_hoc_id": None,
    }
    last = conn.execute("SELECT max(ngay) AS d FROM buoi_hoc WHERE lop_hoc_id = %s", (cls["id"],)).fetchone()["d"]
    if last is None or last <= date.today() + timedelta(days=3):
        pytest.skip("lớp sắp kết thúc")
    with pytest.raises(RuleViolation, match="Trùng lịch"):
        training.create_class(conn, ACADEMIC, data)


def test_teacher_marks_only_own_class(conn):
    own = conn.execute(
        """SELECT b.id FROM buoi_hoc b JOIN lop_hoc l ON l.id = b.lop_hoc_id JOIN giang_vien g ON g.id = l.giang_vien_id
           WHERE g.username = 'giangvien' AND b.ngay <= current_date ORDER BY b.ngay DESC LIMIT 1"""
    ).fetchone()
    other = conn.execute(
        """SELECT b.id FROM buoi_hoc b JOIN lop_hoc l ON l.id = b.lop_hoc_id JOIN giang_vien g ON g.id = l.giang_vien_id
           WHERE g.username IS DISTINCT FROM 'giangvien' AND b.ngay <= current_date LIMIT 1"""
    ).fetchone()
    gv = conn.execute("SELECT id FROM giang_vien WHERE username = 'giangvien'").fetchone()["id"]
    teacher = Actor("giangvien", "teacher", giang_vien_id=gv)
    with pytest.raises(Forbidden):
        enrollment.mark_attendance(conn, teacher, other["id"], [])
    roster = enrollment.session_roster(conn, teacher, own["id"])["hoc_vien"]
    if roster:
        enrollment.mark_attendance(
            conn, teacher, own["id"], [{"don_hang_id": r["don_hang_id"], "trang_thai": "co_mat"} for r in roster]
        )


def test_agent_can_never_write_grades(conn):
    dh = conn.execute("SELECT id FROM don_hang WHERE trang_thai_hoc = 'dang_hoc' LIMIT 1").fetchone()["id"]
    with pytest.raises(Forbidden, match="sửa điểm"):
        enrollment.set_grade(conn, agent_actor("cham_soc", "academic"), dh, "giua_khoa", 90)


# ---------------------------------------------------------------- CRM & cổng học viên
def test_lead_lifecycle_and_reason_required(conn):
    lead = crm.create_lead(
        conn,
        MANAGER,
        {"ho_ten": "Khách Test", "so_dien_thoai": "0911222333", "nguon": "zalo", "email": "khach.test@example.com"},
    )
    assert lead["phu_trach"]  # tự phân người phụ trách
    with pytest.raises(RuleViolation):
        crm.transition(conn, CONSULTANT, lead["id"], "hen_hoc_thu")
    with pytest.raises(RuleViolation, match="lý do"):
        crm.transition(conn, CONSULTANT, lead["id"], "khong_tiep_tuc")
    assert crm.log_contact(conn, CONSULTANT, lead["id"], "Đã gọi")["trang_thai"] == "da_lien_he"


def test_student_portal_only_shows_own_data(conn):
    me = Actor("hocvien", "student", hoc_vien_id=1)
    assert students.portal_overview(conn, me)["hoc_vien"]["id"] == 1
    other = conn.execute("SELECT id FROM don_hang WHERE hoc_vien_id <> 1 LIMIT 1").fetchone()["id"]
    with pytest.raises(Forbidden):
        students.submit_request(conn, me, "hoan_phi", "Cho em hoàn tiền", other)
    with pytest.raises(Forbidden):
        finance.get_invoice(conn, me, other)


# ---------------------------------------------------------------- hộp duyệt & mức tự chủ
def test_forbidden_action_cannot_be_submitted(conn):
    with pytest.raises(Forbidden, match="mức Cấm"):
        proposals.submit(conn, agent_actor("x", "manager"), "ghi_nhan_thanh_toan", "t", "s", {})


def test_l1_proposal_waits_then_executes_on_approval_with_audit(conn, mails):
    p = proposals.submit(
        conn,
        Actor("tuvan", "consultant", is_agent=True),
        "cap_voucher",
        "Voucher",
        "s",
        {"hoc_vien_id": 1, "ho_ten": "A", "phan_tram": 10, "ly_do": "Thân thiết", "so_ngay": 30},
    )
    assert p["trang_thai"] == "cho_duyet"
    done = proposals.approve(conn, CONSULTANT, p["id"], {"phan_tram": 12})
    assert done["trang_thai"] == "da_thuc_hien" and done["da_sua"]
    assert conn.execute("SELECT phan_tram FROM voucher ORDER BY id DESC LIMIT 1").fetchone()["phan_tram"] == 12
    trail = conn.execute("SELECT hanh_dong, duyet_boi FROM audit_log WHERE de_xuat_id = %s", (p["id"],)).fetchall()
    assert any(t["hanh_dong"] == "cap_voucher" and t["duyet_boi"] == "tuvan" for t in trail)


def test_executor_still_bound_by_role_limits(conn):
    """Người duyệt là quản lý, nhưng đề xuất do tư vấn viên ra lệnh -> thực thi với hạn mức 15% của tư vấn viên."""
    p = proposals.submit(
        conn,
        Actor("tuvan", "consultant", is_agent=True),
        "cap_voucher",
        "V",
        "s",
        {"hoc_vien_id": 1, "ho_ten": "A", "phan_tram": 10, "ly_do": "x", "so_ngay": 30},
    )
    out = proposals.approve(conn, MANAGER, p["id"], {"phan_tram": 25})
    assert out["trang_thai"] == "that_bai" and "15%" in out["ket_qua"]


def test_wrong_role_cannot_approve(conn):
    p = proposals.submit(
        conn,
        Actor("tuvan", "consultant", is_agent=True),
        "cap_voucher",
        "V",
        "s",
        {"hoc_vien_id": 1, "ho_ten": "A", "phan_tram": 5, "ly_do": "x", "so_ngay": 30},
    )
    with pytest.raises(Forbidden):
        proposals.approve(conn, ACADEMIC, p["id"])


def test_l2_daily_limit_falls_back_to_approval(conn, mails):
    conn.execute("UPDATE chinh_sach_tu_chu SET muc = 'L2', han_muc_ngay = 1 WHERE loai_hanh_dong = 'tao_viec_nhac'")
    me = agent_actor("tuyen_sinh", "consultant")
    item = {"khach_id": 1, "moc": "t", "ho_ten": "A", "phu_trach": "tuvan", "ly_do": "x"}
    first = proposals.submit(conn, me, "tao_viec_nhac", "a", "s", {"items": [item]})
    second = proposals.submit(conn, me, "tao_viec_nhac", "b", "s", {"items": [{**item, "khach_id": 2}]})
    assert first["trang_thai"] == "da_thuc_hien" and second["trang_thai"] == "cho_duyet"
    assert "Vượt hạn mức" in second["tom_tat"]


def test_agent_cannot_change_autonomy(conn):
    with pytest.raises(Forbidden):
        proposals.update_policy(conn, agent_actor("x", "manager"), "cap_voucher", "L2", 10)


def test_dedupe_key_prevents_repeating_a_proposal(conn):
    me = agent_actor("giao_vu", "academic")
    data = {"lop_hoc_id": 1, "ma_lop": "X", "si_so": 1, "toi_thieu": 8}
    assert proposals.submit(conn, me, "canh_bao_lop_thieu", "t", "s", data, dedupe_key="k1")
    assert proposals.submit(conn, me, "canh_bao_lop_thieu", "t", "s", data, dedupe_key="k1") is None


# ---------------------------------------------------------------- agent nền
def test_debt_agent_is_idempotent_and_never_mails_twice(conn, mails):
    first = run_agent("cong_no", "test", conn=conn)
    sent = len(mails)
    second = run_agent("cong_no", "test", conn=conn)
    assert first["de_xuat"] + first["tu_dong"] > 0
    assert second["de_xuat"] == 0 and second["tu_dong"] == 0 and len(mails) == sent
    recipients = [m.to for m in mails]
    assert len(recipients) == len(set(recipients))


def test_paid_students_are_skipped_at_execution_time(conn, mails):
    run_agent("cong_no", "test", conn=conn)
    p = conn.execute(
        "SELECT * FROM de_xuat_agent WHERE loai_hanh_dong IN ('nhac_no_tiep', 'tam_dung_hoc') AND trang_thai = 'cho_duyet'"
        " ORDER BY id LIMIT 1"
    ).fetchone()
    if p is None:
        pytest.skip("không có đề xuất chờ duyệt")
    dot_ids = [i["dot_id"] for i in p["du_lieu"].get("items", [])] or [p["du_lieu"]["dot_id"]]
    conn.execute("UPDATE dot_thanh_toan SET trang_thai = 'da_thanh_toan' WHERE id = ANY(%s)", (dot_ids,))
    out = proposals.approve(conn, ACCOUNTANT, p["id"])
    assert out["trang_thai"] == "da_thuc_hien"
    assert "đã đóng" in out["ket_qua"] or "Đã gửi 0" in out["ket_qua"]


def test_all_background_agents_run(conn, mails):
    for name in ["cong_no", "tuyen_sinh", "giao_vu", "cham_soc", "bao_cao"]:
        assert "loi" not in run_agent(name, "test", conn=conn)


def test_partial_payment_lowers_installment_amount_used_by_reminders(conn):
    """Lỗi từng gặp: đợt đã đóng một nửa vẫn bị nhắc với số tiền gốc của đợt."""
    inv = _fresh_invoice(conn)
    finance.record_payment(conn, ACCOUNTANT, inv["don_hang_id"], 1_000_000, "tien_mat")
    dot = next(d for d in finance.open_installments(conn) if d["don_hang_id"] == inv["don_hang_id"])
    assert dot["so_tien"] == inv["thanh_tien"] - 1_000_000
    assert dot["so_tien_goc"] == inv["thanh_tien"]
