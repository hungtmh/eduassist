"""Chạy SQL đã qua kiểm tra bằng role agent_ro và định dạng kết quả gọn cho LLM đọc."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import psycopg

from eduassist.config import get_settings
from eduassist.db import ro_pool
from eduassist.security.sql_guard import validate_and_limit

AGENT_READABLE_TABLES = {"khoa_hoc", "lop_hoc", "hoc_vien", "don_hang", "thanh_toan", "voucher"}
MAX_ROWS_SHOWN_TO_LLM = 40


@dataclass
class QueryResult:
    sql: str
    columns: list[str]
    rows: list[tuple]

    def to_markdown(self) -> str:
        if not self.rows:
            return "(0 dòng)"
        shown = self.rows[:MAX_ROWS_SHOWN_TO_LLM]
        lines = ["| " + " | ".join(self.columns) + " |", "|" + "---|" * len(self.columns)]
        lines += ["| " + " | ".join(_fmt(v) for v in r) + " |" for r in shown]
        if len(self.rows) > len(shown):
            lines.append(f"... (còn {len(self.rows) - len(shown)} dòng, tổng {len(self.rows)} dòng)")
        return "\n".join(lines)


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, Decimal):
        return f"{v:,.0f}" if v == v.to_integral_value() else f"{v:,.2f}"
    if isinstance(v, int) and abs(v) >= 10_000:
        return f"{v:,}"
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return str(v).replace("|", "/").replace("\n", " ")


def run_readonly(query: str) -> QueryResult:
    """Kiểm tra (raise SQLRejected) rồi chạy. Lỗi từ Postgres raise psycopg.Error."""
    s = get_settings()
    safe_sql = validate_and_limit(query, AGENT_READABLE_TABLES, s.sql_row_limit)
    # Role đã đặt mặc định read-only + timeout; đặt lại ở đây để không phụ thuộc cấu hình DB
    with ro_pool().connection() as conn, conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        conn.execute(f"SET LOCAL statement_timeout = {int(s.sql_timeout_ms)}")
        cur = conn.cursor(row_factory=psycopg.rows.tuple_row)
        cur.execute(safe_sql)
        columns = [d.name for d in cur.description] if cur.description else []
        rows = cur.fetchall()
    return QueryResult(sql=safe_sql, columns=columns, rows=rows)
