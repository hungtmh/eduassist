"""Tài khoản, khoá học, danh mục và phân trang với Postgres thật. Mỗi test rollback; email bị bắt lại.

Chạy: uv run pytest -m integration  (cần `uv run eduassist-setup` trước)
"""

import re
from urllib.parse import parse_qs, urlparse

import psycopg
import pytest
from psycopg.rows import dict_row

from eduassist.config import get_settings
from eduassist.services import accounts, crm, students, training
from eduassist.services.core import Actor, Conflict, Forbidden, RuleViolation
from eduassist.services.notifications import _capture, capture_mail

pytestmark = pytest.mark.integration

MANAGER = Actor("quanly", "manager")
CONSULTANT = Actor("tuvan", "consultant")
ACADEMIC = Actor("giaovu", "academic")
AGENT_MANAGER = Actor("agent:x", "manager", is_agent=True)


@pytest.fixture
def conn():
    get_settings.cache_clear()
    with (
        psycopg.connect(get_settings().database_url, row_factory=dict_row, autocommit=True) as c,
        c.transaction(force_rollback=True),
    ):
        yield c


@pytest.fixture
def mails():
    box = []
    token = capture_mail(box)
    yield box
    _capture.reset(token)


def _token_from(mail) -> str:
    url = re.search(r"https?://\S+/dat-mat-khau\?token=\S+", mail.body).group(0)
    return parse_qs(urlparse(url).query)["token"][0]


def _new_staff(conn, username="nv.test", role="consultant", email="nv.test@anhduong.example"):
    return accounts.create_staff_user(conn, MANAGER, username, "Nhân viên Test", role, email)


# ---------------------------------------------------------------- đăng nhập & khoá tạm
def test_login_locks_after_repeated_failures(conn):
    temp = _new_staff(conn)["mat_khau_tam"]
    max_fail = get_settings().login_max_failures
    for _ in range(max_fail - 1):
        assert accounts.login(conn, "nv.test", "sai-mat-khau-1") is None
    with pytest.raises(accounts.AccountLocked):
        accounts.login(conn, "nv.test", "sai-mat-khau-1")
    # đang khoá: mật khẩu đúng cũng bị từ chối
    with pytest.raises(accounts.AccountLocked):
        accounts.login(conn, "nv.test", temp)
    row = conn.execute("SELECT locked_until, failed_logins FROM app_user WHERE username = 'nv.test'").fetchone()
    assert row["locked_until"] is not None and row["failed_logins"] == 0
    assert conn.execute("SELECT 1 FROM audit_log WHERE hanh_dong = 'khoa_tam_dang_nhap'").fetchone()


def test_login_success_resets_failure_counter(conn):
    temp = _new_staff(conn)["mat_khau_tam"]
    accounts.login(conn, "nv.test", "sai-mat-khau-1")
    row = accounts.login(conn, "NV.Test ", temp)  # không phân biệt hoa thường, bỏ khoảng trắng
    assert row["username"] == "nv.test" and row["must_change_password"]
    assert (
        conn.execute("SELECT failed_logins FROM app_user WHERE username = 'nv.test'").fetchone()["failed_logins"] == 0
    )


def test_inactive_account_cannot_login(conn):
    temp = _new_staff(conn)["mat_khau_tam"]
    accounts.update_user(conn, MANAGER, "nv.test", active=False)
    assert accounts.login(conn, "nv.test", temp) is None


# ---------------------------------------------------------------- đổi / đặt lại mật khẩu
def test_change_password_bumps_token_version(conn):
    temp = _new_staff(conn)["mat_khau_tam"]
    before = accounts.load_account(conn, "nv.test")["token_version"]
    with pytest.raises(RuleViolation, match="hiện tại"):
        accounts.change_password(conn, "nv.test", "sai-roi-123", "Hoa-sen-2026")
    row = accounts.change_password(conn, "nv.test", temp, "Hoa-sen-2026")
    assert row["token_version"] == before + 1 and not row["must_change_password"]
    assert accounts.login(conn, "nv.test", "Hoa-sen-2026")


def test_reset_link_flow_single_use(conn, mails):
    _new_staff(conn)
    accounts.request_password_reset(conn, "NV.TEST@anhduong.example")
    assert len(mails) == 1 and mails[0].to == "nv.test@anhduong.example"
    token = _token_from(mails[0])
    # email_log không chứa link dùng được
    logged = conn.execute("SELECT body FROM email_log WHERE loai = 'tai_khoan_dat_lai' ORDER BY id DESC").fetchone()
    assert token not in logged["body"] and "[link đã ẩn]" in logged["body"]
    # DB chỉ lưu hash
    assert not conn.execute("SELECT 1 FROM password_reset WHERE token_hash = %s", (token,)).fetchone()
    assert accounts.check_link(conn, token)["username"] == "nv.test"
    accounts.reset_password(conn, token, "Mat-troi-99")
    assert accounts.login(conn, "nv.test", "Mat-troi-99")
    with pytest.raises(RuleViolation, match="hết hạn"):
        accounts.reset_password(conn, token, "Lan-thu-hai-1")


def test_reset_request_for_unknown_account_is_silent(conn, mails):
    accounts.request_password_reset(conn, "khong-ai-ca@nowhere.vn")
    assert mails == []


def test_expired_reset_link_rejected(conn, mails):
    _new_staff(conn)
    accounts.request_password_reset(conn, "nv.test")
    token = _token_from(mails[0])
    conn.execute("UPDATE password_reset SET expires_at = now() - interval '1 minute' WHERE username = 'nv.test'")
    with pytest.raises(RuleViolation):
        accounts.check_link(conn, token)


# ---------------------------------------------------------------- quản trị tài khoản
def test_only_manager_creates_users_and_agent_never_can(conn):
    with pytest.raises(Forbidden):
        accounts.create_staff_user(conn, CONSULTANT, "abc", "A", "consultant")
    with pytest.raises(Forbidden, match="Agent"):
        accounts.create_staff_user(conn, AGENT_MANAGER, "abc", "A", "consultant")


@pytest.mark.parametrize("username", ["ab", "Có Dấu", "a b c", "-bat-dau-gach"])
def test_bad_usernames_rejected(conn, username):
    with pytest.raises(RuleViolation):
        accounts.create_staff_user(conn, MANAGER, username, "A", "consultant")


def test_duplicate_username_or_email_rejected(conn):
    _new_staff(conn)
    with pytest.raises(Conflict):
        _new_staff(conn)
    with pytest.raises(Conflict):
        _new_staff(conn, username="khac", email="NV.TEST@anhduong.example")


def test_role_change_and_deactivation_revoke_sessions(conn):
    _new_staff(conn)
    v0 = accounts.load_account(conn, "nv.test")["token_version"]
    accounts.update_user(conn, MANAGER, "nv.test", display_name="Tên mới")
    assert accounts.load_account(conn, "nv.test")["token_version"] == v0  # đổi tên: không đăng xuất
    accounts.update_user(conn, MANAGER, "nv.test", role="accountant")
    assert accounts.load_account(conn, "nv.test")["token_version"] == v0 + 1


def test_manager_cannot_lock_self_and_last_manager_stays(conn):
    with pytest.raises(RuleViolation, match="tự khoá"):
        accounts.update_user(conn, MANAGER, "quanly", active=False)
    with pytest.raises(RuleViolation, match="tự khoá"):
        accounts.update_user(conn, MANAGER, "quanly", role="consultant")
    other = Actor("quanly2", "manager")
    _new_staff(conn, username="quanly2", role="manager", email="ql2@anhduong.example")
    conn.execute("UPDATE app_user SET active = false WHERE role = 'manager' AND username NOT IN ('quanly', 'quanly2')")
    accounts.update_user(conn, other, "quanly", active=False)  # còn quanly2
    with pytest.raises(RuleViolation, match="ít nhất một quản lý"):
        accounts.update_user(conn, MANAGER, "quanly2", active=False)


def test_staff_cannot_become_student(conn):
    _new_staff(conn)
    with pytest.raises(RuleViolation):
        accounts.update_user(conn, MANAGER, "nv.test", role="student")


def test_admin_reset_forces_change(conn):
    _new_staff(conn)
    temp = accounts.admin_reset_password(conn, MANAGER, "nv.test")["mat_khau_tam"]
    row = accounts.login(conn, "nv.test", temp)
    assert row["must_change_password"]


def test_teacher_account_links_profile(conn):
    gv = training.save_teacher(conn, ACADEMIC, None, "GV Kiểm Thử", "gv.kt@anhduong.example", "Tiếng Anh")
    res = accounts.create_staff_user(conn, MANAGER, "gv.kt", "GV Kiểm Thử", "teacher", None, gv["id"])
    assert res["user"]["giang_vien_id"] == gv["id"]
    with pytest.raises(Conflict):
        accounts.create_staff_user(conn, MANAGER, "gv.kt2", "GV", "teacher", None, gv["id"])


# ---------------------------------------------------------------- tài khoản học viên
def _student_without_account(conn) -> dict:
    row = conn.execute(
        """INSERT INTO hoc_vien (ho_ten, email, so_dien_thoai, nam_sinh, thanh_pho, nguon, ngay_dang_ky)
           VALUES ('Lê Thị Kiểm Thử', 'le.kiemthu@example.com', '0900000001', 2001, 'Hà Nội', 'website',
                   current_date) RETURNING *"""
    ).fetchone()
    return row


def test_student_account_sends_activation_link_not_password(conn, mails):
    hv = _student_without_account(conn)
    res = accounts.create_student_account(conn, CONSULTANT, hv["id"])
    assert res["user"]["username"] == "le.kiemthu" and res["da_gui_email"]
    assert len(mails) == 1 and res["mat_khau_tam"] not in mails[0].body
    token = _token_from(mails[0])
    assert accounts.check_link(conn, token)["muc_dich"] == "kich_hoat"
    accounts.reset_password(conn, token, "Hoc-vien-2026")
    row = accounts.login(conn, "le.kiemthu", "Hoc-vien-2026")
    assert row["hoc_vien_id"] == hv["id"] and not row["must_change_password"]
    with pytest.raises(Conflict):
        accounts.create_student_account(conn, CONSULTANT, hv["id"])
    page = students.list_students(conn, CONSULTANT, q=str(hv["id"]))
    assert page[0]["co_tai_khoan"] is True


def test_teacher_cannot_create_student_accounts(conn):
    hv = _student_without_account(conn)
    with pytest.raises(Forbidden):
        accounts.create_student_account(conn, Actor("giangvien", "teacher"), hv["id"])


# ---------------------------------------------------------------- khoá học & danh mục
COURSE = {
    "ma": "test-ielts-1",
    "ten": "IELTS kiểm thử",
    "danh_muc": "Tiếng Anh",
    "trinh_do": "Trung cấp",
    "hoc_phi": 6_000_000,
    "so_buoi": 24,
    "mo_ta": "Khoá học dùng cho kiểm thử tự động.",
}


def test_course_create_update_stop_selling(conn):
    with pytest.raises(Forbidden):
        training.create_course(conn, ACADEMIC, COURSE)
    c = training.create_course(conn, MANAGER, COURSE)
    assert c["ma"] == "TEST-IELTS-1" and c["dang_mo_ban"]
    with pytest.raises(Conflict):
        training.create_course(conn, MANAGER, COURSE)
    with pytest.raises(RuleViolation, match="Danh mục"):
        training.update_course(conn, MANAGER, c["id"], {"danh_muc": "Nấu ăn"})
    c = training.update_course(conn, MANAGER, c["id"], {"hoc_phi": 6_500_000, "dang_mo_ban": False})
    assert c["hoc_phi"] == 6_500_000 and not c["dang_mo_ban"]
    assert c["id"] not in {x["id"] for x in training.list_courses(conn, MANAGER, only_selling=True)}
    from datetime import date, timedelta

    with pytest.raises(RuleViolation, match="ngừng bán"):
        training.create_class(
            conn,
            ACADEMIC,
            {
                "khoa_hoc_id": c["id"],
                "ngay_khai_giang": date.today() + timedelta(days=20),
                "ca_hoc": "toi",
                "lich_hoc": "T2-T4-T6",
                "hinh_thuc": "online",
                "si_so_toi_da": 20,
                "si_so_toi_thieu": 5,
                "giang_vien_id": None,
                "phong_hoc_id": None,
            },
        )


def test_room_capacity_cannot_drop_below_class_size(conn):
    row = conn.execute(
        """SELECT ph.*, lh.si_so_toi_da FROM lop_hoc lh JOIN phong_hoc ph ON ph.id = lh.phong_hoc_id
           WHERE lh.trang_thai IN ('sap_khai_giang', 'dang_hoc') ORDER BY lh.si_so_toi_da DESC LIMIT 1"""
    ).fetchone()
    if row is None:
        pytest.skip("không có lớp offline đang mở")
    with pytest.raises(RuleViolation, match="sĩ số tối đa"):
        training.save_room(conn, ACADEMIC, row["id"], row["co_so_id"], row["ten"], row["si_so_toi_da"] - 1)


def test_branch_and_room_crud(conn):
    cs = training.save_branch(conn, MANAGER, None, "Cơ sở Kiểm thử", "1 Đường Thử, Quận 1")
    with pytest.raises(Conflict):
        training.save_branch(conn, MANAGER, None, "cơ sở kiểm thử", "khác")
    room = training.save_room(conn, ACADEMIC, None, cs["id"], "P.T1", 20)
    room = training.save_room(conn, ACADEMIC, room["id"], cs["id"], "P.T1", 25)
    assert room["suc_chua"] == 25
    with pytest.raises(Forbidden):
        training.save_branch(conn, ACADEMIC, None, "Không được", "Địa chỉ dài đủ")


# ---------------------------------------------------------------- phân trang
def test_pagination_total_and_pages_do_not_overlap(conn):
    total = conn.execute("SELECT count(*) AS n FROM khach_tiem_nang").fetchone()["n"]
    if total < 3:
        pytest.skip("cần ít nhất 3 khách")
    p1 = crm.list_leads(conn, CONSULTANT, limit=2, offset=0)
    p2 = crm.list_leads(conn, CONSULTANT, limit=2, offset=2)
    assert p1.total == p2.total == total
    assert len(p1) == 2 and not {r["id"] for r in p1} & {r["id"] for r in p2}
    beyond = crm.list_leads(conn, CONSULTANT, limit=2, offset=total + 10)
    assert list(beyond) == [] and beyond.total == total
    assert "_total" not in p1[0]


def test_lead_counts_cover_everything(conn):
    counts = crm.lead_counts(conn, CONSULTANT)
    assert counts["tong"] == conn.execute("SELECT count(*) AS n FROM khach_tiem_nang").fetchone()["n"]
