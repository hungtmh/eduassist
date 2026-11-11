"""Analytics agent: trả lời câu hỏi số liệu bằng Text-to-SQL an toàn.

Lớp (4) của Text-to-SQL nằm ở đây: SQL bị từ chối / lỗi -> trả thông báo lỗi về cho LLM tự sửa,
tối đa vài lần (ToolCallLimitMiddleware) để không lặp vô tận.
"""

from functools import lru_cache

import psycopg
from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, ToolCallLimitMiddleware, dynamic_prompt
from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from eduassist.agents.context import UserContext, emit
from eduassist.db import app_pool
from eduassist.llm import chat_model, resilience_middleware
from eduassist.rag.store import similar_sql_examples
from eduassist.security.sql_guard import SQLRejected
from eduassist.security.sql_runner import AGENT_READABLE_TABLES, run_readonly
from eduassist.services.core import today

MAX_SQL_ATTEMPTS = 4

PROMPT = """Bạn là chuyên viên phân tích dữ liệu của Trung tâm Đào tạo Ánh Dương.
Nhiệm vụ: trả lời câu hỏi số liệu bằng cách viết SQL (PostgreSQL) rồi gọi tool run_sql.

SCHEMA (chỉ được dùng các bảng/cột này):
{schema}

QUY TẮC NGHIỆP VỤ:
- Hôm nay là {today}. Dùng current_date / date_trunc cho mốc thời gian tương đối ("tháng này", "quý trước").
- Doanh thu / tiền đã thu = SUM(thanh_toan.so_tien), hoàn tiền là số âm. KHÔNG tính doanh thu bằng don_hang.thanh_tien.
- Công nợ của một đơn = don_hang.thanh_tien - tổng thanh_toan.so_tien của đơn đó,
  chỉ xét đơn có trang_thai IN ('chua_thanh_toan', 'thanh_toan_mot_phan').
- Đếm lượt đăng ký thì loại đơn trang_thai = 'da_huy', trừ khi câu hỏi nói khác.
- Học viên ĐANG HỌC = don_hang.trang_thai_hoc = 'dang_hoc'. Nợ QUÁ HẠN = dot_thanh_toan.trang_thai = 'qua_han'.
- Chuyên cần: diem_danh nối buoi_hoc; 'di_tre' tính nửa buổi. Khách tiềm năng / tỉ lệ chuyển đổi: khach_tiem_nang.
- Tìm theo tên người/khoá học dùng ILIKE '%...%'.

CÁCH LÀM:
- Viết MỘT câu SELECT, gọi run_sql. Nếu run_sql trả về "LỖI", đọc lỗi, sửa SQL và chạy lại.
- Mọi con số trong câu trả lời PHẢI lấy từ kết quả run_sql. Không đoán, không bịa.
- Nếu câu hỏi không trả lời được bằng dữ liệu hiện có, nói rõ là không có dữ liệu.

TRẢ LỜI bằng tiếng Việt, gồm: 1-2 câu kết luận; bảng markdown kết quả (tối đa 15 dòng, ghi chú nếu bị cắt);
cuối cùng là câu SQL đã chạy thành công trong khối ```sql```."""


@lru_cache
def schema_description() -> str:
    """Sinh mô tả schema từ information_schema + COMMENT trong sql/schema.sql (luôn khớp DB thật)."""
    with app_pool().connection() as conn:
        rows = conn.execute(
            """
            SELECT c.table_name, c.column_name, c.data_type,
                   col_description(format('public.%%I', c.table_name)::regclass, c.ordinal_position) AS col_comment,
                   obj_description(format('public.%%I', c.table_name)::regclass) AS table_comment
            FROM information_schema.columns c
            WHERE c.table_schema = 'public' AND c.table_name = ANY(%s)
            ORDER BY c.table_name, c.ordinal_position
            """,
            (sorted(AGENT_READABLE_TABLES),),
        ).fetchall()
    lines, current = [], None
    for r in rows:
        if r["table_name"] != current:
            current = r["table_name"]
            lines.append(f"\n{current}" + (f"  -- {r['table_comment']}" if r["table_comment"] else ""))
        comment = f"  -- {r['col_comment']}" if r["col_comment"] else ""
        lines.append(f"  {r['column_name']} {r['data_type']}{comment}")
    return "\n".join(lines).strip()


def _log_query(ctx: UserContext | None, question: str, sql_text: str, ok: bool, error: str | None, rows: int | None):
    if ctx is None:
        return
    with app_pool().connection() as conn:
        conn.execute(
            """INSERT INTO query_log (run_id, thread_id, user_id, question, sql_text, ok, error, row_count)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (ctx.run_id, ctx.thread_id, ctx.user_id, question, sql_text, ok, error, rows),
        )


@tool
def run_sql(query: str, runtime: ToolRuntime[UserContext]) -> str:
    """Chạy MỘT câu SELECT (PostgreSQL) trên dữ liệu trung tâm và trả về bảng kết quả.
    Chỉ đọc dữ liệu; câu lệnh ghi/xoá sẽ bị từ chối."""
    question = runtime.state["messages"][0].content if runtime.state.get("messages") else ""
    question = question.split("CÂU HỎI:")[-1].strip()
    emit("sql", status="running", sql=query)
    try:
        result = run_readonly(query)
    except SQLRejected as e:
        _log_query(runtime.context, question, query, False, f"rejected: {e}", None)
        emit("sql", status="rejected", sql=query, error=str(e))
        return f"LỖI (bị chặn bởi lớp kiểm tra an toàn): {e}\nHãy viết lại một câu SELECT hợp lệ."
    except psycopg.Error as e:
        msg = (e.diag.message_primary if e.diag and e.diag.message_primary else str(e)).strip()
        _log_query(runtime.context, question, query, False, msg, None)
        emit("sql", status="error", sql=query, error=msg)
        return f"LỖI từ PostgreSQL: {msg}\nHãy sửa câu SQL và chạy lại."
    _log_query(runtime.context, question, result.sql, True, None, len(result.rows))
    emit("sql", status="ok", sql=result.sql, rows=len(result.rows))
    return f"SQL đã chạy: {result.sql}\nSố dòng: {len(result.rows)}\n\n{result.to_markdown()}"


@dynamic_prompt
def analytics_prompt(request: ModelRequest) -> str:
    # Tính lại mỗi lần gọi để "hôm nay" luôn đúng dù server chạy qua nhiều ngày
    return PROMPT.format(schema=schema_description(), today=today().isoformat())


def build_analytics_agent():
    return create_agent(
        chat_model(),
        tools=[run_sql],
        context_schema=UserContext,
        middleware=[
            analytics_prompt,
            *resilience_middleware(),
            ToolCallLimitMiddleware(tool_name="run_sql", run_limit=MAX_SQL_ATTEMPTS, exit_behavior="continue"),
        ],
        name="analytics",
    )


def task_with_examples(question: str) -> str:
    """Few-shot ĐỘNG: chèn các ví dụ (câu hỏi, SQL) gần nghĩa nhất từ kho ví dụ - kho này lớn dần nhờ feedback."""
    examples = similar_sql_examples(question, k=3)
    if not examples:
        return question
    shots = "\n\n".join(f"Câu hỏi: {e['question']}\nSQL: {e['sql_text']}" for e in examples)
    return f"VÍ DỤ THAM KHẢO (câu hỏi tương tự đã được xác nhận đúng):\n{shots}\n\nCÂU HỎI: {question}"
