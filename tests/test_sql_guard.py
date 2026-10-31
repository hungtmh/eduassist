import pytest

from eduassist.security.sql_guard import SQLRejected, validate_and_limit

ALLOWED = {"khoa_hoc", "lop_hoc", "hoc_vien", "don_hang", "thanh_toan", "voucher"}


def check(q: str, limit: int = 200) -> str:
    return validate_and_limit(q, ALLOWED, limit)


@pytest.mark.parametrize(
    "q",
    [
        "SELECT * FROM khoa_hoc",
        "select ten, hoc_phi from khoa_hoc where hoc_phi > 5000000 order by hoc_phi desc;",
        "WITH t AS (SELECT don_hang_id, sum(so_tien) s FROM thanh_toan GROUP BY 1) SELECT * FROM t",
        "SELECT kh.ten, count(*) FROM don_hang dh JOIN lop_hoc lh ON lh.id = dh.lop_hoc_id "
        "JOIN khoa_hoc kh ON kh.id = lh.khoa_hoc_id GROUP BY 1",
        "SELECT ma FROM khoa_hoc UNION SELECT ma_lop FROM lop_hoc",
        "SELECT date_trunc('month', ngay_dat) AS m, count(*) FROM don_hang GROUP BY 1",
        "SELECT * FROM public.hoc_vien",
    ],
)
def test_allows_safe_queries(q):
    assert "LIMIT" in check(q).upper()


@pytest.mark.parametrize(
    "q, reason",
    [
        ("DELETE FROM khoa_hoc", "SELECT"),
        ("UPDATE don_hang SET trang_thai = 'da_thanh_toan'", "SELECT"),
        ("DROP TABLE hoc_vien", "SELECT"),
        ("INSERT INTO voucher (ma) VALUES ('x')", "SELECT"),
        ("SELECT 1; DROP TABLE hoc_vien", "MỘT"),
        ("SELECT * INTO bang_moi FROM hoc_vien", "INTO"),
        ("SELECT * FROM hoc_vien FOR UPDATE", "FOR UPDATE"),
        ("SELECT * FROM app_user", "app_user"),
        ("SELECT * FROM query_log", "query_log"),
        ("SELECT * FROM pg_catalog.pg_user", "schema"),
        ("SELECT * FROM information_schema.tables", "schema"),
        ("SELECT pg_sleep(30)", "pg_sleep"),
        ("SELECT pg_read_file('/etc/passwd')", "pg_read_file"),
        ("SELECT current_setting('is_superuser')", "current_setting"),
        ("COPY hoc_vien TO STDOUT", "SELECT"),
        ("SELECT * FROM khoa_hoc WHERE id IN (SELECT hoc_vien_id FROM app_user)", "app_user"),
        ("", "rỗng"),
        ("SELEC * FRM khoa_hoc", ""),
    ],
)
def test_rejects_dangerous_queries(q, reason):
    with pytest.raises(SQLRejected, match=reason or None):
        check(q)


def test_cte_name_is_not_treated_as_table():
    out = check("WITH app_user AS (SELECT * FROM khoa_hoc) SELECT * FROM app_user")
    assert "khoa_hoc" in out


def test_adds_limit_when_missing():
    assert check("SELECT * FROM khoa_hoc", 50).endswith("LIMIT 50")


def test_keeps_smaller_limit():
    assert check("SELECT * FROM khoa_hoc LIMIT 5", 50).endswith("LIMIT 5")


def test_caps_larger_limit():
    assert check("SELECT * FROM khoa_hoc LIMIT 100000", 50).endswith("LIMIT 50")


def test_union_is_wrapped_with_limit():
    out = check("SELECT ma FROM khoa_hoc UNION SELECT ma_lop FROM lop_hoc", 10)
    assert out.upper().startswith("SELECT * FROM (") and out.endswith("LIMIT 10")
