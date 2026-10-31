"""Checkpointer (state hội thoại theo thread) + Store (bộ nhớ dài hạn theo user) trên Postgres."""

from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from eduassist.config import get_settings


@lru_cache
def langgraph_pool() -> ConnectionPool:
    # LangGraph yêu cầu autocommit + dict_row; prepare_threshold=0 tránh lỗi prepared statement khi dùng pool
    return ConnectionPool(
        get_settings().database_url,
        min_size=1,
        max_size=10,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
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
