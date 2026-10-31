"""Smoke test API thật (cần API đang chạy + Groq key). In ra luồng sự kiện SSE.

uv run python scripts/smoke_api.py "câu hỏi" --user nhanvien [--approve y,n] [--like]
"""

import argparse
import json
import os

import httpx

API = os.environ.get("API_URL", "http://localhost:8000")


def stream(client: httpx.Client, path: str, body: dict) -> list[tuple[str, dict]]:
    events = []
    with client.stream("POST", path, json=body, timeout=300) as r:
        if r.status_code != 200:
            r.read()
            print("HTTP", r.status_code, r.text)
            return events
        event = None
        for line in r.iter_lines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
                events.append((event, data))
                if event == "token":
                    print(data["text"], end="", flush=True)
                elif event == "step":
                    detail = {k: v for k, v in data.items() if k not in ("type", "step")}
                    print(f"\n  · {data.get('step')}: {str(detail)[:140]}")
                elif event in ("interrupt", "error", "meta"):
                    print(f"\n[{event}] {data}")
                elif event == "done":
                    print(f"\n[done] sources={data.get('sources')}")
    return events


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("question")
    p.add_argument("--user", default="nhanvien")
    p.add_argument("--approve", default="", help="danh sách y/n cho các thao tác chờ duyệt")
    p.add_argument("--like", action="store_true")
    a = p.parse_args()
    with httpx.Client(base_url=API) as c:
        token = c.post("/auth/login", json={"username": a.user, "password": "demo123"}).json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        events = stream(c, "/chat", {"message": a.question})
        meta = events[0][1]
        answers = iter(a.approve.split(",")) if a.approve else iter(())
        while events and events[-1][0] == "interrupt":
            decisions = [
                {"type": "approve"}
                if next(answers, "n").strip() == "y"
                else {"type": "reject", "message": "Không duyệt"}
                for _ in events[-1][1]["actions"]
            ]
            print(f"\n>>> resume với {decisions}")
            body = {"conversation_id": meta["conversation_id"], "run_id": meta["run_id"], "decisions": decisions}
            events = stream(c, "/chat/resume", body)
        if a.like:
            body = {"conversation_id": meta["conversation_id"], "run_id": meta["run_id"], "score": 1}
            print("\n[feedback]", c.post("/feedback", json=body).json())


if __name__ == "__main__":
    main()
