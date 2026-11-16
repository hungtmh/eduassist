"""Trạng thái dùng chung giữa các tiến trình / máy API, lưu trong Redis.

Chạy nhiều tiến trình (WEB_CONCURRENCY > 1) hoặc nhiều máy thì bộ đếm trong RAM của từng tiến trình là sai: kẻ dò mật
khẩu được thử gấp N lần, giới hạn chat tổng nhân N lần. Module này đưa các bộ đếm đó vào Redis:

- RateLimiter : giới hạn lượt gọi theo cửa sổ trượt 60 giây (đăng nhập theo IP, chat theo người...).
- Slots       : giới hạn số việc chạy cùng lúc cho toàn hệ thống (số lượt chat LLM đang chạy).
- tài khoản   : cache 30 giây kết quả đọc tài khoản ở đầu mỗi request; xoá ngay khi tài khoản đổi.
- cached_json : cache số liệu tổng hợp ít đổi (bản tin, danh sách khoá học công khai).

REDIS_URL trống (dev, test, chạy 1 tiến trình): mọi thứ lưu trong RAM như trước, không cần cài Redis.

Redis lỗi hoặc chậm: mỗi lệnh chờ tối đa redis_timeout giây, lỗi thì cả tiến trình bỏ qua Redis trong
REDIS_RETRY_SECONDS giây (không để mọi request đều chờ timeout) và dùng tạm bộ nhớ của tiến trình. Giới hạn lượt gọi
vẫn có hiệu lực (theo từng tiến trình), cache tài khoản thì tắt -> đọc thẳng DB. Hệ thống chậm đi chứ không dừng.
"""

import json
import logging
import secrets
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from eduassist.config import get_settings

log = logging.getLogger("eduassist.cache")

REDIS_RETRY_SECONDS = 5.0
ACCOUNT_TTL_SECONDS = 30
_PREFIX = "ea:"


# ---------------------------------------------------------------- kết nối Redis + ngắt mạch khi Redis lỗi
class _Breaker:
    """Ngắt mạch: Redis lỗi thì cả tiến trình dùng RAM trong REDIS_RETRY_SECONDS giây. Hết hạn thì chỉ MỘT lệnh được
    thử lại Redis, các lệnh khác vẫn dùng RAM cho tới khi lần thử đó thành công. (Diễn tập tắt Redis: nếu mọi luồng cùng
    thử lại một lúc, mỗi luồng chờ phân giải tên máy / timeout, API đứng vài giây mỗi chu kỳ.)"""

    def __init__(self):
        self.down_until = 0.0
        self.tripped = False
        self.lock = threading.Lock()

    def available(self) -> bool:
        if not self.tripped:
            return True
        with self.lock:
            if time.monotonic() < self.down_until:
                return False
            self.down_until = time.monotonic() + REDIS_RETRY_SECONDS  # người thử là mình; người khác chờ chu kỳ sau
            return True

    def is_down(self) -> bool:
        return self.tripped

    def success(self) -> None:
        if self.tripped:
            with self.lock:
                self.tripped = False
            log.info("Redis đã trở lại")

    def trip(self, exc: Exception) -> None:
        with self.lock:
            first = not self.tripped
            self.tripped = True
            self.down_until = time.monotonic() + REDIS_RETRY_SECONDS
        if first:
            log.warning("Redis lỗi, dùng bộ nhớ tiến trình (thử lại mỗi %ss): %s", REDIS_RETRY_SECONDS, exc)


_breaker = _Breaker()


@lru_cache
def _client():
    url = get_settings().redis_url
    if not url:
        return None
    import redis

    t = get_settings().redis_timeout
    return redis.Redis.from_url(
        url,
        socket_timeout=t,
        socket_connect_timeout=t,
        health_check_interval=30,
        decode_responses=True,
        # Pool có hạn: Redis chậm thì luồng chờ trong pool tối đa t giây rồi báo lỗi, không mở kết nối vô hạn
        max_connections=get_settings().redis_max_connections,
    )


def redis_client():
    """Client Redis đang dùng được, hoặc None (chưa cấu hình / đang ngắt mạch)."""
    c = _client()
    return c if c is not None and _breaker.available() else None


def _call(fn: Callable[[Any], Any], fallback: Callable[[], Any]):
    """Chạy fn(redis); không có Redis hoặc Redis lỗi thì chạy fallback()."""
    r = redis_client()
    if r is None:
        return fallback()
    try:
        out = fn(r)
    except Exception as e:  # redis.RedisError, timeout, mất kết nối...
        _breaker.trip(e)
        return fallback()
    _breaker.success()
    return out


def redis_status() -> str:
    """'off' (không cấu hình) | 'ok' | 'down' - dùng cho /metrics."""
    if _client() is None:
        return "off"
    return "down" if _breaker.is_down() else "ok"


# ---------------------------------------------------------------- giới hạn lượt gọi (cửa sổ trượt 60 giây)
# Một ZSET mỗi khoá, phần tử = mốc thời gian (ms). Chạy nguyên khối trong Redis nên nhiều tiến trình không đếm lệch.
# Trả {1, 0} nếu cho qua, {0, số_ms_cần_chờ} nếu vượt.
_SLIDING_WINDOW = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, now - window)
if redis.call('ZCARD', KEYS[1]) >= limit then
  local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  return {0, tonumber(oldest[2]) + window - now}
end
redis.call('ZADD', KEYS[1], now, now .. ':' .. ARGV[3])
redis.call('PEXPIRE', KEYS[1], window)
return {1, 0}
"""


class TooManyRequests(Exception):
    def __init__(self, retry_after: int):
        super().__init__(retry_after)
        self.retry_after = retry_after


class RateLimiter:
    """per_minute lượt trong 60 giây gần nhất cho mỗi khoá. name tách các bộ đếm khác nhau dùng chung khoá."""

    WINDOW_MS = 60_000

    def __init__(self, per_minute: int, name: str = "default"):
        self.per_minute = per_minute
        self.name = name
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> None:
        """Ghi một lượt; vượt giới hạn thì raise TooManyRequests."""
        wait_ms = _call(lambda r: self._redis_hit(r, key), lambda: self._memory_hit(key))
        if wait_ms:
            raise TooManyRequests(max(1, int(wait_ms / 1000) + 1))

    def _redis_hit(self, r, key: str) -> int:
        ok, wait_ms = r.eval(
            _SLIDING_WINDOW, 1, f"{_PREFIX}rl:{self.name}:{key}", self.WINDOW_MS, self.per_minute, secrets.token_hex(4)
        )
        return 0 if int(ok) else int(wait_ms)

    def _memory_hit(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.WINDOW_MS / 1000:
                hits.popleft()
            if len(hits) >= self.per_minute:
                return int((self.WINDOW_MS / 1000 - (now - hits[0])) * 1000)
            hits.append(now)
            return 0


# ---------------------------------------------------------------- giới hạn số việc chạy cùng lúc (toàn hệ thống)
# ZSET: phần tử = mã lượt, điểm = hạn thuê (ms). Tiến trình chết giữa chừng thì chỗ tự trả khi hết hạn thuê.
_ACQUIRE = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, now)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then return 0 end
redis.call('ZADD', KEYS[1], now + tonumber(ARGV[2]), ARGV[3])
redis.call('PEXPIRE', KEYS[1], tonumber(ARGV[2]) * 2)
return 1
"""


class Slots:
    """Tối đa `limit` việc cùng lúc. acquire() không chờ: hết chỗ thì trả None ngay để báo người dùng thử lại."""

    def __init__(self, name: str, limit: int, lease_seconds: float):
        self.name = name
        self.limit = limit
        self.lease_ms = int(lease_seconds * 1000)
        self.key = f"{_PREFIX}slots:{name}"
        self._local = 0
        self._lock = threading.Lock()

    def acquire(self) -> str | None:
        r = redis_client()
        if r is not None:
            token = secrets.token_hex(8)
            try:
                ok = r.eval(_ACQUIRE, 1, self.key, self.limit, self.lease_ms, token)
            except Exception as e:
                _breaker.trip(e)
            else:
                _breaker.success()
                return token if ok else None
        # Không có Redis: giới hạn theo tiến trình; mã "mem:" để release biết trả chỗ về đâu
        with self._lock:
            if self._local >= self.limit:
                return None
            self._local += 1
        return "mem:" + secrets.token_hex(8)

    def release(self, token: str) -> None:
        if token.startswith("mem:"):
            with self._lock:
                self._local -= 1
            return
        _call(lambda r: r.zrem(self.key, token), lambda: None)

    def in_use(self) -> int:
        def redis_count(r):
            r.zremrangebyscore(self.key, 0, int(time.time() * 1000))
            return r.zcard(self.key)

        return _call(redis_count, lambda: self._local)


@lru_cache
def llm_slots() -> Slots:
    """Số lượt chat LLM đang chạy trên toàn hệ thống (Copilot + chat công khai)."""
    s = get_settings()
    return Slots("llm", s.llm_max_concurrent, s.chat_turn_timeout_seconds + 15)


# ---------------------------------------------------------------- cache tài khoản (đầu mỗi request)
def _account_key(username: str) -> str:
    return f"{_PREFIX}acct:{username}"


def get_account(username: str) -> dict | None:
    raw = _call(lambda r: r.get(_account_key(username)), lambda: None)
    return json.loads(raw) if raw else None


def put_account(username: str, data: dict) -> None:
    _call(lambda r: r.set(_account_key(username), json.dumps(data), ex=ACCOUNT_TTL_SECONDS), lambda: None)


def forget_account(username: str) -> None:
    def delete(r):
        r.delete(_account_key(username))

    def unavailable():
        # Không xoá được (Redis đang lỗi): bản cache cũ tự hết hạn sau ACCOUNT_TTL_SECONDS giây
        if _client() is not None:
            log.warning("không xoá được cache tài khoản %s; tự hết hạn sau %ss", username, ACCOUNT_TTL_SECONDS)

    _call(delete, unavailable)


# Xoá cache SAU khi transaction commit: xoá trước commit thì request khác có thể đọc lại bản cũ (chưa commit) từ DB
# rồi ghi đè vào cache. account_changed() xoá ngay một lần và ghi tên lại; dependency `db` gọi flush_after_commit().
_pending: dict[int, set[str]] = defaultdict(set)
_pending_lock = threading.Lock()


def account_changed(conn, username: str) -> None:
    forget_account(username)
    from psycopg.pq import TransactionStatus

    if conn is not None and conn.info.transaction_status != TransactionStatus.IDLE:
        with _pending_lock:
            _pending[id(conn)].add(username)


def flush_after_commit(conn) -> None:
    with _pending_lock:
        names = _pending.pop(id(conn), set())
    for n in names:
        forget_account(n)


def discard_pending(conn) -> None:
    with _pending_lock:
        _pending.pop(id(conn), None)


# ---------------------------------------------------------------- cache số liệu tổng hợp
_local_cache: dict[str, tuple[float, str]] = {}
_local_lock = threading.Lock()


_key_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
FILL_WAIT_SECONDS = 3.0


def cached_json(key: str, ttl: int, compute: Callable[[], Any]) -> Any:
    """Giá trị đã cache (tối đa ttl giây) hoặc compute(). Có Redis: dùng chung mọi tiến trình. Không: RAM tiến trình.

    Hết hạn đúng lúc đông người xem thì CHỈ MỘT request tính lại, các request khác chờ kết quả đó (tối đa
    FILL_WAIT_SECONDS giây) - không để hàng chục request cùng chạy một truy vấn nặng (đo được: bản tin trên 1,3 triệu
    lượt điểm danh bị tính 8 lần cùng lúc, mỗi lần 1,3 giây). Trong tiến trình: khoá theo khoá cache. Giữa các tiến
    trình: khoá SET NX trong Redis."""
    full = f"{_PREFIX}c:{key}"

    def local_get():
        with _local_lock:
            hit = _local_cache.get(full)
        return hit[1] if hit and hit[0] > time.monotonic() else None

    def get():
        return _call(lambda r: r.get(full), local_get)

    raw = get()
    if raw is not None:
        return json.loads(raw)
    if len(_key_locks) > 2000:  # khoá cache theo tham số người dùng gửi (bộ lọc): không để phình vô hạn
        _key_locks.clear()
    with _key_locks[full]:
        raw = get()  # request khác trong tiến trình vừa tính xong
        if raw is None:
            raw = _fill(full, ttl, compute, get)
    return json.loads(raw)


def _fill(full: str, ttl: int, compute: Callable[[], Any], get: Callable[[], str | None]) -> str:
    from eduassist.api.fastjson import dumps

    lock_key = full + ":lock"
    holder = _call(lambda r: bool(r.set(lock_key, "1", nx=True, px=int(FILL_WAIT_SECONDS * 1000))), lambda: True)
    if not holder:  # tiến trình khác đang tính: chờ kết quả, quá hạn thì tự tính
        deadline = time.monotonic() + FILL_WAIT_SECONDS
        while time.monotonic() < deadline:
            time.sleep(0.05)
            raw = get()
            if raw is not None:
                return raw
    try:
        # Cùng cách đổi kiểu với API (Decimal -> số, ngày -> ISO): lần trúng cache và lần tính mới trả JSON giống nhau
        raw = dumps(compute()).decode()

        def local_put():
            with _local_lock:
                if len(_local_cache) > 1000:
                    _local_cache.clear()
                _local_cache[full] = (time.monotonic() + ttl, raw)

        _call(lambda r: r.set(full, raw, ex=ttl), local_put)
        return raw
    finally:
        if holder:
            _call(lambda r: r.delete(lock_key), lambda: None)
