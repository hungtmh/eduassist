"""View dot_con_lai tính theo đơn (LATERAL) + index ngày thu tiền (phát hiện khi test tải trên dữ liệu lớn).

Revision ID: 0007
Revises: 0006
"""

from pathlib import Path

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

ROOT = Path(__file__).resolve().parents[2] / "sql"


def upgrade() -> None:
    op.get_bind().connection.driver_connection.execute((ROOT / "007_scale_queries.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS thanh_toan_ngay_idx")
    op.execute("DROP INDEX IF EXISTS don_hang_con_no_idx")
    # View cũ (cộng toàn bộ thanh_toan rồi ghép) - cùng kết quả
    op.get_bind().connection.driver_connection.execute(
        (ROOT / "003_installment_balance.sql").read_text(encoding="utf-8")
    )
