"""Supervisor: nhận câu hỏi, giao cho agent con phù hợp, tổng hợp câu trả lời.

PHÂN QUYỀN NẰM Ở ĐÂY, TRONG CODE: mỗi vai trò có một graph riêng chỉ chứa các tool được phép.
Học viên không có tool ask_analytics / ask_action, nên dù prompt injection thế nào LLM cũng
không thể gọi tới - tool đó đơn giản là không tồn tại trong graph của họ.
"""

import re
import uuid
from datetime import date
from functools import lru_cache

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, PIIMiddleware, ToolCallLimitMiddleware, dynamic_prompt
from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from eduassist.agents.action import build_action_agent
from eduassist.agents.advisor import build_advisor_agent
from eduassist.agents.analytics import build_analytics_agent, task_with_examples
from eduassist.agents.context import ROLE_LABEL, Role, UserContext, emit
from eduassist.agents.persistence import get_checkpointer, get_store, memory_namespace
from eduassist.config import get_settings
from eduassist.db import app_pool
from eduassist.formatting import fold, is_refusal
from eduassist.llm import chat_model, resilience_middleware

MAX_MEMORIES_IN_PROMPT = 10

BASE_PROMPT = """Bạn là EduAssist, trợ lý AI của Trung tâm Đào tạo Ánh Dương (dữ liệu demo). Hôm nay là {today}.
Người dùng: {name} - vai trò: {role}.

Bạn KHÔNG tự trả lời kiến thức về trung tâm từ trí nhớ; hãy giao việc cho đúng agent qua tool:
{tool_guide}
Có thể gọi nhiều tool lần lượt cho một câu hỏi. Câu chào hỏi, cảm ơn thì trả lời trực tiếp, không cần tool.
Giao việc bằng NGÔN NGỮ TỰ NHIÊN, đầy đủ ngữ cảnh. KHÔNG tự viết SQL - agent con tự biết cấu trúc dữ liệu.
Người dùng đã yêu cầu thao tác (gửi email, cấp voucher) thì gọi ask_action luôn, KHÔNG hỏi lại "có muốn gửi không":
hệ thống sẽ tự hiện nút Duyệt / Từ chối cho người dùng trước khi thao tác thực sự chạy.
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
    "ask_analytics": "- ask_analytics: số liệu kinh doanh, doanh thu, công nợ, danh sách học viên/lớp (có id, email).",
    "ask_action": "- ask_action: gửi email, cấp mã giảm giá. Truyền ĐỦ thông tin: người nhận (email hoặc hoc_vien_id),"
    " nội dung, mức giảm. Cần danh sách người nhận thì hỏi ask_analytics TRƯỚC.",
}


def _run_subagent(name: str, agent, task: str, runtime: ToolRuntime[UserContext]) -> str:
    emit("agent_start", agent=name, task=task)
    result = agent.invoke({"messages": [{"role": "user", "content": task}]}, context=runtime.context)
    answer = result["messages"][-1].content
    emit("agent_end", agent=name)
    # Chỉ trả câu trả lời CUỐI: context của supervisor gọn, không lẫn các bước nội bộ của agent con
    return answer


@lru_cache
def _subagents(for_student: bool) -> dict:
    return {
        "advisor": build_advisor_agent(for_student),
        "analytics": build_analytics_agent(),
        "action": build_action_agent(),
    }


SOURCE_RE = re.compile(r"Nguồn:\s*([^\n)]+)")


def verified_sources(answer: str) -> list[str]:
    """Trích các nguồn agent tư vấn đã ghi, CHỈ giữ nguồn có thật trong policy_chunks (chống trích dẫn bịa)."""
    cited = []
    for match in SOURCE_RE.findall(answer):
        for part in re.split(r";|,(?=\s*\d\d_)", match):
            part = part.strip(" .)*`\"'")
            if part:
                cited.append(part)
    valid = known_sources()
    # So khớp sau khi bỏ dấu: LLM hay "sửa" tên file thành có dấu (bao_luu -> bao_lưu)
    return list(dict.fromkeys(valid[fold(c)] for c in cited if fold(c) in valid))


@lru_cache
def known_sources() -> dict[str, str]:
    """{dạng-bỏ-dấu: tên nguồn chuẩn} của mọi mục tài liệu đang có trong pgvector."""
    with app_pool().connection() as conn:
        rows = conn.execute("SELECT DISTINCT source, section FROM policy_chunks").fetchall()
    names = (f"{r['source']} › {r['section'].split(' › ')[-1]}" for r in rows)
    return {fold(n): n for n in names}


@tool
def ask_advisor(question: str, runtime: ToolRuntime[UserContext]) -> str:
    """Hỏi agent tư vấn về chính sách, học phí, ưu đãi, khoá học, lịch khai giảng, lộ trình học.
    Truyền câu hỏi đầy đủ ngữ cảnh (VD: đối tượng, mục tiêu, thời gian rảnh)."""
    agent = _subagents(runtime.context.role == "student")["advisor"]
    answer = _run_subagent("advisor", agent, question, runtime)
    sources = verified_sources(answer)
    if sources:
        emit("sources", items=sources)
    if is_refusal(answer):  # lỗ hổng tài liệu -> báo cáo định kỳ cho nhân viên bổ sung
        with app_pool().connection() as conn:
            conn.execute(
                "INSERT INTO knowledge_gap (question, user_id, role) VALUES (%s, %s, %s)",
                (question, runtime.context.user_id, runtime.context.role),
            )
    return answer


@tool
def ask_analytics(question: str, runtime: ToolRuntime[UserContext]) -> str:
    """Hỏi agent phân tích dữ liệu: doanh thu, công nợ, số lượng đăng ký, danh sách học viên/lớp.
    question là câu hỏi bằng tiếng Việt tự nhiên (KHÔNG phải SQL). Kết quả gồm bảng số liệu và câu SQL đã chạy."""
    return _run_subagent("analytics", _subagents(False)["analytics"], task_with_examples(question), runtime)


@tool
def ask_action(task: str, runtime: ToolRuntime[UserContext]) -> str:
    """Giao việc cho agent vận hành: gửi email, cấp mã giảm giá. Mô tả đầy đủ người nhận và nội dung.
    Thao tác sẽ chờ người dùng duyệt trước khi thực hiện."""
    return _run_subagent("action", _subagents(False)["action"], task, runtime)


@tool
def remember_user_fact(fact: str, runtime: ToolRuntime[UserContext]) -> str:
    """Ghi nhớ lâu dài MỘT thông tin ngắn về người dùng (VD: "Con đang học lớp 8, muốn học buổi tối")."""
    get_store().put(memory_namespace(runtime.context.user_id), str(uuid.uuid4()), {"fact": fact[:300]})
    emit("memory", fact=fact)
    return "Đã ghi nhớ."


@dynamic_prompt
def supervisor_prompt(request: ModelRequest) -> str:
    ctx: UserContext = request.runtime.context
    items = get_store().search(memory_namespace(ctx.user_id), limit=MAX_MEMORIES_IN_PROMPT)
    return render_supervisor_prompt(ctx, [it.value["fact"] for it in items])


def render_supervisor_prompt(ctx: UserContext, facts: list[str]) -> str:
    memories = "\n".join(f"- {f}" for f in facts) or "(chưa có)"
    if ctx.is_staff:
        guide = "\n".join(TOOL_GUIDE[k] for k in ("ask_advisor", "ask_analytics", "ask_action"))
    else:
        guide = TOOL_GUIDE["ask_advisor_student" if ctx.hoc_vien_id else "ask_advisor"]
    return BASE_PROMPT.format(
        today=date.today().isoformat(),
        name=ctx.display_name,
        role=ROLE_LABEL[ctx.role],
        tool_guide=guide,
        memories=memories,
    )


ROLE_TOOLS = {
    "student": [ask_advisor, remember_user_fact],
    "staff": [ask_advisor, ask_analytics, ask_action, remember_user_fact],
    "manager": [ask_advisor, ask_analytics, ask_action, remember_user_fact],
}


@lru_cache
def build_supervisor(role: Role):
    middleware = [
        supervisor_prompt,
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
    return create_agent(
        chat_model(),
        tools=ROLE_TOOLS[role],
        context_schema=UserContext,
        middleware=middleware,
        checkpointer=get_checkpointer(),
        store=get_store(),
        name=f"supervisor_{role}",
    )
