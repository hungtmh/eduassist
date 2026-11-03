"""Action agent: thực hiện thao tác có tác động thật (gửi email, cấp voucher).

Mọi thao tác ghi đều đi qua HumanInTheLoopMiddleware: agent DỪNG (interrupt) và chờ nhân viên
bấm Duyệt / Từ chối. Giới hạn nghiệp vụ (mức giảm tối đa, số người nhận) được kiểm tra trong code.
"""

import re
import secrets
import smtplib
from datetime import date, datetime, timedelta
from email.message import EmailMessage

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, ToolCallLimitMiddleware, dynamic_prompt
from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from eduassist.agents.context import UserContext, emit
from eduassist.config import get_settings
from eduassist.db import app_pool
from eduassist.formatting import vnd
from eduassist.llm import chat_model, resilience_middleware

MAX_RECIPIENTS = 50
MAX_REMINDERS = 500  # nhắc nợ hàng loạt: email do code soạn từ mẫu, không qua LLM -> cho phép nhiều hơn
MAX_VOUCHER_PERCENT = {"staff": 15, "manager": 30}  # quản lý được cấp mức cao hơn
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

PROMPT = """Bạn là thư ký vận hành của Trung tâm Đào tạo Ánh Dương. Hôm nay là {today}.
Bạn thực hiện thao tác theo yêu cầu của nhân viên:
- send_payment_reminders: NHẮC NỢ HỌC PHÍ - luôn dùng tool này (không dùng send_email) khi được yêu cầu nhắc nợ.
  Hệ thống tự tính công nợ, tự điền tên + số tiền vào từng email; bạn chỉ truyền hạn thanh toán và (nếu được
  chỉ định) danh sách hoc_vien_id. Không chỉ định ai -> bỏ trống để gửi cho TẤT CẢ học viên đang nợ.
  Không được nêu hạn thanh toán -> dùng ngày {default_deadline}.
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


DEBTORS_SQL = """
WITH paid AS (SELECT don_hang_id, SUM(so_tien) AS tong FROM thanh_toan GROUP BY don_hang_id)
SELECT hv.id, hv.ho_ten, hv.email, SUM(dh.thanh_tien - COALESCE(p.tong, 0))::bigint AS con_no
FROM don_hang dh
JOIN hoc_vien hv ON hv.id = dh.hoc_vien_id
LEFT JOIN paid p ON p.don_hang_id = dh.id
WHERE dh.trang_thai IN ('chua_thanh_toan', 'thanh_toan_mot_phan')
  AND dh.thanh_tien - COALESCE(p.tong, 0) > 0
  AND (%(ids)s::int[] IS NULL OR hv.id = ANY(%(ids)s::int[]))
GROUP BY hv.id, hv.ho_ten, hv.email
ORDER BY con_no DESC, hv.id
"""


REMINDER_SUBJECT = "Trung tâm Ánh Dương - Nhắc thanh toán học phí"
REMINDER_COOLDOWN_HOURS = 24


def find_debtors(hoc_vien_ids: list[int] | None = None) -> list[dict]:
    """Công nợ tính bằng code (không phải SQL do LLM viết): phải thu - đã thu, chỉ các đơn còn hiệu lực."""
    with app_pool().connection() as conn:
        return conn.execute(DEBTORS_SQL, {"ids": hoc_vien_ids or None}).fetchall()


def reminder_targets(hoc_vien_ids: list[int] | None = None) -> tuple[list[dict], int]:
    """(người sẽ nhận, số người bỏ qua vì đã được nhắc trong REMINDER_COOLDOWN_HOURS giờ qua).

    Chống gửi trùng nằm trong code: LLM có gọi lại tool bao nhiêu lần thì mỗi người cũng chỉ nhận một email.
    """
    debtors = find_debtors(hoc_vien_ids)
    with app_pool().connection() as conn:
        recent = {
            r["email"]
            for r in conn.execute(
                """SELECT DISTINCT unnest(recipients) AS email FROM email_log
                   WHERE subject = %s AND sent_at > now() - make_interval(hours => %s)""",
                (REMINDER_SUBJECT, REMINDER_COOLDOWN_HOURS),
            ).fetchall()
        }
    targets = [d for d in debtors if d["email"] not in recent]
    return targets, len(debtors) - len(targets)


def parse_deadline(text: str) -> date:
    """Nhận '15/12/2026' hoặc '2026-12-15'. Hạn phải trong 1..60 ngày tới."""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            d = datetime.strptime(text.strip(), fmt).date()
            break
        except ValueError:
            continue
    else:
        raise ValueError("hạn thanh toán phải có dạng dd/mm/yyyy")
    if not date.today() < d <= date.today() + timedelta(days=60):
        raise ValueError("hạn thanh toán phải trong vòng 60 ngày tới")
    return d


def reminder_email(student: dict, deadline: date, note: str = "") -> tuple[str, str]:
    subject = REMINDER_SUBJECT
    body = (
        f"Kính gửi {student['ho_ten']},\n\n"
        f"Trung tâm Đào tạo Ánh Dương xin thông báo học phí còn lại của bạn là {vnd(student['con_no'])}.\n"
        f"Bạn vui lòng hoàn tất thanh toán trước ngày {deadline:%d/%m/%Y} để việc học không bị gián đoạn.\n"
        + (f"\n{note.strip()}\n" if note.strip() else "")
        + "\nNếu bạn đã thanh toán, vui lòng bỏ qua email này. Cần hỗ trợ, gọi hotline 1900 0000.\n\n"
        "Trân trọng,\nTrung tâm Đào tạo Ánh Dương"
    )
    return subject, body


def _smtp_send(recipient: str, subject: str, body: str, smtp: smtplib.SMTP, sender: str) -> None:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)
    smtp.send_message(msg)


@tool
def send_payment_reminders(
    han_thanh_toan: str,
    runtime: ToolRuntime[UserContext],
    hoc_vien_ids: list[int] | None = None,
    loi_nhan_them: str = "",
) -> str:
    """Gửi email nhắc nợ học phí, MỖI HỌC VIÊN MỘT EMAIL với đúng tên và số tiền còn nợ (hệ thống tự tính).
    han_thanh_toan: dd/mm/yyyy. hoc_vien_ids: bỏ trống = tất cả học viên đang nợ. Cần người duyệt trước khi gửi."""
    try:
        deadline = parse_deadline(han_thanh_toan)
    except ValueError as e:
        return f"LỖI: {e}. Chưa có email nào được gửi."
    debtors, skipped = reminder_targets(hoc_vien_ids)
    skip_note = f" Bỏ qua {skipped} người đã được nhắc trong {REMINDER_COOLDOWN_HOURS} giờ qua." if skipped else ""
    if not debtors:
        return "Không gửi email nào: không có học viên đang nợ cần nhắc." + skip_note
    if len(debtors) > MAX_REMINDERS:
        return f"LỖI: {len(debtors)} người nhận vượt giới hạn {MAX_REMINDERS}. Chưa có email nào được gửi."
    s = get_settings()
    sent: list[tuple] = []
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as smtp:
            for d in debtors:
                subject, body = reminder_email(d, deadline, loi_nhan_them)
                _smtp_send(d["email"], subject, body, smtp, s.smtp_from)
                sent.append(([d["email"]], subject, body, runtime.context.user_id))
    except OSError as e:
        failed = f"LỖI SMTP sau khi gửi {len(sent)}/{len(debtors)} email ({e})."
    else:
        failed = ""
    if sent:
        with app_pool().connection() as conn, conn.cursor() as cur:
            cur.executemany("INSERT INTO email_log (recipients, subject, body, sent_by) VALUES (%s, %s, %s, %s)", sent)
    emit("action", action="send_payment_reminders", recipients=len(sent))
    total = sum(d["con_no"] for d in debtors[: len(sent)])
    return (
        failed
        or f"ĐÃ GỬI XONG {len(sent)} email nhắc nợ (tổng còn nợ {vnd(total)}), hạn thanh toán {deadline:%d/%m/%Y}."
    ) + skip_note


def describe_reminders(tool_call: dict, state, runtime) -> str:
    """Nội dung hiện cho người duyệt: tính TRƯỚC khi gửi, đúng dữ liệu sẽ gửi đi."""
    args = tool_call["args"]
    try:
        deadline = parse_deadline(args.get("han_thanh_toan", ""))
    except ValueError as e:
        return f"Nhắc nợ học phí - tham số không hợp lệ ({e}); nếu duyệt, tool sẽ báo lỗi và không gửi gì."
    debtors, skipped = reminder_targets(args.get("hoc_vien_ids"))
    skip_note = f"\n\n⚠️ Bỏ qua {skipped} người đã được nhắc trong {REMINDER_COOLDOWN_HOURS} giờ qua." if skipped else ""
    if not debtors:
        return "Nhắc nợ học phí - không có ai cần nhắc; nếu duyệt sẽ không gửi email nào." + skip_note
    top = "\n".join(f"- {d['ho_ten']} (id {d['id']}): {vnd(d['con_no'])}" for d in debtors[:5])
    more = f"\n- … và {len(debtors) - 5} người khác" if len(debtors) > 5 else ""
    subject, body = reminder_email(debtors[0], deadline, args.get("loi_nhan_them", ""))
    return (
        f"**Gửi {len(debtors)} email nhắc nợ** (mỗi người một email riêng) · tổng còn nợ "
        f"**{vnd(sum(d['con_no'] for d in debtors))}** · hạn **{deadline:%d/%m/%Y}**{skip_note}\n\n{top}{more}\n\n"
        f"**Email mẫu** (gửi {debtors[0]['email']}) – **{subject}**\n\n> " + body.replace("\n", "\n> ")
    )


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


@dynamic_prompt
def action_prompt(request) -> str:
    return PROMPT.format(today=date.today(), default_deadline=f"{date.today() + timedelta(days=7):%d/%m/%Y}")


def build_action_agent():
    review = {"allowed_decisions": ["approve", "reject"]}
    return create_agent(
        chat_model(),
        tools=[send_payment_reminders, get_student_contacts, send_email, create_voucher],
        context_schema=UserContext,
        middleware=[
            action_prompt,
            *resilience_middleware(),
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "send_payment_reminders": {**review, "description": describe_reminders},
                    "send_email": review,
                    "create_voucher": review,
                    "get_student_contacts": False,
                },
                description_prefix="Cần duyệt thao tác",
            ),
            ToolCallLimitMiddleware(run_limit=8),
        ],
        name="action",
    )
