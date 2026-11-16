"""Alembic env: migration viết bằng SQL thuần (op.execute), không dùng ORM metadata."""

from alembic import context
from sqlalchemy import create_engine, pool

from eduassist.config import get_settings


def _url() -> str:
    url = get_settings().database_url
    # SQLAlchemy cần chỉ rõ driver psycopg 3
    return url.replace("postgresql://", "postgresql+psycopg://", 1) if url.startswith("postgresql://") else url


def run_offline() -> None:
    context.configure(url=_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    # Migration có thể tạo index trên bảng lớn: tắt timeout mặc định của role ứng dụng cho phiên này
    engine = create_engine(
        _url(),
        poolclass=pool.NullPool,
        connect_args={"options": "-c statement_timeout=0 -c lock_timeout=0 -c idle_in_transaction_session_timeout=0"},
    )
    with engine.connect() as conn:
        context.configure(connection=conn, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
