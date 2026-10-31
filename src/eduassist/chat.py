"""Lớp dịch vụ: chạy MỘT lượt hội thoại và chuẩn hoá stream của LangGraph thành sự kiện đơn giản.

API (SSE), CLI và bộ eval đều dùng chung hàm này -> hành vi giống hệt nhau ở mọi nơi.

Sự kiện:
  {"type": "step", "step": ...} tiến trình (agent_start/agent_end, sql, retrieval, courses, action, memory)
  {"type": "token", "text"}    từng mẩu chữ của câu trả lời cuối
  {"type": "interrupt", "actions": [...]}   cần người duyệt; gọi lại với resume=...
  {"type": "done", "answer", "sources"}   kết thúc lượt (sources = nguồn tài liệu đã kiểm chứng)
  {"type": "error", "message"} lỗi (đã ẩn chi tiết kỹ thuật)
"""

import logging
from collections.abc import Iterator
from typing import Any

from langgraph.types import Command

from eduassist.agents.context import UserContext
from eduassist.agents.supervisor import build_supervisor
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
            actions.append({"name": req["name"], "args": req["args"]})
    return actions


def stream_turn(ctx: UserContext, message: str | None = None, resume: list[dict] | None = None) -> Iterator[dict]:
    """message: câu hỏi mới. resume: danh sách quyết định [{"type": "approve"} | {"type": "reject", "message"}]."""
    graph = build_supervisor(ctx.role)
    config = _config(ctx)
    payload: Any = (
        Command(resume={"decisions": resume})
        if resume is not None
        else {"messages": [{"role": "user", "content": message}]}
    )
    answer_parts: list[str] = []
    sources: list[str] = []
    interrupts = []
    try:
        for namespace, mode, data in graph.stream(
            payload, config, context=ctx, stream_mode=["custom", "messages", "updates"], subgraphs=True
        ):
            if mode == "custom":
                if data.get("type") == "sources":
                    sources.extend(s for s in data["items"] if s not in sources)
                yield {"type": "step", "step": data.get("type"), **{k: v for k, v in data.items() if k != "type"}}
            elif mode == "messages":
                chunk, meta = data
                # Chỉ stream chữ của supervisor (namespace rỗng), không stream suy nghĩ nội bộ của agent con
                if not namespace and meta.get("langgraph_node") == "model" and chunk.content:
                    text = chunk.content if isinstance(chunk.content, str) else ""
                    if text:
                        answer_parts.append(text)
                        yield {"type": "token", "text": text}
            elif mode == "updates" and "__interrupt__" in data:
                interrupts.extend(data["__interrupt__"])
    except Exception:
        log.exception("turn failed user=%s thread=%s", ctx.user_id, ctx.thread_id)
        yield {
            "type": "error",
            "message": "Xin lỗi, hệ thống đang gặp sự cố khi xử lý yêu cầu. Bạn thử lại sau ít phút nhé.",
        }
        return

    if interrupts:
        yield {"type": "interrupt", "actions": _interrupt_actions(interrupts)}
        return
    answer = "".join(answer_parts)
    if not answer:  # VD: model dự phòng không stream được -> lấy từ state
        msgs = graph.get_state(config).values.get("messages", [])
        answer = msgs[-1].content if msgs else ""
        if answer:
            yield {"type": "token", "text": answer}
    yield {"type": "done", "answer": answer, "sources": sources}


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
