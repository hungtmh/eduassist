"""Chat với EduAssist ngay trên terminal (không cần chạy API).

uv run eduassist-chat --user nhanvien                         # chat tương tác
uv run eduassist-chat --user hocvien -q "Có cho trả góp không?" # hỏi 1 câu
"""

import argparse
import sys
import uuid

from eduassist.agents.context import UserContext
from eduassist.chat import stream_turn
from eduassist.db import app_pool

STEP_LABEL = {
    "agent_start": lambda e: f"→ {e['agent']}: {e['task'][:90]}",
    "agent_end": lambda e: f"✓ {e['agent']} xong",
    "sql": lambda e: (
        f"  SQL [{e['status']}] {e.get('sql', '')[:110]}" + (f"  ({e['error']})" if e.get("error") else "")
    ),
    "retrieval": lambda e: f"  tra tài liệu: {e['query']}",
    "courses": lambda e: "  tra danh sách khoá học",
    "action": lambda e: f"  thực hiện: {e['action']}",
    "memory": lambda e: f"  ghi nhớ: {e['fact']}",
    "sources": lambda e: f"  nguồn đã kiểm chứng: {len(e['items'])}",
}


def load_context(username: str, thread: str) -> UserContext:
    with app_pool().connection() as conn:
        u = conn.execute(
            "SELECT username, role, display_name, hoc_vien_id FROM app_user WHERE username = %s", (username,)
        ).fetchone()
    if u is None:
        sys.exit(f"Không có tài khoản '{username}'. Chạy: uv run eduassist-setup")
    return UserContext(
        user_id=u["username"],
        role=u["role"],
        display_name=u["display_name"],
        hoc_vien_id=u["hoc_vien_id"],
        run_id=str(uuid.uuid4()),
        thread_id=f"{u['username']}:{thread}",
    )


def run_turn(ctx: UserContext, message: str | None = None, resume: list[dict] | None = None) -> None:
    for ev in stream_turn(ctx, message=message, resume=resume):
        if ev["type"] == "step":
            print(f"\n\033[2m{_step_text(ev)}\033[0m", flush=True)
        elif ev["type"] == "token":
            print(ev["text"], end="", flush=True)
        elif ev["type"] == "interrupt":
            decisions = []
            for a in ev["actions"]:
                print(f"\n⚠️  Cần duyệt: {a['name']}")
                for k, v in a["args"].items():
                    print(f"     {k}: {v}")
                ok = _clean(input("   Duyệt? (y/n): ")).lower() == "y"
                decisions.append({"type": "approve"} if ok else {"type": "reject", "message": "Người dùng từ chối."})
            run_turn(ctx, resume=decisions)
            return
        elif ev["type"] == "done" and ev["sources"]:
            print("\n\nNguồn:\n" + "\n".join(f"  - {src}" for src in ev["sources"]))
        elif ev["type"] == "error":
            print(f"\n[LỖI] {ev['message']}")
    print()


def _clean(text: str) -> str:
    # PowerShell pipe có thể chèn BOM vào đầu input
    return text.strip().lstrip("\N{ZERO WIDTH NO-BREAK SPACE}")


def _step_text(ev: dict) -> str:
    return STEP_LABEL[ev["step"]](ev) if ev.get("step") in STEP_LABEL else str(ev)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--user", default="nhanvien")
    p.add_argument("--thread", default=None, help="tiếp tục một thread cũ")
    p.add_argument("-q", "--question")
    args = p.parse_args()
    ctx = load_context(args.user, args.thread or uuid.uuid4().hex[:8])
    print(f"[{ctx.display_name} · {ctx.role} · thread {ctx.thread_id}]")
    if args.question:
        run_turn(ctx, args.question)
        return
    while True:
        try:
            q = _clean(input("\nBạn: "))
        except EOFError:
            break
        if q.lower() in {"exit", "quit", "q"}:
            break
        if q:
            print("EduAssist: ", end="")
            run_turn(ctx, q)


if __name__ == "__main__":
    main()
