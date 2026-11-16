"""Supervisor: nhận câu hỏi, giao cho agent con phù hợp, tổng hợp câu trả lời.

PHÂN QUYỀN NẰM Ở ĐÂY, TRONG CODE: mỗi vai trò có một graph riêng chỉ chứa các tool được phép.
Học viên không có tool ask_analytics / ask_action, nên dù prompt injection thế nào LLM cũng
không thể gọi tới - tool đó đơn giản là không tồn tại trong graph của họ.

Mỗi graph có hai bản cùng tool, cùng middleware: build_supervisor (đồng bộ: CLI, eval) và abuild_supervisor (async:
chat của API). Tool giao việc cho agent con có cả hai cách chạy: bản async `await agent.ainvoke(...)` nên một lượt chat
chờ LLM không giữ luồng nào; tool lá (SQL, RAG) vẫn là hàm thường, LangChain chạy chúng trong thread pool vài mili-giây.
"""

import asyncio
import uuid
from functools import lru_cache

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelRequest, PIIMiddleware, ToolCallLimitMiddleware
from langchain.tools import ToolRuntime
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool

from eduassist.agents.action import build_action_agent
from eduassist.agents.advisor import build_advisor_agent
from eduassist.agents.analytics import build_analytics_agent, task_with_examples
from eduassist.agents.context import ROLE_LABEL, Role, UserContext, emit
from eduassist.agents.persistence import get_async_checkpointer, get_checkpointer, get_store, memory_namespace
from eduassist.config import get_settings
from eduassist.db import app_pool
from eduassist.formatting import fold, is_refusal
from eduassist.llm import chat_model, resilience_middleware
from eduassist.services.core import today

MAX_MEMORIES_IN_PROMPT = 10

BASE_PROMPT = """Bạn là EduAssist, trợ lý AI của Trung tâm Đào tạo Ánh Dương (dữ liệu demo). Hôm nay là {today}.
Người dùng: {name} - vai trò: {role}.

Bạn KHÔNG tự trả lời kiến thức về trung tâm từ trí nhớ; hãy giao việc cho đúng agent qua tool:
{tool_guide}
Có thể gọi nhiều tool lần lượt cho một câu hỏi. Câu chào hỏi, cảm ơn thì trả lời trực tiếp, không cần tool.
Giao việc bằng NGÔN NGỮ TỰ NHIÊN, đầy đủ ngữ cảnh. KHÔNG tự viết SQL - agent con tự biết cấu trúc dữ liệu.
Người dùng đã yêu cầu thao tác (gửi email, cấp voucher, nhắc nợ) thì gọi ask_action luôn, KHÔNG hỏi lại "có muốn
gửi không": agent vận hành tạo ĐỀ XUẤT và giao diện tự hiện thẻ Duyệt / Từ chối cho người dùng.
Mỗi thao tác chỉ làm MỘT lần: phần "KẾT QUẢ THAO TÁC" trong kết quả ask_action là sự thật - đã tạo đề xuất #N
thì báo lại số đề xuất và trạng thái, TUYỆT ĐỐI không gọi lại ask_action cho cùng việc đó.
Khi nhận kết quả từ agent con: chuyển tiếp trung thực, GIỮ NGUYÊN bảng số liệu và câu SQL;
không thêm con số hay chính sách nào không có trong kết quả. Không cần chép lại dòng "Nguồn: ..." -
giao diện tự hiển thị nguồn tài liệu đã được kiểm chứng.
Người dùng chia sẻ thông tin hữu ích lâu dài về bản thân (mục tiêu học, trình độ, lịch rảnh, con học lớp mấy...)
thì gọi remember_user_fact để lần sau tư vấn tốt hơn.
Yêu cầu vượt quyền của vai trò hiện tại: nói rõ là bạn không có quyền thực hiện, không cố làm vòng.

Điều đã biết về người dùng (từ các cuộc trò chuyện trước):
{memories}"""

TOOL_GUIDE = {
    "ask_advisor": "- ask_advisor: chính sách, học phí, ưu đãi, khoá học, lịch khai giảng, tư vấn lộ trình.",
    "ask_advisor_student": "- ask_advisor: chính sách, học phí, ưu đãi, khoá học, lịch khai giảng, tư vấn lộ trình,"
    " các lớp chính người dùng đã đăng ký và học phí còn nợ.",
    "ask_analytics": "- ask_analytics: số liệu kinh doanh, doanh thu, công nợ, danh sách học viên/lớp"
    " (có id; email và SĐT được che).",
    "ask_action": "- ask_action: gửi email, cấp mã giảm giá, NHẮC NỢ HỌC PHÍ. Nhắc nợ: gọi ask_action THẲNG"
    " (agent vận hành tự tính công nợ, tự gửi từng người) - KHÔNG hỏi ask_analytics lấy danh sách trước,"
    " KHÔNG chép danh sách người nợ vào task; chỉ truyền phạm vi (tất cả / hoc_vien_id cụ thể) và hạn thanh toán"
    " nếu người dùng có nói. Việc khác: truyền ĐỦ người nhận (hoc_vien_id / id khách; email chỉ khi người dùng"
    " tự gõ), nội dung, mức giảm;"
    " cần tra danh sách người nhận thì hỏi ask_analytics TRƯỚC.",
}


def _subagent_answer(name: str, result: dict) -> str:
    answer = result["messages"][-1].content
    emit("agent_end", agent=name)
    if name == "action":
        # Thao tác có tác động thật: supervisor phải thấy KẾT QUẢ GỐC của tool, không chỉ lời tóm tắt của LLM.
        # (Đã gặp: tool báo "Đã gửi 153 email" nhưng LLM tóm tắt "chờ duyệt" -> supervisor gửi lại lần nữa.)
        done = [m.content for m in result["messages"] if m.type == "tool" and m.name != "get_student_contacts"]
        if done:
            answer += "\n\nKẾT QUẢ THAO TÁC (do hệ thống ghi, đây là sự thật):\n" + "\n".join(f"- {d}" for d in done)
    # Ngoài ra chỉ trả câu trả lời CUỐI: context của supervisor gọn, không lẫn các bước nội bộ của agent con
    return answer


def _run_subagent(name: str, agent, task: str, runtime: ToolRuntime[UserContext]) -> str:
    emit("agent_start", agent=name, task=task)
    result = agent.invoke({"messages": [{"role": "user", "content": task}]}, context=runtime.context)
    return _subagent_answer(name, result)


async def _arun_subagent(name: str, agent, task: str, runtime: ToolRuntime[UserContext]) -> str:
    emit("agent_start", agent=name, task=task)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": task}]}, context=runtime.context)
    return _subagent_answer(name, result)


def _also_async(sync_tool, coroutine):
    """Gắn bản async cho tool: graph async gọi coroutine, graph đồng bộ gọi hàm thường."""
    sync_tool.coroutine = coroutine
    return sync_tool


@lru_cache
def _subagents(for_student: bool) -> dict:
    return {
        "advisor": build_advisor_agent(for_student),
        "analytics": build_analytics_agent(),
        "action": build_action_agent(),
    }


def verified_sources(answer: str) -> list[str]:
    """Các nguồn agent tư vấn đã trích, CHỈ gồm nguồn có thật trong policy_chunks (chống trích dẫn bịa).

    Không parse theo định dạng: LLM ghi nguồn đủ kiểu ("Nguồn: x", "(nguồn: x)", chép cả thẻ <tai_lieu nguon="x">,
    sửa tên file thành có dấu). Thay vào đó tìm từng nguồn có thật trong câu trả lời đã bỏ dấu/ký tự đặc biệt,
    sắp theo vị trí xuất hiện.
    """
    text = fold(answer)
    found = [(text.find(key), name) for key, name in known_sources().items() if key in text]
    return [name for _, name in sorted(found)]


@lru_cache
def known_sources() -> dict[str, str]:
    """{dạng-bỏ-dấu: tên nguồn chuẩn} của mọi mục tài liệu đang có trong pgvector."""
    with app_pool().connection() as conn:
        rows = conn.execute("SELECT DISTINCT source, section FROM policy_chunks").fetchall()
    names = (f"{r['source']} › {r['section'].split(' › ')[-1]}" for r in rows)
    return {fold(n): n for n in names}


def _record_gap(question: str, ctx: UserContext) -> None:
    with app_pool().connection() as conn:
        conn.execute(
            "INSERT INTO knowledge_gap (question, user_id, role) VALUES (%s, %s, %s)",
            (question, ctx.user_id, ctx.role),
        )


def _advisor_followup(answer: str) -> bool:
    """Gửi nguồn đã kiểm chứng cho giao diện; trả True nếu là câu từ chối (lỗ hổng tài liệu cần ghi lại)."""
    sources = verified_sources(answer)
    if sources:
        emit("sources", items=sources)
    return is_refusal(answer)


@tool
def ask_advisor(question: str, runtime: ToolRuntime[UserContext]) -> str:
    """Hỏi agent tư vấn về chính sách, học phí, ưu đãi, khoá học, lịch khai giảng, lộ trình học.
    Truyền câu hỏi đầy đủ ngữ cảnh (VD: đối tượng, mục tiêu, thời gian rảnh)."""
    agent = _subagents(runtime.context.role == "student")["advisor"]
    answer = _run_subagent("advisor", agent, question, runtime)
    if _advisor_followup(answer):  # lỗ hổng tài liệu -> báo cáo định kỳ cho nhân viên bổ sung
        _record_gap(question, runtime.context)
    return answer


async def _ask_advisor_async(question: str, runtime: ToolRuntime[UserContext]) -> str:
    agent = _subagents(runtime.context.role == "student")["advisor"]
    answer = await _arun_subagent("advisor", agent, question, runtime)
    if _advisor_followup(answer):  # known_sources() đã cache sau lần đầu: không đụng DB
        await asyncio.to_thread(_record_gap, question, runtime.context)
    return answer


@tool
def ask_analytics(question: str, runtime: ToolRuntime[UserContext]) -> str:
    """Hỏi agent phân tích dữ liệu: doanh thu, công nợ, số lượng đăng ký, danh sách học viên/lớp.
    question là câu hỏi bằng tiếng Việt tự nhiên (KHÔNG phải SQL). Kết quả gồm bảng số liệu và câu SQL đã chạy."""
    return _run_subagent("analytics", _subagents(False)["analytics"], task_with_examples(question), runtime)


async def _ask_analytics_async(question: str, runtime: ToolRuntime[UserContext]) -> str:
    task = await asyncio.to_thread(task_with_examples, question)  # tìm ví dụ SQL tương tự: embedding + DB
    return await _arun_subagent("analytics", _subagents(False)["analytics"], task, runtime)


@tool
def ask_action(task: str, runtime: ToolRuntime[UserContext]) -> str:
    """Giao việc cho agent vận hành: gửi email, cấp mã giảm giá. Mô tả đầy đủ người nhận và nội dung.
    Thao tác sẽ chờ người dùng duyệt trước khi thực hiện."""
    return _run_subagent("action", _subagents(False)["action"], task, runtime)


async def _ask_action_async(task: str, runtime: ToolRuntime[UserContext]) -> str:
    return await _arun_subagent("action", _subagents(False)["action"], task, runtime)


@tool
def remember_user_fact(fact: str, runtime: ToolRuntime[UserContext]) -> str:
    """Ghi nhớ lâu dài MỘT thông tin ngắn về người dùng (VD: "Con đang học lớp 8, muốn học buổi tối")."""
    runtime.store.put(memory_namespace(runtime.context.user_id), str(uuid.uuid4()), {"fact": fact[:300]})
    emit("memory", fact=fact)
    return "Đã ghi nhớ."


async def _remember_user_fact_async(fact: str, runtime: ToolRuntime[UserContext]) -> str:
    await runtime.store.aput(memory_namespace(runtime.context.user_id), str(uuid.uuid4()), {"fact": fact[:300]})
    emit("memory", fact=fact)
    return "Đã ghi nhớ."


_also_async(ask_advisor, _ask_advisor_async)
_also_async(ask_analytics, _ask_analytics_async)
_also_async(ask_action, _ask_action_async)
_also_async(remember_user_fact, _remember_user_fact_async)


class SupervisorPrompt(AgentMiddleware):
    """Prompt hệ thống kèm điều đã nhớ về người dùng. Bản async đọc bộ nhớ không chặn event loop."""

    def _apply(self, request: ModelRequest, items) -> ModelRequest:
        prompt = render_supervisor_prompt(request.runtime.context, [it.value["fact"] for it in items])
        return request.override(system_message=SystemMessage(content=prompt))

    def wrap_model_call(self, request, handler):
        ns = memory_namespace(request.runtime.context.user_id)
        return handler(self._apply(request, request.runtime.store.search(ns, limit=MAX_MEMORIES_IN_PROMPT)))

    async def awrap_model_call(self, request, handler):
        ns = memory_namespace(request.runtime.context.user_id)
        items = await request.runtime.store.asearch(ns, limit=MAX_MEMORIES_IN_PROMPT)
        return await handler(self._apply(request, items))


def render_supervisor_prompt(ctx: UserContext, facts: list[str]) -> str:
    memories = "\n".join(f"- {f}" for f in facts) or "(chưa có)"
    if ctx.can_use_data_agents:
        guide = "\n".join(TOOL_GUIDE[k] for k in ("ask_advisor", "ask_analytics", "ask_action"))
    else:
        guide = TOOL_GUIDE["ask_advisor_student" if ctx.hoc_vien_id else "ask_advisor"]
    return BASE_PROMPT.format(
        today=today().isoformat(),
        name=ctx.display_name,
        role=ROLE_LABEL[ctx.role],
        tool_guide=guide,
        memories=memories,
    )


_STAFF_TOOLS = [ask_advisor, ask_analytics, ask_action, remember_user_fact]
ROLE_TOOLS = {
    "student": [ask_advisor, remember_user_fact],
    "teacher": [ask_advisor, remember_user_fact],
    "consultant": _STAFF_TOOLS,
    "academic": _STAFF_TOOLS,
    "accountant": _STAFF_TOOLS,
    "manager": _STAFF_TOOLS,
}


def _middleware(role: Role) -> list:
    middleware = [
        SupervisorPrompt(),
        *resilience_middleware(),
        ToolCallLimitMiddleware(run_limit=get_settings().max_tool_calls_per_turn),
    ]
    if role == "student":
        # Học viên không bao giờ được thấy email / SĐT (kể cả nếu lọt ra từ đâu đó) - che ở câu trả lời
        middleware += [
            PIIMiddleware("email", strategy="mask", apply_to_input=False, apply_to_output=True),
            PIIMiddleware(
                "phone_vn", detector=r"\b0\d{9}\b", strategy="mask", apply_to_input=False, apply_to_output=True
            ),
        ]
    return middleware


def _create(role: Role, checkpointer):
    return create_agent(
        chat_model(),
        tools=ROLE_TOOLS[role],
        context_schema=UserContext,
        middleware=_middleware(role),
        checkpointer=checkpointer,
        store=get_store(),
        name=f"supervisor_{role}",
    )


@lru_cache
def build_supervisor(role: Role):
    return _create(role, get_checkpointer())


_async_graphs: dict = {}


async def abuild_supervisor(role: Role):
    """Graph cho chat async: cùng tool và middleware, checkpointer async (pool async của event loop hiện tại)."""
    saver = await get_async_checkpointer()
    key = (role, id(saver))
    if key not in _async_graphs:
        _async_graphs[key] = _create(role, saver)
    return _async_graphs[key]
