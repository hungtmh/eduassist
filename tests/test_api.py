"""Test API với backend giả: không gọi LLM, không cần database."""

import json

import pytest
from fastapi.testclient import TestClient

from eduassist.api import main
from eduassist.api.auth import AuthUser
from eduassist.api.ratelimit import RateLimiter

USERS = {
    "hocvien": AuthUser("hocvien", "student", "Học viên", 1),
    "nhanvien": AuthUser("nhanvien", "staff", "Nhân viên", None),
}


class FakeBackend:
    def __init__(self):
        self.calls = []
        self.pending: dict[str, list[dict]] = {}

    def authenticate(self, username, password):
        return USERS.get(username) if password == "demo123" else None

    def stream_turn(self, ctx, message=None, resume=None):
        self.calls.append({"ctx": ctx, "message": message, "resume": resume})
        yield {"type": "step", "step": "agent_start", "agent": "advisor", "task": message or ""}
        if message and "email" in message:
            self.pending[ctx.thread_id] = [{"name": "send_email", "args": {"recipients": ["a@example.com"]}}]
            yield {"type": "interrupt", "actions": self.pending[ctx.thread_id]}
            return
        self.pending.pop(ctx.thread_id, None)
        yield {"type": "token", "text": "Xin "}
        yield {"type": "token", "text": "chào"}
        yield {"type": "done", "answer": "Xin chào", "sources": []}

    def pending_actions(self, ctx):
        return self.pending.get(ctx.thread_id, [])

    def thread_history(self, ctx):
        return [{"role": "user", "content": f"thread={ctx.thread_id}"}]

    def record_feedback(self, ctx, run_id, score, comment):
        return {"saved": True, "promoted_sql_examples": ["q"] if ctx.is_staff and score == 1 else []}

    def healthcheck(self):
        return True


@pytest.fixture
def backend():
    return FakeBackend()


@pytest.fixture
def client(backend):
    main.app.dependency_overrides[main.get_backend] = lambda: backend
    main.app.dependency_overrides[main.get_rate_limiter] = lambda: RateLimiter(per_minute=1000)
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def login(client, username="hocvien") -> dict:
    r = client.post("/auth/login", json={"username": username, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_login_wrong_password(client):
    assert client.post("/auth/login", json={"username": "hocvien", "password": "x"}).status_code == 401


def test_endpoints_require_token(client):
    assert client.post("/chat", json={"message": "hi"}).status_code == 401
    assert client.get("/me").status_code == 401


def test_tampered_token_rejected(client):
    headers = login(client)
    headers["Authorization"] = headers["Authorization"][:-3] + "abc"
    assert client.get("/me", headers=headers).status_code == 401


def test_me_returns_role_from_token(client):
    assert client.get("/me", headers=login(client, "nhanvien")).json()["role"] == "staff"


def test_chat_streams_sse_events(client, backend):
    r = client.post("/chat", json={"message": "chào", "conversation_id": "c1"}, headers=login(client))
    events = parse_sse(r.text)
    assert [e for e, _ in events] == ["meta", "step", "token", "token", "done"]
    assert events[0][1]["conversation_id"] == "c1"
    ctx = backend.calls[0]["ctx"]
    assert ctx.role == "student" and ctx.hoc_vien_id == 1


def test_thread_id_is_namespaced_by_user(client, backend):
    client.post("/chat", json={"message": "a", "conversation_id": "same"}, headers=login(client, "hocvien"))
    client.post("/chat", json={"message": "a", "conversation_id": "same"}, headers=login(client, "nhanvien"))
    assert [c["ctx"].thread_id for c in backend.calls] == ["hocvien:same", "nhanvien:same"]


def test_history_cannot_read_other_users_thread(client):
    r = client.get("/conversations/same/messages", headers=login(client, "hocvien"))
    assert r.json()["messages"][0]["content"] == "thread=hocvien:same"


def test_invalid_conversation_id_rejected(client):
    r = client.post("/chat", json={"message": "a", "conversation_id": "../x"}, headers=login(client))
    assert r.status_code == 422


def test_hitl_flow_interrupt_then_resume(client, backend):
    h = login(client, "nhanvien")
    events = parse_sse(client.post("/chat", json={"message": "gửi email", "conversation_id": "c2"}, headers=h).text)
    assert events[-1][0] == "interrupt"
    # còn thao tác chờ duyệt -> không cho chat tiếp
    assert client.post("/chat", json={"message": "x", "conversation_id": "c2"}, headers=h).status_code == 409
    # số quyết định phải khớp số thao tác
    bad = client.post("/chat/resume", json={"conversation_id": "c2", "decisions": []}, headers=h)
    assert bad.status_code == 422
    r = client.post("/chat/resume", json={"conversation_id": "c2", "decisions": [{"type": "approve"}]}, headers=h)
    assert parse_sse(r.text)[-1][0] == "done"
    assert backend.calls[-1]["resume"] == [{"type": "approve"}]


def test_resume_without_pending_is_conflict(client):
    r = client.post(
        "/chat/resume", json={"conversation_id": "c3", "decisions": [{"type": "approve"}]}, headers=login(client)
    )
    assert r.status_code == 409


def test_feedback_promotes_only_for_staff(client):
    body = {"conversation_id": "c1", "run_id": "0" * 8 + "-0000-0000-0000-" + "0" * 12, "score": 1}
    assert client.post("/feedback", json=body, headers=login(client, "hocvien")).json()["promoted_sql_examples"] == []
    assert client.post("/feedback", json=body, headers=login(client, "nhanvien")).json()["promoted_sql_examples"]


def test_rate_limit(backend):
    main.app.dependency_overrides[main.get_backend] = lambda: backend
    limiter = RateLimiter(per_minute=2)
    main.app.dependency_overrides[main.get_rate_limiter] = lambda: limiter
    c = TestClient(main.app)
    h = login(c)
    codes = [c.post("/chat", json={"message": "a"}, headers=h).status_code for _ in range(3)]
    main.app.dependency_overrides.clear()
    assert codes == [200, 200, 429]
