"""Chạy nhiều tiến trình / nhiều máy (docs/SCALING_PLAN.md giai đoạn 2-4): trạng thái dùng chung trong Redis, Redis
lỗi thì tự dùng RAM, chat async có giới hạn thời gian và số lượt chạy cùng lúc, /metrics.

Phần đầu không cần Redis hay database. Phần cuối (integration) cần `docker compose up -d db redis`.
"""

import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient
from psycopg.pq import TransactionStatus

from eduassist import cache
from eduassist.config import Settings


@pytest.fixture
def no_redis(monkeypatch):
    monkeypatch.setattr(cache, "_client", lambda: None)
    cache._local_cache.clear()


# ---------------------------------------------------------------- không có Redis: hành vi như một tiến trình
def test_rate_limiter_without_redis_counts_in_memory(no_redis):
    rl = cache.RateLimiter(3, "t_mem")
    for _ in range(3):
        rl.hit("ip1")
    with pytest.raises(cache.TooManyRequests) as e:
        rl.hit("ip1")
    assert 1 <= e.value.retry_after <= 61
    rl.hit("ip2")  # khoá khác không bị ảnh hưởng


def test_redis_down_falls_back_to_memory_without_waiting_each_time(monkeypatch):
    import redis

    # Cổng không có ai nghe: lệnh đầu lỗi sau tối đa timeout, sau đó ngắt mạch -> không chờ nữa
    dead = redis.Redis(host="127.0.0.1", port=6390, socket_timeout=0.2, socket_connect_timeout=0.2)
    monkeypatch.setattr(cache, "_client", lambda: dead)
    monkeypatch.setattr(cache, "_breaker", cache._Breaker())
    rl = cache.RateLimiter(2, "t_down")
    rl.hit("k")  # lỗi Redis -> đếm trong RAM
    assert cache.redis_status() == "down"
    start = time.perf_counter()
    rl.hit("k")
    with pytest.raises(cache.TooManyRequests):
        rl.hit("k")  # giới hạn vẫn có hiệu lực khi Redis chết
    assert time.perf_counter() - start < 0.1  # đang ngắt mạch: không thử Redis lại
    assert cache.get_account("ai_do") is None  # cache tài khoản tắt -> đọc DB


def test_after_redis_failure_only_one_caller_probes_again(monkeypatch):
    b = cache._Breaker()
    b.trip(RuntimeError("down"))
    assert not b.available()
    monkeypatch.setattr(cache, "REDIS_RETRY_SECONDS", 0.0)
    b.down_until = 0
    assert b.available() is True  # người thử lại
    b.down_until = time.monotonic() + 5
    assert b.available() is False  # những người khác vẫn dùng RAM trong lúc đó
    b.success()
    assert b.available() and not b.is_down()


def test_slots_limit_concurrent_work_without_redis(no_redis):
    slots = cache.Slots("t", 2, lease_seconds=30)
    a, b = slots.acquire(), slots.acquire()
    assert a and b and slots.acquire() is None
    slots.release(a)
    assert slots.in_use() == 1
    assert slots.acquire() is not None


def test_cached_json_computes_once_and_keeps_api_types(no_redis):
    from decimal import Decimal

    calls = []

    def compute():
        calls.append(1)
        return {"hoc_phi": Decimal("3500000"), "giam": Decimal("0.5")}

    first = cache.cached_json("t:x", 60, compute)
    second = cache.cached_json("t:x", 60, compute)
    assert first == second == {"hoc_phi": 3500000, "giam": 0.5}  # cùng cách đổi kiểu với API (fastjson)
    assert len(calls) == 1


def test_cached_json_single_flight_when_many_requests_miss_together(no_redis):
    import threading

    calls = []

    def slow():
        calls.append(1)
        time.sleep(0.2)
        return {"n": 1}

    results = []
    threads = [threading.Thread(target=lambda: results.append(cache.cached_json("t:sf", 60, slow))) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == [{"n": 1}] * 10 and len(calls) == 1


@pytest.mark.integration
def test_cached_json_single_flight_across_processes(real_redis):
    # Tiến trình khác đang giữ khoá tính lại: tiến trình này chờ kết quả thay vì tự chạy truy vấn nặng
    real_redis.set("ea:c:t:x2:lock", "1", px=3000)

    def other_process_fills():
        time.sleep(0.2)
        real_redis.set("ea:c:t:x2", '{"v": 2}', ex=60)

    import threading

    threading.Thread(target=other_process_fills).start()
    assert cache.cached_json("t:x2", 60, lambda: {"v": "tự tính"}) == {"v": 2}


class _Info:
    def __init__(self, status):
        self.transaction_status = status


class _Conn:
    def __init__(self, status):
        self.info = _Info(status)


def test_account_cache_cleared_again_after_commit(monkeypatch):
    deleted = []
    monkeypatch.setattr(cache, "forget_account", deleted.append)
    conn = _Conn(TransactionStatus.INTRANS)
    cache.account_changed(conn, "lan")
    assert deleted == ["lan"]  # xoá ngay
    cache.flush_after_commit(conn)
    assert deleted == ["lan", "lan"]  # và xoá lại sau commit (chặn request khác ghi lại bản cũ chưa commit)
    cache.flush_after_commit(conn)
    assert deleted == ["lan", "lan"]


def test_production_refuses_many_workers_without_redis(monkeypatch):
    monkeypatch.setenv("WEB_CONCURRENCY", "4")
    strong = "x" * 40
    base = dict(
        app_env="production",
        jwt_secret=strong,
        agent_ro_password=strong,
        database_url=f"postgresql://app_rw:{strong}@db/eduassist",
        agent_ro_url=f"postgresql://agent_ro:{strong}@db/eduassist",
        cors_origins="https://a.vn",
    )
    with pytest.raises(ValueError, match="REDIS_URL"):
        Settings(**base)
    assert Settings(**base, redis_url="redis://redis:6379/0")


# ---------------------------------------------------------------- chat async: giới hạn thời gian, số lượt, đóng giữa chừng
class _SlowGraph:
    def __init__(self, delay: float, fail: bool = False):
        self.delay = delay
        self.fail = fail

    async def astream(self, *a, **kw):
        yield (), "custom", {"type": "agent_start", "agent": "advisor"}
        if self.fail:
            raise RuntimeError("Groq 500")
        await asyncio.sleep(self.delay)
        yield (), "custom", {"type": "agent_end"}


def _ctx():
    from eduassist.agents.context import UserContext

    return UserContext(user_id="u", role="student", display_name="U", run_id="r", thread_id="u:t")


async def _collect(agen):
    return [ev async for ev in agen]


@pytest.fixture
def chat_env(monkeypatch, no_redis):
    from eduassist import chat

    slots = cache.Slots("t_llm", 1, lease_seconds=60)
    monkeypatch.setattr(cache, "llm_slots", lambda: slots)

    class S:
        chat_turn_timeout_seconds = 0.3

    monkeypatch.setattr(chat, "get_settings", lambda: S)
    return chat, slots


def test_chat_turn_stops_at_total_timeout_and_frees_slot(chat_env, monkeypatch):
    chat, slots = chat_env

    async def graph(role):
        return _SlowGraph(delay=5)

    monkeypatch.setattr(chat, "abuild_supervisor", graph)
    start = time.perf_counter()
    events = asyncio.run(_collect(chat.astream_turn(_ctx(), message="hi")))
    assert time.perf_counter() - start < 4  # bị cắt ở 0,3 giây, không chờ hết 5 giây của LLM giả
    assert events[-1]["type"] == "error" and events[-1]["code"] == "timeout"
    assert slots.in_use() == 0


def test_chat_busy_when_llm_slots_full(chat_env, monkeypatch):
    chat, slots = chat_env
    held = slots.acquire()

    async def graph(role):  # không được gọi tới
        raise AssertionError

    monkeypatch.setattr(chat, "abuild_supervisor", graph)
    events = asyncio.run(_collect(chat.astream_turn(_ctx(), message="hi")))
    assert events == [{"type": "error", "message": chat.BUSY_MESSAGE, "code": "busy"}]
    slots.release(held)


def test_chat_error_and_early_close_free_slot(chat_env, monkeypatch):
    chat, slots = chat_env

    async def failing(role):
        return _SlowGraph(delay=0, fail=True)

    monkeypatch.setattr(chat, "abuild_supervisor", failing)
    events = asyncio.run(_collect(chat.astream_turn(_ctx(), message="hi")))
    assert events[-1]["type"] == "error" and slots.in_use() == 0

    async def slow(role):
        return _SlowGraph(delay=5)

    monkeypatch.setattr(chat, "abuild_supervisor", slow)

    async def close_after_first():
        gen = chat.astream_turn(_ctx(), message="hi")
        first = await anext(gen)
        assert slots.in_use() == 1
        await gen.aclose()  # người dùng đóng trình duyệt
        return first

    assert asyncio.run(close_after_first())["step"] == "agent_start"
    assert slots.in_use() == 0


def test_sse_closes_async_source_when_client_stops_reading():
    from eduassist.api.sse import sse_response

    closed = []

    async def source():
        try:
            yield {"type": "token", "text": "a"}
            await asyncio.sleep(10)
            yield {"type": "done"}
        finally:
            closed.append(True)

    async def scenario():
        body = sse_response(source(), {"conversation_id": "c"}).body_iterator
        frames = [await anext(body), await anext(body)]
        await body.aclose()
        return frames

    frames = asyncio.run(scenario())
    assert frames[0].startswith("event: meta") and '"text": "a"' in frames[1]
    assert closed == [True]


# ---------------------------------------------------------------- /metrics
def test_metrics_endpoint_counts_requests_by_route_template(no_redis):
    from eduassist.api import main

    c = TestClient(main.app)
    c.get("/health/live")
    c.get("/khong-co")
    text = c.get("/metrics").text
    assert 'route="/health/live",method="GET",status="200"' in text
    assert 'route="khac",method="GET",status="404"' in text
    assert "eduassist_request_seconds_bucket" in text and "eduassist_llm_turns_in_use" in text


def test_metrics_token_required_when_configured(monkeypatch, no_redis):
    from pydantic import SecretStr

    from eduassist.api import main

    real = main.get_settings()
    monkeypatch.setattr(main, "get_settings", lambda: real.model_copy(update={"metrics_token": SecretStr("bi-mat")}))
    c = TestClient(main.app)
    assert c.get("/metrics").status_code == 401
    assert c.get("/metrics", headers={"Authorization": "Bearer bi-mat"}).status_code == 200


# ================================================================ cần Redis + Postgres thật
REDIS_URL = "redis://localhost:6379/15"


@pytest.fixture
def real_redis(monkeypatch):
    import redis

    r = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=1)
    try:
        r.ping()
    except redis.RedisError:
        pytest.skip("cần Redis: docker compose up -d redis")
    r.flushdb()
    monkeypatch.setattr(cache, "_client", lambda: r)
    monkeypatch.setattr(cache, "_breaker", cache._Breaker())
    yield r
    r.flushdb()


@pytest.mark.integration
def test_rate_limit_is_shared_between_processes(real_redis):
    # Hai đối tượng = hai tiến trình API: cùng một bộ đếm trong Redis (trước đây mỗi tiến trình đếm riêng)
    a, b = cache.RateLimiter(4, "login"), cache.RateLimiter(4, "login")
    for limiter in (a, b, a, b):
        limiter.hit("1.2.3.4")
    with pytest.raises(cache.TooManyRequests):
        a.hit("1.2.3.4")
    with pytest.raises(cache.TooManyRequests):
        b.hit("1.2.3.4")


@pytest.mark.integration
def test_llm_slots_shared_and_expire_if_holder_dies(real_redis):
    a, b = cache.Slots("llm_t", 2, lease_seconds=0.5), cache.Slots("llm_t", 2, lease_seconds=0.5)
    t1, t2 = a.acquire(), b.acquire()
    assert t1 and t2 and a.acquire() is None and b.in_use() == 2
    b.release(t2)
    assert a.acquire() is not None
    time.sleep(0.6)  # tiến trình giữ chỗ chết, không kịp release: chỗ tự trả khi hết hạn thuê
    assert b.in_use() == 0


@pytest.mark.integration
def test_account_cache_dropped_when_account_changes(real_redis):
    from eduassist.api import auth
    from eduassist.api.platform import db
    from eduassist.services import accounts

    assert auth._load_from_db("ketoan") is not None
    assert cache.get_account("ketoan")["role"] == "accountant"
    gen = db()  # đúng cách API mở transaction (dependency `db`)
    conn = next(gen)
    accounts.logout_everywhere(conn, "ketoan")
    with pytest.raises(StopIteration):
        next(gen)  # commit + xoá cache sau commit
    assert cache.get_account("ketoan") is None
    fresh = auth._load_from_db("ketoan")
    assert fresh.token_version == cache.get_account("ketoan")["token_version"]


@pytest.mark.integration
def test_public_pages_served_from_shared_cache(real_redis):
    from eduassist.api import main

    c = TestClient(main.app)
    first = c.get("/public/schedule")
    assert first.status_code == 200
    assert real_redis.get("ea:c:public:schedule") is not None
    assert c.get("/public/schedule").json() == first.json()


# ---------------------------------------------------------------- worker: khoá chống chạy trùng, "chạy ngay" qua hàng đợi
@pytest.mark.integration
def test_scheduled_agent_skipped_while_another_worker_runs_it():
    import psycopg

    from eduassist.background import runner
    from eduassist.config import get_settings

    with psycopg.connect(get_settings().database_url) as other:  # worker khác đang giữ khoá của agent
        other.execute("SELECT pg_advisory_xact_lock(hashtext('agent:cong_no'))")
        res = runner.run_agent("cong_no", "lich:daily")
        other.rollback()
    assert "bo_qua" in res and "run_id" not in res


@pytest.mark.integration
def test_scheduled_agent_rechecks_inside_lock(monkeypatch):
    from eduassist.background import runner
    from eduassist.db import app_pool
    from eduassist.services.core import today

    with app_pool().connection() as c:
        rid = c.execute(
            """INSERT INTO lan_chay_agent (agent, kich_hoat, ngay_nghiep_vu, ket_thuc, trang_thai, tom_tat)
               VALUES ('bao_cao', 'lich:weekly', %s, now(), 'xong', 'test') RETURNING id""",
            (today(),),
        ).fetchone()["id"]
    try:
        # Worker A đã chạy xong ca tuần này; worker B lấy danh sách "đến lịch" từ trước nên vẫn gọi run_agent
        res = runner.run_agent("bao_cao", "lich:weekly")
        assert res.get("bo_qua", "").startswith("Worker khác")
    finally:
        with app_pool().connection() as c:
            c.execute("DELETE FROM lan_chay_agent WHERE id = %s", (rid,))


@pytest.mark.integration
def test_run_now_goes_through_worker_queue(monkeypatch):
    from eduassist.background import runner
    from eduassist.db import app_pool

    with app_pool().connection() as c:
        c.execute(f"DELETE FROM outbox_su_kien WHERE loai = '{runner.RUN_REQUEST}' AND processed_at IS NULL")
        req = runner.request_run(c, "bao_cao", "quanly")
        again = runner.request_run(c, "bao_cao", "quanly")  # bấm 2 lần khi chưa chạy: vẫn một yêu cầu
        assert again["yeu_cau_id"] == req["yeu_cau_id"]
        assert runner.run_request_status(c, req["yeu_cau_id"])["trang_thai"] == "cho"
        run_id = c.execute(
            """INSERT INTO lan_chay_agent (agent, kich_hoat, ngay_nghiep_vu, ket_thuc, trang_thai, tom_tat,
                      so_de_xuat, so_tu_dong)
               VALUES ('bao_cao', 'thu_cong:quanly', current_date, now(), 'xong', 'Đã lập báo cáo', 1, 0) RETURNING id"""
        ).fetchone()["id"]
    calls = []

    def fake_run(name, trigger, event=None, conn=None):
        calls.append((name, trigger))
        return {"agent": name, "run_id": run_id, "tom_tat": "Đã lập báo cáo"}

    monkeypatch.setattr(runner, "run_agent", fake_run)
    try:
        assert runner.process_run_requests() == 1
        assert runner.process_run_requests() == 0  # chạy đúng một lần
        assert calls == [("bao_cao", "thu_cong:quanly")]
        with app_pool().connection() as c:
            st = runner.run_request_status(c, req["yeu_cau_id"])
        assert st["trang_thai"] == "xong" and st["tom_tat"] == "Đã lập báo cáo" and st["de_xuat"] == 1
    finally:
        with app_pool().connection() as c:
            c.execute("DELETE FROM outbox_su_kien WHERE id = %s", (req["yeu_cau_id"],))
            c.execute("DELETE FROM lan_chay_agent WHERE id = %s", (run_id,))


# ---------------------------------------------------------------- chat async thật (LLM giả) + checkpointer async
@pytest.mark.integration
def test_async_chat_streams_and_saves_conversation(monkeypatch, no_redis):
    import uuid

    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage

    from eduassist import chat
    from eduassist.agents import persistence, supervisor
    from eduassist.agents.context import UserContext

    class FakeLLM(GenericFakeChatModel):
        def bind_tools(self, tools, **kw):
            return self

    monkeypatch.setattr(supervisor, "chat_model", lambda *a, **k: FakeLLM(messages=iter([AIMessage("Chào bạn nhé")])))
    monkeypatch.setattr(supervisor, "_async_graphs", {})
    tid = f"test_async:{uuid.uuid4().hex[:8]}"
    ctx = UserContext(user_id="test_async", role="student", display_name="T", run_id="r", thread_id=tid)

    async def run():
        try:
            return [ev async for ev in chat.astream_turn(ctx, message="Xin chào")]
        finally:
            saver = await persistence.get_async_checkpointer()
            history = await (await supervisor.abuild_supervisor("student")).aget_state(chat._config(ctx))
            await saver.adelete_thread(tid)
            await persistence.close_async()
            run.history = history

    # psycopg async không chạy trên ProactorEventLoop mặc định của Windows (Docker/Linux thì không sao)
    events = asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    tokens = "".join(e["text"] for e in events if e["type"] == "token")
    assert tokens == "Chào bạn nhé"
    assert events[-1] == {"type": "done", "answer": "Chào bạn nhé", "sources": []}
    msgs = run.history.values["messages"]
    assert [m.type for m in msgs] == ["human", "ai"]
    assert json.dumps([m.content for m in msgs], ensure_ascii=False) == '["Xin chào", "Chào bạn nhé"]'


# ---------------------------------------------------------------- truy vấn danh sách theo trang (dữ liệu lớn)
@pytest.mark.integration
def test_paged_class_list_matches_full_list():
    from eduassist.db import app_pool
    from eduassist.services import training
    from eduassist.services.core import Actor

    me = Actor(id="giaovu", role="academic")
    with app_pool().connection() as c:
        full = training.list_classes(c, me)
        page = training.list_classes(c, me, limit=7, offset=5)
        opened = training.list_classes(c, me, open_only=True)
    assert page.total == len(full) and list(page) == full[5:12]
    assert opened and {r["trang_thai"] for r in opened} <= {"dang_hoc", "sap_khai_giang"}


@pytest.mark.integration
def test_invoice_pages_cover_every_invoice_once_in_order():
    from eduassist.db import app_pool
    from eduassist.services import finance
    from eduassist.services.core import Actor

    me = Actor(id="ketoan", role="accountant")
    with app_pool().connection() as c:
        pages = [finance.list_invoices(c, me, limit=100, offset=o) for o in range(0, 2000, 100)]
        total = c.execute("SELECT count(*) AS n FROM don_hang").fetchone()["n"]
    rows = [r for p in pages for r in p]
    assert pages[0].total == total == len(rows) == len({r["id"] for r in rows})
    keys = [(r["han_gan_nhat"] is None, r["han_gan_nhat"] or 0, -r["id"]) for r in rows]
    assert keys == sorted(keys, key=lambda k: (k[0], str(k[1]), k[2]))


@pytest.mark.integration
def test_request_waiting_on_a_locked_table_fails_fast_with_503():
    # Diễn tập "DB đứng": một transaction khoá hẳn bảng học viên. Request chờ khoá phải nhả sau lock_timeout (5 giây),
    # không giữ chỗ chạy tới statement_timeout (15 giây) làm mọi trang khác lỗi theo.
    import psycopg

    from eduassist.api import main
    from eduassist.api.auth import AuthUser, get_user_loader
    from eduassist.config import get_settings

    users = {"giaovu": AuthUser("giaovu", "academic", "Giáo vụ", None)}
    main.app.dependency_overrides[get_user_loader] = lambda: users.get
    try:
        c = TestClient(main.app)
        from eduassist.api.auth import create_token

        h = {"Authorization": f"Bearer {create_token(users['giaovu'])}"}
        with psycopg.connect(get_settings().database_url) as locker:
            locker.execute("LOCK TABLE hoc_vien IN ACCESS EXCLUSIVE MODE")
            start = time.perf_counter()
            r = c.get("/students?limit=5", headers=h)
            waited = time.perf_counter() - start
            locker.rollback()
        assert r.status_code == 503 and r.headers["retry-after"] == "2"
        assert 4 <= waited < 10
        assert c.get("/students?limit=5", headers=h).status_code == 200  # nhả khoá là chạy lại ngay
    finally:
        main.app.dependency_overrides.clear()


def test_llm_retries_only_transient_errors():
    import httpx
    from groq import APIConnectionError, APIStatusError

    from eduassist.llm import transient_error

    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")

    def status(code):
        return APIStatusError("x", response=httpx.Response(code, request=req), body=None)

    assert transient_error(status(429)) and transient_error(status(503)) and transient_error(status(500))
    assert not transient_error(status(401)) and not transient_error(status(400)) and not transient_error(status(403))
    assert transient_error(APIConnectionError(request=req)) and transient_error(TimeoutError())
    assert not transient_error(ValueError("bug trong code"))
