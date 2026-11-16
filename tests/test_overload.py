"""Chống quá tải và chống kẹt (eduassist.api.overload, eduassist.db).

Phần không cần database chạy cùng test đơn vị; hai test kẹt cần Postgres (marker integration).
"""

import asyncio

import anyio.to_thread
import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout
from pydantic import ValidationError

from eduassist.api import main
from eduassist.api.overload import AdmissionControl
from eduassist.config import Settings


def _gated_app(gate: asyncio.Event) -> FastAPI:
    app = FastAPI()

    @app.get("/slow")
    async def slow():
        await gate.wait()
        return {"ok": True}

    @app.post("/chat")
    async def chat():
        await gate.wait()
        return {"ok": True}

    @app.get("/health/live")
    async def live():
        return {"status": "ok"}

    return app


def _client(asgi) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=asgi), base_url="http://t")


# ---------------------------------------------------------------- cửa vào: chạy, xếp hàng, từ chối
def test_excess_requests_wait_in_queue_then_succeed():
    async def scenario():
        gate = asyncio.Event()
        ctl = AdmissionControl(_gated_app(gate), max_concurrent=2, max_queue=10, queue_timeout=5)
        async with _client(ctl) as c:
            tasks = [asyncio.create_task(c.get("/slow")) for _ in range(5)]
            await asyncio.sleep(0.05)
            snapshot = ctl.stats()
            gate.set()
            done = await asyncio.gather(*tasks)
        return snapshot, [r.status_code for r in done], ctl.stats()

    snapshot, codes, after = asyncio.run(scenario())
    assert snapshot["active"] == 2 and snapshot["waiting"] == 3  # chỉ 2 chạy, 3 xếp hàng (không tốn luồng)
    assert codes == [200] * 5
    assert after == {"active": 0, "waiting": 0, "streams": 0, "rejected": 0}


def test_full_queue_and_queue_timeout_are_rejected_fast():
    async def scenario():
        gate = asyncio.Event()
        ctl = AdmissionControl(_gated_app(gate), max_concurrent=1, max_queue=1, queue_timeout=0.2)
        async with _client(ctl) as c:
            running = asyncio.create_task(c.get("/slow"))
            await asyncio.sleep(0.05)
            queued = asyncio.create_task(c.get("/slow"))  # vào hàng, sẽ hết hạn chờ sau 0,2 s
            await asyncio.sleep(0.05)
            full = await c.get("/slow")  # hàng đã đầy -> từ chối ngay
            timed_out = await queued
            live = await c.get("/health/live")  # luôn trả lời, kể cả khi quá tải
            gate.set()
            ok = await running
            after = await c.get("/slow")  # hết tải thì phục vụ lại bình thường
        return full, timed_out, live, ok, after, ctl

    full, timed_out, live, ok, after, ctl = asyncio.run(scenario())
    assert full.status_code == 503 and full.headers["retry-after"] == "2"
    assert "quá tải" in full.json()["detail"]
    assert timed_out.status_code == 503
    assert live.status_code == 200
    assert ok.status_code == 200 and after.status_code == 200
    assert ctl.stats()["rejected"] == 2 and ctl.stats()["active"] == 0


def test_chat_streams_have_their_own_compartment():
    async def scenario():
        gate = asyncio.Event()
        ctl = AdmissionControl(_gated_app(gate), max_concurrent=1, max_queue=0, queue_timeout=0.1, max_streams=2)
        async with _client(ctl) as c:
            chats = [asyncio.create_task(c.post("/chat")) for _ in range(2)]
            await asyncio.sleep(0.05)
            third_chat = await c.post("/chat")  # ngăn chat đầy
            page = asyncio.create_task(c.get("/slow"))  # trang thường vẫn còn chỗ
            await asyncio.sleep(0.05)
            gate.set()
            return third_chat, await page, await asyncio.gather(*chats)

    third_chat, page, chats = asyncio.run(scenario())
    assert third_chat.status_code == 503
    assert page.status_code == 200
    assert [r.status_code for r in chats] == [200, 200]


def test_admission_disabled_when_zero():
    async def scenario():
        gate = asyncio.Event()
        gate.set()
        ctl = AdmissionControl(_gated_app(gate), max_concurrent=0)
        async with _client(ctl) as c:
            return [r.status_code for r in await asyncio.gather(*(c.get("/slow") for _ in range(5)))]

    assert asyncio.run(scenario()) == [200] * 5


def test_settings_refuse_admission_limits_that_can_starve_the_thread_pool():
    with pytest.raises(ValidationError, match="THREAD_POOL_SIZE"):
        Settings(thread_pool_size=40, max_concurrent_requests=32, max_concurrent_streams=8)
    assert Settings(thread_pool_size=100, max_concurrent_requests=32, max_concurrent_streams=40)


# ---------------------------------------------------------------- hết kết nối -> 503, không phải 500
def test_pool_timeout_becomes_503_with_retry_after():
    def exhausted():
        raise PoolTimeout("couldn't get a connection after 5.00 sec")

    @main.app.get("/_test/pool-exhausted")
    def _route(_=Depends(exhausted)):
        return {}

    try:
        r = TestClient(main.app).get("/_test/pool-exhausted")
    finally:
        main.app.router.routes = [
            rt for rt in main.app.router.routes if getattr(rt, "path", "") != "/_test/pool-exhausted"
        ]
    assert r.status_code == 503
    assert r.headers["retry-after"] == "2"
    assert "quá tải" in r.json()["detail"]


def test_health_live_does_not_touch_database():
    # Không override backend / database: nếu endpoint đụng DB thì test này lỗi khi không có Postgres
    r = TestClient(main.app).get("/health/live")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


# ---------------------------------------------------------------- kẹt khi tải cao (cần Postgres)
@pytest.fixture
def tiny_pools(monkeypatch):
    """Pool chính 1 kết nối, pool đăng nhập 1 kết nối, chờ tối đa 1 giây."""
    from eduassist import db
    from eduassist.api.auth import get_user_loader
    from eduassist.config import get_settings

    monkeypatch.setenv("DB_POOL_SIZE", "1")
    monkeypatch.setenv("DB_AUTH_POOL_SIZE", "1")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "1")
    for cached in (get_settings, db.app_pool, db.auth_pool, get_user_loader):
        cached.cache_clear()
    user = get_user_loader()("quanly")
    assert user is not None, "cần dữ liệu demo (uv run eduassist-setup)"
    yield user
    for pool in (db.app_pool, db.auth_pool):
        if pool.cache_info().currsize:
            pool().close()
        pool.cache_clear()
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.mark.integration
def test_request_holding_db_connection_can_still_authenticate(tiny_pools):
    """Endpoint dùng Depends(db) giữ 1 kết nối app_pool rồi mới kiểm tra đăng nhập. Khi kiểm tra đăng nhập
    còn dùng chung app_pool, request này kẹt tới hết hạn chờ (deadlock thứ nhất khi test tải)."""
    from eduassist.api.auth import create_token

    token = create_token(tiny_pools)
    r = TestClient(main.app).get("/me/today", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text


@pytest.mark.integration
def test_many_concurrent_requests_do_not_starve_thread_pool(tiny_pools):
    """Deadlock thứ hai: thread pool 4 luồng, 1 kết nối DB, 20 request cùng lúc. Không có kiểm soát cửa vào,
    các luồng bị request chờ kết nối chiếm hết trong khi request đang giữ kết nối chờ luồng -> lỗi 503 hàng loạt.
    Cửa vào cho chạy 2 request một lúc (< 4 luồng) thì mọi request đều xong."""
    from eduassist.api.auth import create_token

    headers = {"Authorization": f"Bearer {create_token(tiny_pools)}"}
    gated = AdmissionControl(main.app, max_concurrent=2, max_queue=100, queue_timeout=30, max_streams=1)

    async def scenario():
        anyio.to_thread.current_default_thread_limiter().total_tokens = 4
        async with _client(gated) as c:
            return await asyncio.gather(*(c.get("/me/today", headers=headers) for _ in range(20)))

    codes = [r.status_code for r in asyncio.run(scenario())]
    assert codes == [200] * 20, codes
