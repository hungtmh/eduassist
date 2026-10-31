"""Debug: in các bước supervisor đã làm trong thread gần nhất của một user.

uv run python scripts/inspect_thread.py nhanvien
"""

import sys

from eduassist.agents.persistence import langgraph_pool
from eduassist.agents.supervisor import build_supervisor

user = sys.argv[1] if len(sys.argv) > 1 else "nhanvien"
role = {"hocvien": "student", "quanly": "manager"}.get(user, "staff")
with langgraph_pool().connection() as c:
    tid = c.execute(
        "SELECT thread_id FROM checkpoints WHERE thread_id LIKE %s AND checkpoint_ns = '' "
        "ORDER BY checkpoint_id DESC LIMIT 1",
        (f"{user}:%",),
    ).fetchone()["thread_id"]
print("thread", tid)
state = build_supervisor(role).get_state({"configurable": {"thread_id": tid}})
for m in state.values["messages"]:
    if m.type == "ai" and m.tool_calls:
        for tc in m.tool_calls:
            print("CALL  ", tc["name"], str(tc["args"])[:400])
    elif m.type == "tool":
        print("RESULT", m.content[:800].replace("\n", " / "))
    else:
        print(m.type.upper().ljust(6), str(m.content)[:300].replace("\n", " / "))
    print("-" * 80)
