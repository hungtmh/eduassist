"""Schema nền tảng: 6 vai trò, đào tạo, học vụ, tài chính, CRM, thông báo, tầng agentic, audit.

Revision ID: 0002
Revises: 0001
"""

from pathlib import Path

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parents[2] / "sql" / "002_platform.sql"


def upgrade() -> None:
    # SQL thô qua psycopg (xem 0001_prototype.py để biết lý do)
    op.get_bind().connection.driver_connection.execute(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    raise NotImplementedError("Downgrade không được hỗ trợ cho dữ liệu nghiệp vụ")
