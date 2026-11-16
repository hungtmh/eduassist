"""Connection pool cho các vai trò database.

- app_pool  : user app_rw - nghiệp vụ đọc/ghi (voucher, log, vector...).
- auth_pool : user app_rw - CHỈ dùng để kiểm tra đăng nhập ở đầu mỗi request. Tách riêng vì một request
              giữ 1 kết nối app_pool (dependency `db`) rồi mới kiểm tra đăng nhập: nếu cùng pool, khi tải cao
              mọi kết nối đều bị request giữ để chờ kết nối thứ hai -> deadlock (đã gặp khi test tải ~100 req/s).
- ro_pool   : user agent_ro - CHỈ dùng cho câu SQL do LLM sinh ra. Database tự chặn mọi lệnh ghi,
              kể cả khi lớp kiểm tra sqlglot bị vượt qua.

- read_pool : chỉ đọc cho trang công khai / báo cáo. Có DATABASE_READ_URL (bản sao đọc) thì đọc từ đó, không thì
              dùng chung app_pool.

Mọi pool đều có hạn chờ (db_pool_timeout): hết kết nối thì báo PoolTimeout -> API trả 503, không treo.

Đi qua PgBouncer (DB_VIA_PGBOUNCER=true, chế độ transaction): không gửi tham số phiên lúc mở kết nối (PgBouncer không
chuyển tiếp `options`) - statement_timeout, lock_timeout và idle_in_transaction_session_timeout khi đó do setup đặt bằng
ALTER ROLE. Prepared statement vẫn dùng được nhờ PgBouncer >= 1.21 (max_prepared_statements, deploy/pgbouncer):
đo trên máy 2 vCPU, tắt prepared statement làm Postgres tốn thêm khoảng 30% CPU để phân tích lại từng câu.
PgBouncer cũ hơn thì đặt DB_PGBOUNCER_PREPARED=false.
"""

from functools import lru_cache

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from eduassist.config import get_settings


def _configure(conn) -> None:
    from pgvector.psycopg import register_vector

    register_vector(conn)


def session_options() -> str:
    """Tham số phiên của kết nối ứng dụng (cũng là giá trị setup đặt bằng ALTER ROLE)."""
    s = get_settings()
    return (
        f"-c statement_timeout={int(s.db_statement_timeout_ms)} "
        f"-c lock_timeout={int(s.db_lock_timeout_ms)} "
        f"-c idle_in_transaction_session_timeout={int(s.db_idle_in_transaction_timeout_ms)}"
    )


def pool_kwargs(**extra) -> dict:
    """Tham số kết nối dùng chung cho mọi pool của ứng dụng (kể cả pool của LangGraph)."""
    kw: dict = {"autocommit": True, **extra}
    if get_settings().db_via_pgbouncer and not get_settings().db_pgbouncer_prepared:
        kw["prepare_threshold"] = None
    return kw


def _app_kwargs() -> dict:
    # statement_timeout: câu SQL nào chạy quá lâu thì Postgres huỷ, kết nối được trả lại pool.
    # idle_in_transaction_session_timeout: code treo giữa transaction thì Postgres đóng phiên, nhả khoá dòng.
    kw = pool_kwargs(row_factory=dict_row)
    if not get_settings().db_via_pgbouncer:
        kw["options"] = session_options()
    return kw


@lru_cache
def app_pool() -> ConnectionPool:
    s = get_settings()
    return ConnectionPool(
        s.database_url,
        min_size=1,
        max_size=s.db_pool_size,
        timeout=s.db_pool_timeout,
        kwargs=_app_kwargs(),
        configure=_configure,
        open=True,
        name="app",
    )


@lru_cache
def auth_pool() -> ConnectionPool:
    s = get_settings()
    return ConnectionPool(
        s.database_url,
        min_size=1,
        max_size=s.db_auth_pool_size,
        timeout=s.db_pool_timeout,
        kwargs=_app_kwargs(),
        open=True,
        name="auth",
    )


@lru_cache
def ro_pool() -> ConnectionPool:
    s = get_settings()
    return ConnectionPool(
        s.agent_ro_url,
        min_size=1,
        max_size=5,
        timeout=s.db_pool_timeout,
        kwargs=pool_kwargs(row_factory=dict_row),
        open=True,
        name="agent_ro",
    )


@lru_cache
def read_pool() -> ConnectionPool:
    s = get_settings()
    if not s.database_read_url:
        return app_pool()
    return ConnectionPool(
        s.database_read_url,
        min_size=1,
        max_size=s.db_pool_size,
        timeout=s.db_pool_timeout,
        kwargs=_app_kwargs(),
        configure=_configure,
        open=True,
        name="read",
    )


def all_pools() -> dict[str, ConnectionPool]:
    """Các pool đã mở trong tiến trình này (cho /metrics), không tự mở pool mới."""
    out = {}
    for name, fn in (("app", app_pool), ("auth", auth_pool), ("agent_ro", ro_pool), ("read", read_pool)):
        if fn.cache_info().currsize:
            out[name] = fn()
    return out
