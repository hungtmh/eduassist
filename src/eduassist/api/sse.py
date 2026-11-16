"""Trả sự kiện chat dạng Server-Sent Events.

Nhận cả async iterator (chat thật: chờ LLM không giữ luồng) lẫn iterator thường (bản giả trong test). Khi người dùng
đóng trình duyệt, Starlette dừng đọc; ở đây đóng hẳn generator (aclose) ngay để huỷ lời gọi LLM đang chờ và trả chỗ
trong giới hạn số lượt chat, không đợi bộ dọn rác.
"""

import json
from collections.abc import AsyncIterator, Iterable

from fastapi.responses import StreamingResponse

HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}  # proxy không gom đệm, chữ hiện ngay


def _frame(ev: dict) -> str:
    return f"event: {ev['type']}\ndata: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"


def sse_response(events: AsyncIterator[dict] | Iterable[dict], meta: dict | None = None) -> StreamingResponse:
    head = f"event: meta\ndata: {json.dumps(meta)}\n\n" if meta is not None else None

    if hasattr(events, "__aiter__"):

        async def agen():
            try:
                if head:
                    yield head
                async for ev in events:
                    yield _frame(ev)
            finally:
                await events.aclose()

        body = agen()
    else:

        def gen():
            if head:
                yield head
            for ev in events:
                yield _frame(ev)

        body = gen()
    return StreamingResponse(body, media_type="text/event-stream", headers=HEADERS)
