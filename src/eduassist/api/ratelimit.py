"""Rate limit theo user (cửa sổ trượt 60 giây), lưu trong RAM.

Đủ cho 1 instance. Chạy nhiều instance thì chuyển sang Redis (cùng thuật toán, đổi nơi lưu).
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, status


class RateLimiter:
    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) >= self.per_minute:
                retry = int(60 - (now - hits[0])) + 1
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    f"Bạn gửi quá nhiều yêu cầu. Thử lại sau {retry} giây.",
                    headers={"Retry-After": str(retry)},
                )
            hits.append(now)
