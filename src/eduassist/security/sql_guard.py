"""Lớp kiểm tra SQL do LLM sinh ra, TRƯỚC khi gửi tới database.

Đây là lớp (1) và (2) trong 4 lớp an toàn của Text-to-SQL:
  (1) Phân tích cú pháp bằng sqlglot: đúng 1 câu lệnh, chỉ SELECT/WITH/UNION, chỉ đọc bảng trong allowlist,
      không SELECT INTO, không FOR UPDATE, không gọi hàm nguy hiểm.
  (2) Ép LIMIT để không kéo cả bảng về.
Lớp (3) là role agent_ro read-only ở chính Postgres - vẫn chặn được nếu lớp này có lỗ hổng.
Lớp (4) là cho LLM tự sửa khi bị từ chối (xử lý ở tool run_sql).
"""

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

# Hàm có thể gây hại / lộ thông tin hệ thống dù chỉ nằm trong SELECT
FORBIDDEN_FUNCTIONS = {
    "pg_sleep",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_stat_file",
    "lo_import",
    "lo_export",
    "dblink",
    "dblink_exec",
    "set_config",
    "current_setting",
    "pg_terminate_backend",
    "pg_cancel_backend",
    "pg_reload_conf",
    "query_to_xml",
    "pg_advisory_lock",
    "txid_current",
    "version",
}


class SQLRejected(ValueError):
    """SQL không qua được kiểm tra. Thông điệp được gửi lại cho LLM để nó tự sửa."""


def validate_and_limit(query: str, allowed_tables: set[str], row_limit: int) -> str:
    query = query.strip().rstrip(";").strip()
    if not query:
        raise SQLRejected("Câu SQL rỗng.")
    try:
        statements = [s for s in sqlglot.parse(query, read="postgres") if s is not None]
    except ParseError as e:
        raise SQLRejected(f"Lỗi cú pháp SQL: {e}") from e
    if len(statements) != 1:
        raise SQLRejected("Chỉ được chạy đúng MỘT câu lệnh SQL.")
    stmt = statements[0]

    if not isinstance(stmt, exp.Query):
        raise SQLRejected(f"Chỉ cho phép truy vấn đọc (SELECT). Nhận được: {type(stmt).__name__.upper()}.")
    for node in stmt.walk():
        if isinstance(node, exp.Into):
            raise SQLRejected("Không được dùng SELECT ... INTO.")
        if isinstance(node, exp.Lock):
            raise SQLRejected("Không được dùng FOR UPDATE / FOR SHARE.")
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Command)):
            raise SQLRejected("Không được ghi/sửa/xoá dữ liệu.")
        if isinstance(node, exp.Func):
            name = (node.name if isinstance(node, exp.Anonymous) else node.sql_name()).lower()
            if name in FORBIDDEN_FUNCTIONS:
                raise SQLRejected(f"Không được gọi hàm {name}().")

    cte_names = {cte.alias_or_name.lower() for cte in stmt.find_all(exp.CTE)}
    for table in stmt.find_all(exp.Table):
        name = table.name.lower()
        if not name:  # VD: SELECT * FROM generate_series(...) - không phải bảng
            continue
        if table.db and table.db.lower() != "public":
            raise SQLRejected(f"Không được truy cập schema '{table.db}'. Chỉ dùng các bảng nghiệp vụ.")
        if name not in cte_names and name not in allowed_tables:
            raise SQLRejected(
                f"Không được truy cập bảng '{name}'. Các bảng được phép: {', '.join(sorted(allowed_tables))}."
            )

    return _apply_limit(stmt, row_limit).sql(dialect="postgres")


def _apply_limit(stmt: exp.Query, row_limit: int) -> exp.Query:
    limit = stmt.args.get("limit")
    if isinstance(stmt, exp.Select):
        current = limit.expression if limit else None
        if isinstance(current, exp.Literal) and current.is_int and int(current.this) <= row_limit:
            return stmt
        return stmt.limit(row_limit)
    # UNION / INTERSECT...: bọc ngoài để LIMIT áp cho toàn bộ kết quả
    return exp.select("*").from_(stmt.subquery("q")).limit(row_limit)
