"""Action agent: thực hiện thao tác có tác động thật (gửi email, cấp voucher).

Mọi thao tác ghi đều đi qua HumanInTheLoopMiddleware: agent DỪNG (interrupt) và chờ nhân viên
bấm Duyệt / Từ chối. Giới hạn nghiệp vụ (mức giảm tối đa, số người nhận) được kiểm tra trong code.
"""

import re
import secrets
import smtplib
from datetime import date, timedelta
from email.message import EmailMessage

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, ToolCallLimitMiddleware
from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from eduassist.agents.context import UserContext, emit
from eduassist.config import get_settings
from eduassist.db import app_pool
from eduassist.llm import chat_model, resilience_middleware

MAX_RECIPIENTS = 50
MAX_VOUCHER_PERCENT = {"staff": 15, "manager": 30}  # quản lý được cấp mức cao hơn
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

PROMPT = """Bạn là thư ký vận hành của Trung tâm Đào tạo Ánh Dương. Bạn thực hiện thao tác theo yêu cầu của nhân viên:
- get_student_contacts: lấy họ tên + email học viên theo danh sách hoc_vien_id (không cần duyệt).
- send_email: gửi email. Viết tiếng Việt lịch sự, xưng "Trung tâm", ký tên "Trung tâm Đào tạo Ánh Dương".
  Mỗi học viên một email riêng nếu nội dung có thông tin cá nhân (VD: số tiền nợ của từng người).
- create_voucher: cấp mã giảm giá cho một học viên.
Đủ thông tin thì GỌI TOOL NGAY. TUYỆT ĐỐI không hỏi "bạn có muốn duyệt/gửi không" bằng lời: khi bạn gọi
send_email / create_voucher, hệ thống tự dừng lại và hiện nút Duyệt / Từ chối cho người dùng.
Nếu thao tác bị từ chối, KHÔNG thử lại thao tác đó; báo lại kết quả.
Chỉ hỏi lại khi THIẾU thông tin bắt buộc (không có người nhận, không rõ mức giảm) - không tự đoán.
Cuối cùng tóm tắt ngắn gọn những gì đã làm / chưa làm."""


@tool
def get_student_contacts(hoc_vien_ids: list[int]) -> str:
    """Lấy họ tên và email của các học viên theo id."""
    with app_pool().connection() as conn:
        rows = conn.execute(
            "SELECT id, ho_ten, email FROM hoc_vien WHERE id = ANY(%s) ORDER BY id", (hoc_vien_ids[:MAX_RECIPIENTS],)
        ).fetchall()
    return "\n".join(f"- id {r['id']}: {r['ho_ten']} <{r['email']}>" for r in rows) or "Không tìm thấy học viên nào."


@tool
def send_email(recipients: list[str], subject: str, body: str, runtime: ToolRuntime[UserContext]) -> str:
    """Gửi MỘT email tới danh sách người nhận (tối đa 50 địa chỉ). Cần người duyệt trước khi gửi."""
    invalid = [r for r in recipients if not EMAIL_RE.match(r)]
    if invalid:
        return f"LỖI: địa chỉ email không hợp lệ: {', '.join(invalid)}"
    if not recipients or len(recipients) > MAX_RECIPIENTS:
        return f"LỖI: số người nhận phải từ 1 đến {MAX_RECIPIENTS}."
    # Chỉ được gửi tới email học viên có thật: chặn gõ nhầm địa chỉ và chặn việc bị lừa gửi dữ liệu ra ngoài
    with app_pool().connection() as conn:
        known = {
            r["email"]
            for r in conn.execute(
                "SELECT email FROM hoc_vien WHERE email = ANY(%s)", ([r.lower() for r in recipients],)
            ).fetchall()
        }
    unknown = [r for r in recipients if r.lower() not in known]
    if unknown:
        return (
            f"LỖI: không phải email của học viên trong hệ thống: {', '.join(unknown)}. "
            "Dùng get_student_contacts để lấy đúng địa chỉ. Chưa có email nào được gửi."
        )
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = s.smtp_from
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as smtp:
            smtp.send_message(msg)
    except OSError as e:
        return f"LỖI: không gửi được email ({e}). Chưa có email nào được gửi."
    with app_pool().connection() as conn:
        conn.execute(
            "INSERT INTO email_log (recipients, subject, body, sent_by) VALUES (%s, %s, %s, %s)",
            (recipients, subject, body, runtime.context.user_id),
        )
    emit("action", action="send_email", recipients=len(recipients))
    return f"Đã gửi email '{subject}' tới {len(recipients)} người nhận."


@tool
def create_voucher(
    hoc_vien_id: int, phan_tram: int, ly_do: str, runtime: ToolRuntime[UserContext], so_ngay_hieu_luc: int = 30
) -> str:
    """Cấp mã giảm giá cho một học viên. phan_tram là % giảm học phí. Cần người duyệt trước khi tạo."""
    ctx = runtime.context
    limit = MAX_VOUCHER_PERCENT.get(ctx.role, 0)
    if not 1 <= phan_tram <= limit:
        return f"LỖI: vai trò {ctx.role} chỉ được cấp voucher từ 1% đến {limit}%."
    if not 1 <= so_ngay_hieu_luc <= 90:
        return "LỖI: hiệu lực voucher từ 1 đến 90 ngày."
    code = "AD-" + secrets.token_hex(3).upper()
    expires = date.today() + timedelta(days=so_ngay_hieu_luc)
    with app_pool().connection() as conn:
        student = conn.execute("SELECT ho_ten FROM hoc_vien WHERE id = %s", (hoc_vien_id,)).fetchone()
        if student is None:
            return f"LỖI: không có học viên id {hoc_vien_id}."
        conn.execute(
            """INSERT INTO voucher (ma, hoc_vien_id, phan_tram, ly_do, han_su_dung, created_by)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (code, hoc_vien_id, phan_tram, ly_do, expires, ctx.user_id),
        )
    emit("action", action="create_voucher", code=code)
    return f"Đã tạo voucher {code} giảm {phan_tram}% cho {student['ho_ten']} (id {hoc_vien_id}), hạn dùng {expires}."


def build_action_agent():
    review = {"allowed_decisions": ["approve", "reject"]}
    return create_agent(
        chat_model(),
        tools=[get_student_contacts, send_email, create_voucher],
        system_prompt=PROMPT,
        context_schema=UserContext,
        middleware=[
            *resilience_middleware(),
            HumanInTheLoopMiddleware(
                interrupt_on={"send_email": review, "create_voucher": review, "get_student_contacts": False},
                description_prefix="Cần duyệt thao tác",
            ),
            ToolCallLimitMiddleware(run_limit=8),
        ],
        name="action",
    )
