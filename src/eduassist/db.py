"""Connection pool cho 2 vai trò database.

- app_pool : user app_rw - ứng dụng đọc/ghi (auth, voucher, log, vector...).
- ro_pool  : user agent_ro - CHỈ dùng cho câu SQL do LLM sinh ra. Database tự chặn mọi lệnh ghi,
             kể cả khi lớp kiểm tra sqlglot bị vượt qua.
"""
from functools import lru_cache

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from eduassist.config import get_settings


def _configure(conn) -> None:
    from pgvector.psycopg import register_vector

    register_vector(conn)


@lru_cache
def app_pool() -> ConnectionPool:
    return ConnectionPool(
        get_settings().database_url,
        min_size=1,
        max_size=10,
        kwargs={"row_factory": dict_row, "autocommit": True},
        configure=_configure,
        open=True,
    )


@lru_cache
def ro_pool() -> ConnectionPool:
    return ConnectionPool(
        get_settings().agent_ro_url,
        min_size=1,
        max_size=5,
        kwargs={"row_factory": dict_row, "autocommit": True},
        open=True,
    )
