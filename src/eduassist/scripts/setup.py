"""Khởi tạo database: schema, role read-only, dữ liệu giả lập, tài khoản demo, bảng của LangGraph, vector.

    uv run eduassist-setup            # idempotent, chỉ seed khi DB trống
    uv run eduassist-setup --reset    # xoá dữ liệu nghiệp vụ & seed lại
"""
import argparse
import logging
from datetime import date
from pathlib import Path

import psycopg
from psycopg import sql

from eduassist.config import get_settings
from eduassist.security.passwords import hash_password
from eduassist.seed.generate import DEMO_USERS, generate

log = logging.getLogger("eduassist.setup")
ROOT = Path(__file__).resolve().parents[3]

# Bảng Analytics agent được phép SELECT. app_user, query_log, feedback... KHÔNG có ở đây.
AGENT_READABLE_TABLES = ["khoa_hoc", "lop_hoc", "hoc_vien", "don_hang", "thanh_toan", "voucher"]
BUSINESS_TABLES = ["thanh_toan", "don_hang", "voucher", "app_user", "hoc_vien", "lop_hoc", "khoa_hoc"]


def apply_schema(conn: psycopg.Connection) -> None:
    conn.execute((ROOT / "sql" / "schema.sql").read_text(encoding="utf-8"))
    log.info("schema ok")


def ensure_readonly_role(conn: psycopg.Connection) -> None:
    pw = get_settings().agent_ro_password.get_secret_value()
    exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = 'agent_ro'").fetchone()
    stmt = "ALTER ROLE agent_ro WITH LOGIN PASSWORD {}" if exists else "CREATE ROLE agent_ro WITH LOGIN PASSWORD {}"
    conn.execute(sql.SQL(stmt).format(sql.Literal(pw)))
    conn.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM agent_ro")
    conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO agent_ro").format(sql.Identifier(conn.info.dbname)))
    conn.execute("GRANT USAGE ON SCHEMA public TO agent_ro")
    conn.execute(sql.SQL("GRANT SELECT ON {} TO agent_ro").format(
        sql.SQL(", ").join(sql.Identifier(t) for t in AGENT_READABLE_TABLES)))
    # Lớp phòng thủ ở chính database: mọi transaction của agent_ro mặc định read-only + có timeout
    conn.execute("ALTER ROLE agent_ro SET default_transaction_read_only = on")
    conn.execute(sql.SQL("ALTER ROLE agent_ro SET statement_timeout = {}").format(
        sql.Literal(f"{get_settings().sql_timeout_ms}ms")))
    log.info("role agent_ro ok (SELECT trên: %s)", ", ".join(AGENT_READABLE_TABLES))


def seed(conn: psycopg.Connection, reset: bool) -> None:
    has_data = conn.execute("SELECT count(*) AS n FROM khoa_hoc").fetchone()[0] > 0
    if has_data and not reset:
        log.info("đã có dữ liệu - bỏ qua seed (dùng --reset để seed lại)")
        return
    conn.execute("TRUNCATE " + ", ".join(BUSINESS_TABLES) + " RESTART IDENTITY CASCADE")
    ds = generate(date.today())
    for table in ["khoa_hoc", "lop_hoc", "hoc_vien", "don_hang", "thanh_toan"]:
        rows = getattr(ds, table)
        cols = list(rows[0].keys())
        with conn.cursor() as cur:
            with cur.copy(sql.SQL("COPY {} ({}) FROM STDIN").format(
                    sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, cols)))) as copy:
                for r in rows:
                    copy.write_row([r[c] for c in cols])
        conn.execute(sql.SQL("SELECT setval(pg_get_serial_sequence({}, 'id'), (SELECT max(id) FROM {}))").format(
            sql.Literal(table), sql.Identifier(table)))
        log.info("seed %-10s %5d dòng", table, len(rows))
    for username, password, role, display, hv_id in DEMO_USERS:
        conn.execute(
            "INSERT INTO app_user (username, password_hash, role, display_name, hoc_vien_id) VALUES (%s, %s, %s, %s, %s)",
            (username, hash_password(password), role, display, hv_id),
        )
    log.info("tài khoản demo: %s (mật khẩu demo123)", ", ".join(u[0] for u in DEMO_USERS))


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

    with psycopg.connect(get_settings().database_url, autocommit=True) as conn:
        apply_schema(conn)
        ensure_readonly_role(conn)
        seed(conn, args.reset)
    setup_langgraph()
    if not args.skip_ingest:
        from eduassist.rag.ingest import ingest_all

        ingest_all()


if __name__ == "__main__":
    main()
