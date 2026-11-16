"""Web công khai: nội dung trang khoá học, hồ sơ giảng viên công khai, sự đồng ý của khách.

Revision ID: 0005
Revises: 0004
"""

from pathlib import Path

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parents[2] / "sql" / "005_public_site.sql"


def upgrade() -> None:
    op.get_bind().connection.driver_connection.execute(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS khoa_hoc_slug_uidx")
    for col in ("slug", "mo_ta_ngan", "doi_tuong", "ket_qua", "lo_trinh"):
        op.execute(f"ALTER TABLE khoa_hoc DROP COLUMN IF EXISTS {col}")
    for col in ("tieu_su", "hien_thi_cong_khai"):
        op.execute(f"ALTER TABLE giang_vien DROP COLUMN IF EXISTS {col}")
    for col in ("dong_y_luc", "kenh_chi_tiet"):
        op.execute(f"ALTER TABLE khach_tiem_nang DROP COLUMN IF EXISTS {col}")
