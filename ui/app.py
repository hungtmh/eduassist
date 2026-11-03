"""Giao diện chat EduAssist (Chainlit). UI chỉ là CLIENT của FastAPI - không chứa logic agent.

uv run --group ui chainlit run ui/app.py --port 8001
"""

import json
import os
import uuid
from contextlib import suppress

import chainlit as cl
import httpx

# UI chỉ gọi API, không đụng database. Chainlit thấy DATABASE_URL (đọc chung file .env) sẽ tự bật
# data layer riêng của nó -> gỡ biến này để UI không bao giờ có quyền vào DB.
os.environ.pop("DATABASE_URL", None)

API_URL = os.environ.get("API_URL", "http://localhost:8000")
TIMEOUT = httpx.Timeout(300, connect=10)

AGENT_LABEL = {"advisor": "Tư vấn (RAG)", "analytics": "Phân tích dữ liệu (SQL)", "action": "Vận hành"}
ACTION_LABEL = {
    "send_email": "Gửi email",
    "create_voucher": "Cấp mã giảm giá",
    "send_payment_reminders": "Gửi email nhắc nợ",
}
ROLE_LABEL = {"student": "Học viên", "staff": "Nhân viên", "manager": "Quản lý"}


@cl.password_auth_callback
async def auth(username: str, password: str) -> cl.User | None:
    async with httpx.AsyncClient(base_url=API_URL, timeout=TIMEOUT) as client:
        try:
            r = await client.post("/auth/login", json={"username": username, "password": password})
        except httpx.HTTPError:
            return None
    if r.status_code != 200:
        return None
    data = r.json()
    return cl.User(
        identifier=data["user"]["username"],
        display_name=data["user"]["display_name"],
        metadata={"token": data["access_token"], "role": data["user"]["role"]},
    )


@cl.on_chat_start
async def start():
    user = cl.user_session.get("user")
    cl.user_session.set("conversation_id", uuid.uuid4().hex[:12])
    role = user.metadata["role"]
    hint = {
        "student": "Hỏi mình về khoá học, học phí, ưu đãi, hoàn tiền, lịch khai giảng, hoặc các lớp bạn đã đăng ký.",
        "staff": "Bạn có thể hỏi số liệu (doanh thu, công nợ...), tư vấn chính sách, hoặc yêu cầu gửi email / "
        "cấp voucher - mọi thao tác sẽ chờ bạn duyệt.",
    }.get(role, "")
    hint = hint or "Bạn có quyền như nhân viên, kèm mức voucher tối đa 30%."
    await cl.Message(f"Chào **{user.display_name}** ({ROLE_LABEL[role]}). {hint}").send()


def _headers() -> dict:
    return {"Authorization": f"Bearer {cl.user_session.get('user').metadata['token']}"}


async def _stream(path: str, body: dict) -> list[tuple[str, dict]]:
    """Gọi API SSE, hiển thị tiến trình (Step) + chữ chạy. Trả về danh sách sự kiện."""
    events: list[tuple[str, dict]] = []
    answer: cl.Message | None = None  # tạo khi có chữ đầu tiên -> nằm SAU các bước tiến trình
    # Giữ step qua các lần resume trong cùng một lượt -> không hiện trùng "Vận hành" sau khi duyệt
    steps: dict[str, cl.Step] = cl.user_session.get("steps")
    async with (
        httpx.AsyncClient(base_url=API_URL, timeout=TIMEOUT, headers=_headers()) as client,
        client.stream("POST", path, json=body) as r,
    ):
        if r.status_code != 200:
            detail = (await r.aread()).decode()
            with suppress(ValueError, KeyError):
                detail = json.loads(detail)["detail"]
            await cl.Message(f"⚠️ {detail}").send()
            return events
        event = None
        async for line in r.aiter_lines():
            if line.startswith("event: "):
                event = line[7:]
                continue
            if not line.startswith("data: "):
                continue
            data = json.loads(line[6:])
            events.append((event, data))
            if event == "meta":
                cl.user_session.set("run_id", data["run_id"])
            elif event == "step":
                await _render_step(data, steps)
            elif event == "token":
                if answer is None:
                    answer = cl.Message(content="")
                await answer.stream_token(data["text"])
            elif event == "error":
                await cl.Message(f"⚠️ {data['message']}").send()
    for step in steps.values():
        await step.update()
    done = next((d for e, d in events if e == "done"), None)
    if done is not None:
        answer = answer or cl.Message(content=done.get("answer", ""))
        if done.get("sources"):
            answer.content += "\n\n---\n**Nguồn tài liệu:**\n" + "\n".join(f"- {s}" for s in done["sources"])
        answer.actions = [
            cl.Action(name="feedback", payload={"score": 1}, label="👍 Hữu ích", tooltip="Câu trả lời đúng"),
            cl.Action(name="feedback", payload={"score": -1}, label="👎 Chưa đúng", tooltip="Câu trả lời sai"),
        ]
        await answer.send()
    return events


async def _render_step(data: dict, steps: dict[str, cl.Step]) -> None:
    kind = data.get("step")
    if kind == "agent_start":
        agent = data["agent"]
        if agent in steps:  # resume sau khi duyệt: agent chạy lại từ checkpoint, giữ nguyên step cũ
            return
        step = cl.Step(name=AGENT_LABEL.get(agent, agent), type="tool", show_input=False)
        step.output = ""
        await step.send()
        steps[agent] = step
        return
    current = next(reversed(steps.values()), None) if steps else None
    if current is None:
        return
    if kind == "sql":
        if data["status"] == "ok":
            current.output += f"\n✅ SQL chạy thành công ({data['rows']} dòng)\n```sql\n{data['sql']}\n```\n"
        elif data["status"] in ("rejected", "error"):
            current.output += f"\n⛔ SQL bị {'chặn' if data['status'] == 'rejected' else 'lỗi'}: {data['error']}\n"
    elif kind == "retrieval":
        current.output += f"\n🔎 Tra tài liệu: *{data['query']}*\n"
    elif kind == "courses":
        current.output += "\n📚 Tra danh sách khoá học\n"
    elif kind == "action":
        n = f" ({data['recipients']} người nhận)" if data.get("recipients") else ""
        current.output += f"\n⚙️ Đã thực hiện: {ACTION_LABEL.get(data['action'], data['action'])}{n}\n"
    elif kind == "memory":
        current.output += f"\n🧠 Ghi nhớ: {data['fact']}\n"
    elif kind == "agent_end":
        await current.update()
        return
    await current.update()


def _describe(action: dict) -> str:
    args = action["args"]
    if action["name"] == "send_payment_reminders" and action.get("description"):
        return action["description"]  # server soạn sẵn: số người nhận, tổng nợ, email mẫu
    if action["name"] == "send_email":
        return (
            f"**Gửi email** tới {', '.join(args.get('recipients', []))}\n\n"
            f"**Tiêu đề:** {args.get('subject', '')}\n\n> " + args.get("body", "").replace("\n", "\n> ")
        )
    if action["name"] == "create_voucher":
        return (
            f"**Cấp voucher** giảm **{args.get('phan_tram')}%** cho học viên id **{args.get('hoc_vien_id')}**"
            f"\n\nLý do: {args.get('ly_do', '')}"
        )
    return f"**{action['name']}**: `{json.dumps(args, ensure_ascii=False)}`"


async def _handle_interrupts(events: list[tuple[str, dict]]) -> None:
    """Nếu agent dừng chờ duyệt: hỏi từng thao tác, gửi quyết định, lặp tới khi xong."""
    while events and events[-1][0] == "interrupt":
        decisions = []
        for action in events[-1][1]["actions"]:
            res = await cl.AskActionMessage(
                content="🛑 **Cần bạn duyệt trước khi thực hiện**\n\n" + _describe(action),
                actions=[
                    cl.Action(name="approve", payload={"type": "approve"}, label="✅ Duyệt"),
                    cl.Action(name="reject", payload={"type": "reject"}, label="❌ Từ chối"),
                ],
                timeout=600,
            ).send()
            approved = res is not None and res.get("payload", {}).get("type") == "approve"
            decisions.append({"type": "approve"} if approved else {"type": "reject", "message": "Người dùng từ chối"})
        events = await _stream(
            "/chat/resume",
            {
                "conversation_id": cl.user_session.get("conversation_id"),
                "run_id": cl.user_session.get("run_id"),
                "decisions": decisions,
            },
        )


@cl.on_message
async def on_message(message: cl.Message):
    cl.user_session.set("steps", {})
    events = await _stream(
        "/chat", {"message": message.content, "conversation_id": cl.user_session.get("conversation_id")}
    )
    await _handle_interrupts(events)


@cl.action_callback("feedback")
async def on_feedback(action: cl.Action):
    body = {
        "conversation_id": cl.user_session.get("conversation_id"),
        "run_id": cl.user_session.get("run_id"),
        "score": action.payload["score"],
    }
    async with httpx.AsyncClient(base_url=API_URL, timeout=TIMEOUT, headers=_headers()) as client:
        r = await client.post("/feedback", json=body)
    if r.status_code == 200:
        promoted = r.json().get("promoted_sql_examples", [])
        note = " Câu SQL đã được thêm vào kho ví dụ để agent học." if promoted else ""
        await cl.Message(f"Cảm ơn phản hồi của bạn!{note}").send()
    await action.remove()
