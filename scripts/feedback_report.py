"""Báo cáo vòng học liên tục (chạy định kỳ, VD mỗi tuần).

    uv run python scripts/feedback_report.py --days 7

- Tỷ lệ Like/Dislike theo vai trò
- Ví dụ SQL học được từ feedback của nhân viên
- Câu hỏi agent tư vấn KHÔNG tìm thấy trong tài liệu -> danh sách việc cần bổ sung tài liệu
- Câu SQL bị lớp an toàn chặn (dấu hiệu prompt injection hoặc prompt chưa tốt)
"""

import argparse

from eduassist.db import app_pool


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=7)
    days = p.parse_args().days
    with app_pool().connection() as conn:
        fb = conn.execute(
            """SELECT role, count(*) FILTER (WHERE score = 1) AS likes, count(*) FILTER (WHERE score = -1) AS dislikes
               FROM feedback WHERE created_at > now() - make_interval(days => %s) GROUP BY role""",
            (days,),
        ).fetchall()
        learned = conn.execute(
            """SELECT question, created_by, created_at::date AS ngay FROM sql_examples
               WHERE source = 'feedback' AND created_at > now() - make_interval(days => %s) ORDER BY created_at""",
            (days,),
        ).fetchall()
        gaps = conn.execute(
            """SELECT question, count(*) AS n FROM knowledge_gap
               WHERE created_at > now() - make_interval(days => %s) AND user_id NOT LIKE 'eval-%%'
               GROUP BY question ORDER BY n DESC LIMIT 20""",
            (days,),
        ).fetchall()
        blocked = conn.execute(
            """SELECT error, count(*) AS n FROM query_log
               WHERE NOT ok AND error LIKE 'rejected:%%' AND created_at > now() - make_interval(days => %s)
               GROUP BY error ORDER BY n DESC LIMIT 10""",
            (days,),
        ).fetchall()

    print(f"=== BÁO CÁO {days} NGÀY GẦN NHẤT ===\n")
    print("Phản hồi người dùng:")
    for r in fb or [{"role": "(chưa có)", "likes": 0, "dislikes": 0}]:
        print(f"  {r['role']:<8} 👍 {r['likes']}   👎 {r['dislikes']}")
    print(f"\nVí dụ SQL học được từ feedback ({len(learned)}):")
    for r in learned:
        print(f"  + [{r['ngay']}] {r['question']}  (xác nhận bởi {r['created_by']})")
    print(f"\nCâu hỏi chưa có trong tài liệu - cần bổ sung ({len(gaps)}):")
    for r in gaps:
        print(f"  ? ({r['n']} lần) {r['question']}")
    print(f"\nSQL bị lớp an toàn chặn ({sum(r['n'] for r in blocked)}):")
    for r in blocked:
        print(f"  ! ({r['n']} lần) {r['error'][:120]}")


if __name__ == "__main__":
    main()
