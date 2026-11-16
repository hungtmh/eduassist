"""Chống quá tải và chống kẹt: kiểm soát cửa vào của MỘT tiến trình API.

Hai lỗi đã gặp khi test tải (loadtest/api.js), cả hai làm API treo hẳn chứ không chỉ chậm:

1. Mỗi request giữ 1 kết nối DB (dependency `db`) rồi xin thêm kết nối để kiểm tra đăng nhập từ CÙNG pool.
   -> đã sửa bằng auth_pool riêng (eduassist.db).
2. Kẹt giữa thread pool và pool kết nối: request đi qua nhiều bước (lấy kết nối, kiểm tra đăng nhập, chạy
   endpoint), mỗi bước mượn một luồng rồi trả. Khi đông, các request ĐÃ có kết nối chờ luồng để chạy tiếp,
   còn mọi luồng lại bị các request đang chờ kết nối chiếm -> không ai nhả, cứ 5 giây lỗi một loạt.

Cách chặn (2): số request được chạy cùng lúc luôn nhỏ hơn số luồng (max_concurrent + phần chừa cho chat <
thread_pool_size, config.py kiểm tra lúc khởi động), nên luôn còn luồng trống cho request đang giữ kết nối chạy
tiếp. Request vượt trần xếp hàng NGAY TRÊN EVENT LOOP (không tốn luồng, không tốn kết nối) tối đa queue_timeout
giây; hàng đầy hoặc chờ quá lâu thì trả 503 ngay - từ chối nhanh để phần còn lại vẫn chạy và hệ thống tự hồi phục
khi hết tải.

Luồng chat trả lời dần (SSE) kéo dài nhiều giây nên có ngăn riêng (max_streams), không chiếm chỗ của trang thường.
Chat đã async nên một luồng chat chỉ mượn luồng vài mili-giây; ngăn này giới hạn bộ nhớ / kết nối mở, còn số lượt gọi
LLM cùng lúc của toàn hệ thống do eduassist.cache.llm_slots giới hạn.

Viết dạng ASGI thuần (không dùng BaseHTTPMiddleware) để không chặn SSE. Bộ đếm chỉ đổi trên event loop
(một luồng) nên không cần khoá.
"""

import asyncio
import json

# Bản đang chạy của tiến trình (Starlette tự tạo middleware lúc dựng app) - /metrics đọc số liệu ở đây
current: "AdmissionControl | None" = None

# Không đi qua cửa: kiểm tra "còn sống" phải luôn trả lời được
EXEMPT_PATHS = frozenset({"/health/live", "/metrics"})
# Trả lời dần (SSE): giữ kết nối lâu, tính ở ngăn riêng
STREAM_PATHS = frozenset({"/chat", "/chat/resume", "/public/chat"})

_BODY = json.dumps({"detail": "Hệ thống đang quá tải, bạn thử lại sau vài giây."}, ensure_ascii=False).encode()


class AdmissionControl:
    def __init__(
        self,
        app,
        max_concurrent: int,
        max_queue: int = 500,
        queue_timeout: float = 3.0,
        max_streams: int = 40,
    ):
        self.app = app
        self.max_concurrent = max_concurrent
        self.max_queue = max_queue
        self.queue_timeout = queue_timeout
        self.max_streams = max_streams
        self._slots = asyncio.Semaphore(max(max_concurrent, 1))
        # Số liệu để theo dõi (đọc qua /health/live?detail hoặc log)
        self.active = 0
        self.waiting = 0
        self.streams = 0
        self.rejected = 0
        global current
        current = self

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] != "http" or path in EXEMPT_PATHS or self.max_concurrent <= 0:
            await self.app(scope, receive, send)
            return
        if path in STREAM_PATHS:
            await self._stream(scope, receive, send)
            return
        if self._slots.locked() and self.waiting >= self.max_queue:
            await self._reject(send)
            return
        self.waiting += 1
        try:
            async with asyncio.timeout(self.queue_timeout):
                await self._slots.acquire()
        except TimeoutError:
            await self._reject(send)
            return
        finally:
            self.waiting -= 1
        self.active += 1
        try:
            await self.app(scope, receive, send)
        finally:
            self.active -= 1
            self._slots.release()

    async def _stream(self, scope, receive, send):
        if self.streams >= self.max_streams:
            await self._reject(send)
            return
        self.streams += 1
        try:
            await self.app(scope, receive, send)
        finally:
            self.streams -= 1

    async def _reject(self, send) -> None:
        self.rejected += 1
        await send(
            {
                "type": "http.response.start",
                "status": 503,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", b"2"),
                    (b"content-length", str(len(_BODY)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _BODY})

    def stats(self) -> dict:
        return {"active": self.active, "waiting": self.waiting, "streams": self.streams, "rejected": self.rejected}
