"""Tài khoản production (khoá tạm, thu hồi phiên, đặt lại mật khẩu) và khoá học ngừng bán.

Revision ID: 0004
Revises: 0003
"""

from pathlib import Path

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parents[2] / "sql" / "004_accounts.sql"


def upgrade() -> None:
    op.get_bind().connection.driver_connection.execute(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("ALTER TABLE khoa_hoc DROP COLUMN IF EXISTS dang_mo_ban")
    op.execute("DROP TABLE IF EXISTS password_reset")
    op.execute("DROP INDEX IF EXISTS app_user_email_uidx")
    op.execute("DROP INDEX IF EXISTS app_user_hoc_vien_uidx")
    for col in (
        "token_version",
        "must_change_password",
        "failed_logins",
        "locked_until",
        "last_login_at",
        "password_changed_at",
        "created_at",
    ):
        op.execute(f"ALTER TABLE app_user DROP COLUMN IF EXISTS {col}")
