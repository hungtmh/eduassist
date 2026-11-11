"""Test tích hợp với Postgres thật: lớp an toàn (3) ở chính database phải chặn được
ngay cả khi lớp kiểm tra sqlglot bị bỏ qua.  Chạy: uv run pytest -m integration"""

import psycopg
import pytest

from eduassist.config import get_settings
from eduassist.security.sql_guard import SQLRejected
from eduassist.security.sql_runner import run_readonly

pytestmark = pytest.mark.integration


@pytest.fixture
def ro_conn():
    with psycopg.connect(get_settings().agent_ro_url, autocommit=True) as conn:
        yield conn


@pytest.mark.parametrize(
    "stmt",
    [
        "DELETE FROM hoc_vien",
        "UPDATE don_hang SET trang_thai = 'da_thanh_toan'",
        "INSERT INTO voucher (ma, hoc_vien_id, phan_tram, ly_do, han_su_dung, created_by)"
        " VALUES ('X', 1, 10, 'x', current_date, 'x')",
        "DROP TABLE khoa_hoc",
    ],
)
def test_agent_role_cannot_write_even_without_guard(ro_conn, stmt):
    # Gọi THẲNG database, bỏ qua sqlglot: role agent_ro vẫn phải bị từ chối
    with pytest.raises(psycopg.Error):
        ro_conn.execute(stmt)


@pytest.mark.parametrize("table", ["app_user", "query_log", "feedback", "email_log"])
def test_agent_role_cannot_read_app_tables(ro_conn, table):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        ro_conn.execute(f"SELECT * FROM {table} LIMIT 1")


def test_agent_role_has_statement_timeout(ro_conn):
    with pytest.raises(psycopg.errors.QueryCanceled):
        ro_conn.execute("SET statement_timeout = '200ms'")
        ro_conn.execute("SELECT count(*) FROM generate_series(1, 100000000)")


def test_runner_reads_business_data():
    result = run_readonly("SELECT count(*) AS n FROM khoa_hoc")
    assert result.rows[0][0] > 0
    assert result.sql.endswith("LIMIT 200")


def test_runner_blocks_before_database():
    with pytest.raises(SQLRejected):
        run_readonly("SELECT * FROM app_user")


def test_reminders_skip_students_mailed_in_last_24h():
    """Chống gửi trùng nằm ở tầng Service: LLM/agent gọi lại bao nhiêu lần, mỗi người chỉ nhận 1 email / 24 giờ."""
    from psycopg.rows import dict_row

    from eduassist.agents.action import find_debtors
    from eduassist.services.core import Actor
    from eduassist.services.notifications import capture_mail, recently_sent, send_student_emails

    box = []
    capture_mail(box)
    with (
        psycopg.connect(get_settings().database_url, row_factory=dict_row, autocommit=True) as conn,
        conn.transaction(force_rollback=True),
    ):
        conn.execute("TRUNCATE email_log")  # rollback cuối test
        hv = find_debtors(conn)[0]["hoc_vien_id"]
        me = Actor("ketoan", "accountant")
        first = send_student_emails(conn, me, "nhac_no", {hv: ("a", "b")})
        again = send_student_emails(conn, me, "nhac_no", {hv: ("a", "b")})
        assert first.sent == [hv] and again.sent == [] and again.skipped_recent == [hv]
        assert recently_sent(conn, "nhac_no", [hv]) == {hv}
    assert len(box) == 1
