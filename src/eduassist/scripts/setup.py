"""Khởi tạo database: migration (Alembic), role read-only, dữ liệu giả lập, tài khoản demo, bảng LangGraph, vector.

uv run eduassist-setup            # idempotent: chỉ seed khi DB trống hoặc chưa có dữ liệu nền tảng
uv run eduassist-setup --reset    # xoá & seed lại toàn bộ dữ liệu nghiệp vụ (theo ngày hôm nay)
"""

import argparse
import logging
from datetime import date
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from eduassist.config import get_settings
from eduassist.security.passwords import hash_password
from eduassist.security.sql_runner import AGENT_READABLE_TABLES
from eduassist.seed.generate import DEMO_USERS, generate
from eduassist.seed.platform import seed_platform

log = logging.getLogger("eduassist.setup")
ROOT = Path(__file__).resolve().parents[3]

# Thứ tự TRUNCATE không quan trọng nhờ CASCADE; liệt kê đủ để --reset sạch mọi dữ liệu nghiệp vụ + agent
BUSINESS_TABLES = [
    "audit_log",
    "de_xuat_agent",
    "lan_chay_agent",
    "outbox_su_kien",
    "thong_bao",
    "viec_can_lam",
    "lich_hen",
    "khach_tiem_nang",
    "yeu_cau",
    "hoan_phi",
    "bao_luu",
    "diem_so",
    "diem_danh",
    "dot_thanh_toan",
    "buoi_hoc",
    "email_log",
    "thanh_toan",
    "don_hang",
    "voucher",
    "giang_vien",
    "app_user",
    "hoc_vien",
    "lop_hoc",
    "phong_hoc",
    "co_so",
    "khoa_hoc",
    "chinh_sach_tu_chu",
]


def migrate() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(cfg, "head")
    log.info("migration ok (alembic head)")


def ensure_readonly_role(conn: psycopg.Connection) -> None:
    pw = get_settings().agent_ro_password.get_secret_value()
    exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = 'agent_ro'").fetchone()
    stmt = "ALTER ROLE agent_ro WITH LOGIN PASSWORD {}" if exists else "CREATE ROLE agent_ro WITH LOGIN PASSWORD {}"
    conn.execute(sql.SQL(stmt).format(sql.Literal(pw)))
    conn.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM agent_ro")
    conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO agent_ro").format(sql.Identifier(conn.info.dbname)))
    conn.execute("GRANT USAGE ON SCHEMA public TO agent_ro")
    tables = sorted(AGENT_READABLE_TABLES)
    conn.execute(
        sql.SQL("GRANT SELECT ON {} TO agent_ro").format(sql.SQL(", ").join(sql.Identifier(t) for t in tables))
    )
    # Lớp phòng thủ ở chính database: mọi transaction của agent_ro mặc định read-only + có timeout
    conn.execute("ALTER ROLE agent_ro SET default_transaction_read_only = on")
    conn.execute(
        sql.SQL("ALTER ROLE agent_ro SET statement_timeout = {}").format(
            sql.Literal(f"{get_settings().sql_timeout_ms}ms")
        )
    )
    log.info("role agent_ro ok (SELECT trên: %s)", ", ".join(tables))


def _needs_seed(conn) -> bool:
    has_base = conn.execute("SELECT count(*) AS n FROM khoa_hoc").fetchone()["n"] > 0
    has_platform = conn.execute("SELECT count(*) AS n FROM co_so").fetchone()["n"] > 0
    return not (has_base and has_platform)


def seed(conn: psycopg.Connection, reset: bool) -> None:
    if not reset and not _needs_seed(conn):
        log.info("đã có dữ liệu - bỏ qua seed (dùng --reset để seed lại)")
        return
    today = date.today()
    with conn.transaction():
        conn.execute("TRUNCATE " + ", ".join(BUSINESS_TABLES) + " RESTART IDENTITY CASCADE")
        ds = generate(today)
        for table in ["khoa_hoc", "lop_hoc", "hoc_vien", "don_hang", "thanh_toan"]:
            rows = getattr(ds, table)
            cols = list(rows[0].keys())
            with (
                conn.cursor() as cur,
                cur.copy(
                    sql.SQL("COPY {} ({}) FROM STDIN").format(
                        sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, cols))
                    )
                ) as copy,
            ):
                for r in rows:
                    copy.write_row([r[c] for c in cols])
            conn.execute(
                sql.SQL("SELECT setval(pg_get_serial_sequence({}, 'id'), (SELECT max(id) FROM {}))").format(
                    sql.Literal(table), sql.Identifier(table)
                )
            )
            log.info("seed %-16s %6d dòng", table, len(rows))
        for username, password, role, display, hv_id in DEMO_USERS:
            conn.execute(
                "INSERT INTO app_user (username, password_hash, role, display_name, hoc_vien_id, email)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                (username, hash_password(password), role, display, hv_id, f"{username}@anhduong.example"),
            )
        stats = seed_platform(conn, today)
        for k, v in stats.items():
            log.info("seed %-16s %s", k, v)
        _link_demo_accounts(conn)
    log.info("tài khoản demo: %s (mật khẩu demo123)", ", ".join(u[0] for u in DEMO_USERS))


def _link_demo_accounts(conn) -> None:
    """Giảng viên demo dạy lớp đang học; học viên demo có một lớp đang học, trả góp, đợt 2 sắp tới hạn."""
    conn.execute(
        """UPDATE giang_vien SET username = 'giangvien' WHERE id = (
               SELECT giang_vien_id FROM lop_hoc WHERE trang_thai = 'dang_hoc' GROUP BY giang_vien_id
               ORDER BY count(*) DESC, giang_vien_id LIMIT 1)"""
    )
    has_active = conn.execute("SELECT 1 FROM don_hang WHERE hoc_vien_id = 1 AND trang_thai_hoc = 'dang_hoc'").fetchone()
    if not has_active:
        conn.execute(
            """UPDATE don_hang SET hoc_vien_id = 1 WHERE id = (
                   SELECT d.id FROM don_hang d JOIN dot_thanh_toan x ON x.don_hang_id = d.id
                   WHERE d.trang_thai_hoc = 'dang_hoc' AND d.tra_gop AND x.trang_thai = 'chua_thanh_toan'
                     AND NOT EXISTS (SELECT 1 FROM don_hang o WHERE o.hoc_vien_id = 1 AND o.lop_hoc_id = d.lop_hoc_id)
                   ORDER BY x.han_thanh_toan LIMIT 1)"""
        )


def setup_langgraph() -> None:
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.store.postgres import PostgresStore

    url = get_settings().database_url
    with PostgresSaver.from_conn_string(url) as saver:
        saver.setup()
    with PostgresStore.from_conn_string(url) as store:
        store.setup()
    log.info("bảng checkpointer + store của LangGraph ok")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="xoá & seed lại dữ liệu nghiệp vụ")
    parser.add_argument("--skip-ingest", action="store_true", help="không tạo embedding cho tài liệu / ví dụ SQL")
    args = parser.parse_args()

    migrate()
    with psycopg.connect(get_settings().database_url, autocommit=True, row_factory=dict_row) as conn:
        ensure_readonly_role(conn)
        seed(conn, args.reset)
        from eduassist.services.proposals import ensure_default_policies

        ensure_default_policies(conn)
    setup_langgraph()
    if not args.skip_ingest:
        from eduassist.rag.ingest import ingest_all

        ingest_all()


if __name__ == "__main__":
    main()
