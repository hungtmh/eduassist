"""Giới hạn lượt gọi cho API (cửa sổ trượt 60 giây).

Bộ đếm nằm trong Redis khi có REDIS_URL (đúng cho nhiều tiến trình / nhiều máy), không thì trong RAM - xem
eduassist/cache.py.
"""

from functools import lru_cache

from fastapi import HTTPException, status

from eduassist import cache


class RateLimiter(cache.RateLimiter):
    def check(self, key: str) -> None:
        try:
            self.hit(key)
        except cache.TooManyRequests as e:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Bạn gửi quá nhiều yêu cầu. Thử lại sau {e.retry_after} giây.",
                headers={"Retry-After": str(e.retry_after)},
            ) from None


def client_ip(request) -> str:
    """IP người gọi. Sau reverse proxy, uvicorn chạy với --proxy-headers đã thay bằng IP thật từ X-Forwarded-For."""
    return request.client.host if request.client else "unknown"


@lru_cache
def get_login_limiter() -> RateLimiter:
    """Giới hạn theo IP cho đăng nhập, quên mật khẩu, đặt lại mật khẩu (chống dò mật khẩu / spam email)."""
    from eduassist.config import get_settings

    return RateLimiter(get_settings().login_rate_per_minute, "login")
