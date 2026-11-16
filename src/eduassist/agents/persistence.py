"""Checkpointer (state hội thoại theo thread) + Store (bộ nhớ dài hạn theo user) trên Postgres.

Hai bộ: đồng bộ (CLI, eval, đọc lịch sử hội thoại) và async (chat của API - eduassist.chat.astream_turn). Cả hai
đọc/ghi cùng các bảng, nên một hội thoại bắt đầu ở bộ này đọc tiếp được ở bộ kia.
"""

import asyncio
from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import PostgresStore
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, ConnectionPool

from eduassist.config import get_settings
from eduassist.db import pool_kwargs


def _kwargs() -> dict:
    # LangGraph yêu cầu autocommit + dict_row; prepare_threshold=0 tránh lỗi prepared statement khi dùng pool.
    # PgBouncer cũ không hỗ trợ prepared statement: pool_kwargs tắt hẳn (DB_PGBOUNCER_PREPARED=false).
    return pool_kwargs(prepare_threshold=0, row_factory=dict_row)


@lru_cache
def langgraph_pool() -> ConnectionPool:
    return ConnectionPool(
        get_settings().database_url,
        min_size=1,
        max_size=10,
        timeout=get_settings().db_pool_timeout,
        kwargs=_kwargs(),
        open=True,
    )


@lru_cache
def get_checkpointer() -> PostgresSaver:
    return PostgresSaver(langgraph_pool())


@lru_cache
def get_store() -> PostgresStore:
    return PostgresStore(langgraph_pool())


def memory_namespace(user_id: str) -> tuple[str, ...]:
    return ("users", user_id, "memories")


# ---------------------------------------------------------------- bản async (pool async phải mở trong event loop)
_async: dict = {}
_async_lock: asyncio.Lock | None = None


async def get_async_checkpointer() -> AsyncPostgresSaver:
    global _async_lock
    loop = asyncio.get_running_loop()
    if _async.get("loop") is loop:
        return _async["saver"]
    if _async_lock is None or _async.get("lock_loop") is not loop:
        _async_lock, _async["lock_loop"] = asyncio.Lock(), loop
    async with _async_lock:
        if _async.get("loop") is not loop:
            s = get_settings()
            pool = AsyncConnectionPool(
                s.database_url,
                min_size=1,
                max_size=s.db_async_pool_size,
                timeout=s.db_pool_timeout,
                kwargs=_kwargs(),
                open=False,
                name="langgraph_async",
            )
            await pool.open()
            _async.update(loop=loop, pool=pool, saver=AsyncPostgresSaver(pool))
    return _async["saver"]


async def close_async() -> None:
    pool = _async.pop("pool", None)
    _async.pop("loop", None)
    _async.pop("saver", None)
    if pool is not None:
        await pool.close()
