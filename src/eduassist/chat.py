"""Lớp dịch vụ: chạy MỘT lượt hội thoại và chuẩn hoá stream của LangGraph thành sự kiện đơn giản.

API (SSE) dùng bản async astream_turn; CLI và bộ eval dùng bản đồng bộ stream_turn. Hai bản dùng chung cách đổi sự
kiện (_Turn) nên hành vi giống hệt nhau.

Bản async (API) có thêm ba giới hạn để LLM chậm / lỗi không kéo sập hệ thống:
- tối đa chat_turn_timeout_seconds giây mỗi câu, kể cả mọi lần thử lại và model dự phòng;
- tối đa llm_max_concurrent lượt chat đang chạy trên toàn hệ thống (Redis), đầy thì báo bận NGAY, không xếp hàng;
- người dùng đóng trình duyệt thì generator bị đóng -> huỷ luôn lời gọi LLM đang chờ.

Sự kiện:
  {"type": "step", "step": ...} tiến trình (agent_start/agent_end, sql, retrieval, courses, action, memory)
  {"type": "token", "text"}    từng mẩu chữ của câu trả lời cuối
  {"type": "interrupt", "actions": [...]}   cần người duyệt; gọi lại với resume=...
  {"type": "done", "answer", "sources"}   kết thúc lượt (sources = nguồn tài liệu đã kiểm chứng)
  {"type": "error", "message"} lỗi (đã ẩn chi tiết kỹ thuật)
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Iterator
from typing import Any

from langgraph.types import Command

from eduassist.agents.context import UserContext
from eduassist.agents.supervisor import abuild_supervisor, build_supervisor
from eduassist.config import get_settings
from eduassist.observability import tracing_callbacks, tracing_metadata

log = logging.getLogger("eduassist.chat")


def _config(ctx: UserContext) -> dict:
    return {
        "configurable": {"thread_id": ctx.thread_id},
        "callbacks": tracing_callbacks(ctx),
        "metadata": {"user_id": ctx.user_id, "role": ctx.role, "run_id": ctx.run_id, **tracing_metadata(ctx)},
        "recursion_limit": 50,
    }


def _interrupt_actions(interrupts) -> list[dict]:
    # Với subgraphs=True, cùng một interrupt được báo ở cả namespace agent con lẫn supervisor -> lọc trùng theo id
    unique = {getattr(it, "id", id(it)): it for it in interrupts}
    actions = []
    for it in unique.values():
        value = it.value if hasattr(it, "value") else it
        for req in (value or {}).get("action_requests", []):
            actions.append({"name": req["name"], "args": req["args"], "description": req.get("description", "")})
    return actions


ERROR_MESSAGE = "Xin lỗi, hệ thống đang gặp sự cố khi xử lý yêu cầu. Bạn thử lại sau ít phút nhé."
BUSY_MESSAGE = "Trợ lý đang trả lời nhiều người cùng lúc. Bạn thử lại sau khoảng nửa phút nhé."
TIMEOUT_MESSAGE = "Câu hỏi này mất quá nhiều thời gian để trả lời. Bạn thử hỏi ngắn gọn hơn hoặc thử lại sau nhé."


def _payload(message: str | None, resume: list[dict] | None) -> Any:
    if resume is not None:
        return Command(resume={"decisions": resume})
    return {"messages": [{"role": "user", "content": message}]}


class _Turn:
    """Đổi từng phần tử stream của LangGraph thành sự kiện cho giao diện, gom câu trả lời / nguồn / interrupt."""

    def __init__(self):
        self.answer_parts: list[str] = []
        self.sources: list[str] = []
        self.interrupts: list = []

    def handle(self, namespace, mode, data) -> dict | None:
        if mode == "custom":
            if data.get("type") == "sources":
                self.sources.extend(s for s in data["items"] if s not in self.sources)
            return {"type": "step", "step": data.get("type"), **{k: v for k, v in data.items() if k != "type"}}
        if mode == "messages":
            chunk, meta = data
            # Chỉ stream chữ của supervisor (namespace rỗng), không stream suy nghĩ nội bộ của agent con
            if not namespace and meta.get("langgraph_node") == "model" and chunk.content:
                text = chunk.content if isinstance(chunk.content, str) else ""
                if text:
                    self.answer_parts.append(text)
                    return {"type": "token", "text": text}
        elif mode == "updates" and "__interrupt__" in data:
            self.interrupts.extend(data["__interrupt__"])
        return None

    @property
    def answer(self) -> str:
        return "".join(self.answer_parts)


def _last_message(state) -> str:
    msgs = state.values.get("messages", [])
    return msgs[-1].content if msgs else ""


_STREAM = {"stream_mode": ["custom", "messages", "updates"], "subgraphs": True}


def stream_turn(ctx: UserContext, message: str | None = None, resume: list[dict] | None = None) -> Iterator[dict]:
    """Bản đồng bộ (CLI, eval). message: câu hỏi mới. resume: [{"type": "approve"} | {"type": "reject", ...}]."""
    graph = build_supervisor(ctx.role)
    config = _config(ctx)
    turn = _Turn()
    try:
        for namespace, mode, data in graph.stream(_payload(message, resume), config, context=ctx, **_STREAM):
            ev = turn.handle(namespace, mode, data)
            if ev:
                yield ev
    except Exception:
        log.exception("turn failed user=%s thread=%s", ctx.user_id, ctx.thread_id)
        yield {"type": "error", "message": ERROR_MESSAGE}
        return
    if turn.interrupts:
        yield {"type": "interrupt", "actions": _interrupt_actions(turn.interrupts)}
        return
    answer = turn.answer
    if not answer:  # VD: model dự phòng không stream được -> lấy từ state
        answer = _last_message(graph.get_state(config))
        if answer:
            yield {"type": "token", "text": answer}
    yield {"type": "done", "answer": answer, "sources": turn.sources}


async def astream_turn(
    ctx: UserContext, message: str | None = None, resume: list[dict] | None = None
) -> AsyncIterator[dict]:
    """Bản async cho API: chờ LLM không giữ luồng nào. Cùng sự kiện với stream_turn."""
    from eduassist import cache

    slots = cache.llm_slots()
    slot = await asyncio.to_thread(slots.acquire)  # Redis: vài mili-giây, tối đa redis_timeout
    if slot is None:
        log.warning("hết chỗ chat LLM (%s lượt đang chạy) user=%s", slots.limit, ctx.user_id)
        yield {"type": "error", "message": BUSY_MESSAGE, "code": "busy"}
        return
    turn = _Turn()
    try:
        graph = await abuild_supervisor(ctx.role)
        config = _config(ctx)
        async with asyncio.timeout(get_settings().chat_turn_timeout_seconds):
            async for namespace, mode, data in graph.astream(_payload(message, resume), config, context=ctx, **_STREAM):
                ev = turn.handle(namespace, mode, data)
                if ev:
                    yield ev
            if turn.interrupts:
                yield {"type": "interrupt", "actions": _interrupt_actions(turn.interrupts)}
                return
            answer = turn.answer
            if not answer:
                answer = _last_message(await graph.aget_state(config))
                if answer:
                    yield {"type": "token", "text": answer}
        yield {"type": "done", "answer": answer, "sources": turn.sources}
    except TimeoutError:
        log.warning(
            "chat quá %ss user=%s thread=%s", get_settings().chat_turn_timeout_seconds, ctx.user_id, ctx.thread_id
        )
        yield {"type": "error", "message": TIMEOUT_MESSAGE, "code": "timeout"}
    except Exception:
        log.exception("turn failed user=%s thread=%s", ctx.user_id, ctx.thread_id)
        yield {"type": "error", "message": ERROR_MESSAGE}
    finally:
        # Chạy cả khi người dùng đóng trình duyệt (generator bị đóng giữa chừng): trả chỗ ngay, không chờ hết hạn thuê
        await asyncio.shield(asyncio.to_thread(slots.release, slot))


def pending_actions(ctx: UserContext) -> list[dict]:
    """Thao tác đang chờ duyệt của thread (VD: người dùng tải lại trang)."""
    state = build_supervisor(ctx.role).get_state(_config(ctx), subgraphs=True)
    return _interrupt_actions(state.interrupts) if state.interrupts else []


def thread_history(ctx: UserContext) -> list[dict]:
    state = build_supervisor(ctx.role).get_state(_config(ctx))
    out = []
    for m in state.values.get("messages", []):
        if m.type == "human":
            out.append({"role": "user", "content": m.content})
        elif m.type == "ai" and m.content and not m.tool_calls:
            out.append({"role": "assistant", "content": m.content})
    return out
