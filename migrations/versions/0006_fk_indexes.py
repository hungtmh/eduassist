"""Index cho khoá ngoại và cột lọc thường dùng (phát hiện khi test tải).

Revision ID: 0006
Revises: 0005
"""

from pathlib import Path

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parents[2] / "sql" / "006_fk_indexes.sql"


def upgrade() -> None:
    op.get_bind().connection.driver_connection.execute(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    for line in SQL.read_text(encoding="utf-8").splitlines():
        if line.startswith("CREATE INDEX IF NOT EXISTS "):
            op.execute(f"DROP INDEX IF EXISTS {line.split()[5]}")
