"""Schema của prototype (sql/schema.sql, idempotent - chạy được trên DB đã có sẵn từ prototype).

Revision ID: 0001
Revises:
"""

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"


def run_sql_file(name: str) -> None:
    """Chạy file SQL thô bằng kết nối psycopg bên dưới (trong cùng transaction của Alembic).
    Không qua text() của SQLAlchemy để ':' và '%' trong COMMENT/SQL không bị hiểu nhầm là tham số."""
    op.get_bind().connection.driver_connection.execute((SQL_DIR / name).read_text(encoding="utf-8"))


def upgrade() -> None:
    run_sql_file("schema.sql")


def downgrade() -> None:
    raise NotImplementedError("Không hỗ trợ hạ về trước schema gốc")
