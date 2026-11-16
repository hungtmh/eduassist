"""Web công khai, trang Hôm nay, thời khoá biểu với Postgres thật. Mỗi test rollback.

Chạy: uv run pytest -m integration
"""

from datetime import timedelta

import psycopg
import pytest
from psycopg.rows import dict_row

from eduassist.config import get_settings
from eduassist.services import public, training, workday
from eduassist.services.core import Actor, Forbidden, NotFound, RuleViolation, today

pytestmark = pytest.mark.integration

MANAGER = Actor("quanly", "manager")
ACADEMIC = Actor("giaovu", "academic")


@pytest.fixture
def conn():
    get_settings.cache_clear()
    with (
        psycopg.connect(get_settings().database_url, row_factory=dict_row, autocommit=True) as c,
        c.transaction(force_rollback=True),
    ):
        yield c


LEAD = {"ho_ten": "Trần  Thị   Web", "so_dien_thoai": "090 999 8877", "dong_y": True, "trang": "/khoa-hoc/eng-if"}


# ---------------------------------------------------------------- dữ liệu công khai
def test_public_course_hides_private_fields(conn):
    d = public.course_detail(conn, public.list_courses(conn)[0]["slug"])
    flat = str(d)
    assert "@" not in flat  # không lộ email giảng viên
    for lop in d["lop_sap_mo"]:
        assert set(lop) >= {"ma_lop", "ngay_khai_giang", "cho_trong"} and lop["cho_trong"] >= 0


def test_stopped_course_not_public(conn):
    c = public.list_courses(conn)[0]
    training.update_course(conn, MANAGER, c["id"], {"dang_mo_ban": False})
    assert c["slug"] not in {x["slug"] for x in public.list_courses(conn)}
    with pytest.raises(NotFound):
        public.course_detail(conn, c["slug"])


def test_hidden_teacher_not_public(conn):
    gv = conn.execute("SELECT id, ho_ten, email, chuyen_mon FROM giang_vien LIMIT 1").fetchone()
    training.save_teacher(conn, ACADEMIC, gv["id"], gv["ho_ten"], gv["email"], gv["chuyen_mon"], None, False)
    names = {t["ho_ten"] for t in public.center(conn)["giang_vien"]}
    assert gv["ho_ten"] not in names
    assert all(lop["giang_vien"] != gv["ho_ten"] for lop in public.schedule(conn))


def test_policies_readable():
    ps = public.policies()
    assert ps and all(p["slug"] and p["tieu_de"] for p in ps)
    assert "##" in public.policy(ps[0]["slug"])["noi_dung"]
    with pytest.raises(NotFound):
        public.policy("../../etc/passwd")


# ---------------------------------------------------------------- form tư vấn
def test_lead_form_creates_lead_and_event(conn):
    slug = public.list_courses(conn)[0]["slug"]
    public.submit_lead(conn, {**LEAD, "khoa_slug": slug, "nhu_cau": "Muốn học buổi tối"})
    k = conn.execute("SELECT * FROM khach_tiem_nang WHERE so_dien_thoai = '0909998877'").fetchone()
    assert k["ho_ten"] == "Trần Thị Web" and k["nguon"] == "website" and k["dong_y_luc"] is not None
    assert k["khoa_quan_tam_id"] is not None and k["kenh_chi_tiet"] == "form:/khoa-hoc/eng-if"
    assert k["phu_trach"] is not None
    ev = conn.execute(
        "SELECT 1 FROM outbox_su_kien WHERE loai = 'lead.created' AND (payload->>'khach_id')::int = %s", (k["id"],)
    ).fetchone()
    assert ev, "agent tuyển sinh phải được kích hoạt"
    assert conn.execute("SELECT 1 FROM thong_bao WHERE lien_ket = %s", (f"/leads/{k['id']}",)).fetchone()


def test_lead_form_dedupes_same_phone(conn):
    public.submit_lead(conn, {**LEAD, "nhu_cau": "IELTS"})
    public.submit_lead(conn, {**LEAD, "so_dien_thoai": "+84 909 998 877", "nhu_cau": "Thêm TOEIC"})
    rows = conn.execute("SELECT nhu_cau FROM khach_tiem_nang WHERE so_dien_thoai = '0909998877'").fetchall()
    assert len(rows) == 1 and "IELTS" in rows[0]["nhu_cau"] and "TOEIC" in rows[0]["nhu_cau"]


@pytest.mark.parametrize(
    "patch",
    [
        {"dong_y": False},
        {"so_dien_thoai": "12345"},
        {"so_dien_thoai": "0123456789"},  # đầu số không tồn tại
        {"ho_ten": "A1"},
        {"email": "khong-phai-email"},
    ],
)
def test_lead_form_validation(conn, patch):
    with pytest.raises(RuleViolation):
        public.submit_lead(conn, {**LEAD, **patch})


# ---------------------------------------------------------------- hôm nay & thời khoá biểu
def test_my_day_sections_per_role(conn):
    assert "tai_chinh" in workday.my_day(conn, Actor("ketoan", "accountant"))
    assert "tuyen_sinh" in workday.my_day(conn, Actor("tuvan", "consultant"))
    assert "giao_vu" in workday.my_day(conn, ACADEMIC)
    assert "tai_chinh" not in workday.my_day(conn, Actor("tuvan", "consultant"))
    with pytest.raises(Forbidden):
        workday.my_day(conn, Actor("hocvien", "student", hoc_vien_id=1))


def test_teacher_schedule_only_own_classes(conn):
    gv = conn.execute("SELECT id FROM giang_vien WHERE username = 'giangvien'").fetchone()
    if gv is None:
        pytest.skip("chưa có giảng viên demo")
    t = today()
    other = conn.execute("SELECT id FROM giang_vien WHERE id <> %s LIMIT 1", (gv["id"],)).fetchone()["id"]
    rows = workday.schedule(
        conn, Actor("giangvien", "teacher", giang_vien_id=gv["id"]), t, t + timedelta(days=13), other
    )
    assert all(r["giang_vien_id"] == gv["id"] for r in rows)  # tham số giảng viên khác bị bỏ qua


def test_schedule_range_limit(conn):
    t = today()
    with pytest.raises(RuleViolation):
        workday.schedule(conn, ACADEMIC, t, t + timedelta(days=60))
    with pytest.raises(RuleViolation):
        workday.schedule(conn, ACADEMIC, t, t - timedelta(days=1))
    week = workday.schedule(conn, ACADEMIC, t, t + timedelta(days=6))
    assert all(t <= r["ngay"] <= t + timedelta(days=6) for r in week)
