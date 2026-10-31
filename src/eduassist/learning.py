"""Vòng học liên tục (data flywheel) - học ở lớp bao quanh model, KHÔNG fine-tune.

1. Người dùng bấm Like/Dislike -> lưu bảng feedback (+ gửi lên Langfuse nếu bật).
2. NHÂN VIÊN bấm Like cho câu trả lời có chạy SQL -> câu (hỏi, SQL) được đưa vào kho ví dụ few-shot.
   Lần sau gặp câu hỏi tương tự, Analytics agent thấy ví dụ đã được xác nhận -> SQL đúng hơn.
   Chỉ nhận xác nhận từ nhân viên: học viên không thấy SQL nên không đánh giá được, và để tránh bị "đầu độc".
3. Báo cáo định kỳ (scripts/feedback_report.py): câu bị Dislike, câu "không tìm thấy trong tài liệu"
   -> nhân viên bổ sung tài liệu.
"""

import logging

from eduassist.agents.context import UserContext
from eduassist.db import app_pool
from eduassist.observability import record_feedback as send_to_langfuse
from eduassist.rag.store import add_sql_example

log = logging.getLogger("eduassist.learning")


def record_feedback(ctx: UserContext, run_id: str, score: int, comment: str | None = None) -> dict:
    with app_pool().connection() as conn:
        conn.execute(
            """INSERT INTO feedback (run_id, thread_id, user_id, role, score, comment)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (run_id, user_id) DO UPDATE SET score = EXCLUDED.score, comment = EXCLUDED.comment""",
            (run_id, ctx.thread_id, ctx.user_id, ctx.role, score, comment),
        )
    send_to_langfuse(run_id, score, comment)

    promoted = []
    if score == 1 and ctx.is_staff:
        promoted = promote_sql_examples(ctx, run_id)
    return {"saved": True, "promoted_sql_examples": promoted}


def promote_sql_examples(ctx: UserContext, run_id: str) -> list[str]:
    """Lấy câu SQL chạy THÀNH CÔNG CUỐI CÙNG cho mỗi câu hỏi trong lượt này (bỏ các lần thử lỗi trước đó)."""
    with app_pool().connection() as conn:
        rows = conn.execute(
            """SELECT DISTINCT ON (question) question, sql_text
               FROM query_log
               WHERE run_id = %s AND user_id = %s AND ok AND row_count > 0
               ORDER BY question, created_at DESC""",
            (run_id, ctx.user_id),
        ).fetchall()
    added = []
    for r in rows:
        if add_sql_example(r["question"], r["sql_text"], source="feedback", created_by=ctx.user_id):
            added.append(r["question"])
            log.info("flywheel: thêm ví dụ SQL từ feedback của %s: %s", ctx.user_id, r["question"][:80])
    return added
