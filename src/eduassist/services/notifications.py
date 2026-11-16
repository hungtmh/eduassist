"""Phân hệ 6 - Thông báo: email (SMTP) và thông báo trong ứng dụng.

Luật: chỉ gửi tới địa chỉ có thật trong hệ thống; không gửi trùng cùng loại nội dung cho cùng người trong 24 giờ;
giới hạn số người nhận mỗi đợt.
"""

import logging
import re
import smtplib
import ssl
from contextvars import ContextVar
from dataclasses import dataclass
from email.message import EmailMessage

from eduassist.config import get_settings
from eduassist.services.core import Actor, RuleViolation, audit, now, require

log = logging.getLogger("eduassist.notifications")

DEDUPE_HOURS = 24
MAX_FREEFORM_RECIPIENTS = 50  # email do LLM soạn
MAX_TEMPLATED_BATCH = 500  # email do code soạn từ mẫu
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class Mail:
    to: str
    subject: str
    body: str


# Mô phỏng / kiểm thử: gom email vào danh sách thay vì gửi SMTP thật
_capture: ContextVar[list[Mail] | None] = ContextVar("eduassist_mail_capture", default=None)


def capture_mail(box: list[Mail]):
    return _capture.set(box)


def _deliver(mails: list[Mail]) -> None:
    box = _capture.get()
    if box is not None:
        box.extend(mails)
        return
    if not mails:
        return
    s = get_settings()
    smtp_cls = smtplib.SMTP_SSL if s.smtp_security == "ssl" else smtplib.SMTP
    with smtp_cls(s.smtp_host, s.smtp_port, timeout=15) as smtp:
        if s.smtp_security == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_password.get_secret_value())
        for m in mails:
            msg = EmailMessage()
            msg["From"] = s.smtp_from
            msg["To"] = m.to
            msg["Subject"] = m.subject
            msg.set_content(m.body)
            smtp.send_message(msg)


def recently_sent(conn, kind: str, student_ids: list[int]) -> set[int]:
    if not student_ids:
        return set()
    rows = conn.execute(
        """SELECT DISTINCT hoc_vien_id FROM email_log
           WHERE loai = %s AND hoc_vien_id = ANY(%s) AND sent_at > %s::timestamptz - make_interval(hours => %s)
             AND sent_at <= %s::timestamptz""",
        (kind, student_ids, now(), DEDUPE_HOURS, now()),
    ).fetchall()
    return {r["hoc_vien_id"] for r in rows}


@dataclass
class SendResult:
    sent: list[int]
    skipped_recent: list[int]
    error: str | None = None


def send_student_emails(
    conn, actor: Actor, kind: str, messages: dict[int, tuple[str, str]], proposal_id: int | None = None
) -> SendResult:
    """Gửi email theo mẫu, MỖI HỌC VIÊN MỘT EMAIL. messages = {hoc_vien_id: (tiêu đề, nội dung)}.
    Địa chỉ email lấy từ DB theo id (không nhận địa chỉ do LLM gõ)."""
    require(actor, "email.send")
    if len(messages) > MAX_TEMPLATED_BATCH:
        raise RuleViolation(f"Một đợt gửi tối đa {MAX_TEMPLATED_BATCH} email, nhận {len(messages)}.")
    ids = list(messages)
    rows = conn.execute("SELECT id, email FROM hoc_vien WHERE id = ANY(%s)", (ids,)).fetchall()
    emails = {r["id"]: r["email"] for r in rows}
    unknown = [i for i in ids if i not in emails]
    if unknown:
        raise RuleViolation(f"Không có học viên id {', '.join(map(str, unknown))}. Chưa gửi email nào.")
    recent = recently_sent(conn, kind, ids)
    targets = [i for i in ids if i not in recent]
    mails = [Mail(emails[i], *messages[i]) for i in targets]
    error = None
    try:
        _deliver(mails)
    except OSError as e:
        error = f"Lỗi SMTP: {e}"
        targets, mails = [], []
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO email_log (recipients, subject, body, sent_by, loai, hoc_vien_id, de_xuat_id, sent_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            [
                ([m.to], m.subject, m.body, actor.id, kind, i, proposal_id, now())
                for i, m in zip(targets, mails, strict=True)
            ],
        )
    if targets:
        audit(conn, actor, "gui_email", "email", kind, after={"loai": kind, "so_nguoi_nhan": len(targets)})
    return SendResult(sent=targets, skipped_recent=sorted(recent), error=error)


def send_freeform_email(conn, actor: Actor, recipients: list[str], subject: str, body: str, proposal_id=None) -> int:
    """Email nội dung tự do (do người hoặc LLM soạn). Chỉ tới email học viên / khách tiềm năng có thật."""
    require(actor, "email.send")
    recipients = [r.strip().lower() for r in recipients]
    bad = [r for r in recipients if not EMAIL_RE.match(r)]
    if bad:
        raise RuleViolation(f"Địa chỉ email không hợp lệ: {', '.join(bad)}.")
    if not 1 <= len(recipients) <= MAX_FREEFORM_RECIPIENTS:
        raise RuleViolation(f"Số người nhận phải từ 1 đến {MAX_FREEFORM_RECIPIENTS}.")
    known = {
        r["email"]
        for r in conn.execute(
            """SELECT lower(email) AS email FROM hoc_vien WHERE lower(email) = ANY(%(e)s)
               UNION SELECT lower(email) FROM khach_tiem_nang WHERE lower(email) = ANY(%(e)s)""",
            {"e": recipients},
        ).fetchall()
    }
    unknown = [r for r in recipients if r not in known]
    if unknown:
        raise RuleViolation(
            f"Không phải email của học viên/khách trong hệ thống: {', '.join(unknown)}. Chưa gửi email nào."
        )
    _deliver([Mail(r, subject, body) for r in recipients])
    conn.execute(
        """INSERT INTO email_log (recipients, subject, body, sent_by, loai, de_xuat_id, sent_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (recipients, subject, body, actor.id, "tu_do", proposal_id, now()),
    )
    audit(conn, actor, "gui_email", "email", "tu_do", after={"tieu_de": subject, "so_nguoi_nhan": len(recipients)})
    return len(recipients)


def notify(conn, recipient: str, title: str, body: str, link: str | None = None) -> None:
    """Thông báo trong ứng dụng. recipient = username hoặc 'role:<vai trò>'."""
    conn.execute(
        "INSERT INTO thong_bao (nguoi_nhan, tieu_de, noi_dung, lien_ket, created_at) VALUES (%s, %s, %s, %s, %s)",
        (recipient, title, body, link, now()),
    )


def list_notifications(conn, actor: Actor, limit: int = 30) -> list[dict]:
    return conn.execute(
        """SELECT id, tieu_de, noi_dung, lien_ket, da_doc, created_at FROM thong_bao
           WHERE nguoi_nhan = %s OR nguoi_nhan = %s ORDER BY created_at DESC LIMIT %s""",
        (actor.id, f"role:{actor.role}", limit),
    ).fetchall()


def mark_read(conn, actor: Actor, ids: list[int]) -> None:
    conn.execute(
        "UPDATE thong_bao SET da_doc = true WHERE id = ANY(%s) AND (nguoi_nhan = %s OR nguoi_nhan = %s)",
        (ids, actor.id, f"role:{actor.role}"),
    )


def send_system_email(
    conn, to: str, subject: str, body: str, kind: str, logged_body: str | None = None, hoc_vien_id: int | None = None
) -> str | None:
    """Email hệ thống (kích hoạt tài khoản, đặt lại mật khẩu). Không cần quyền email.send: người dùng tự yêu cầu.
    logged_body: nội dung ghi vào email_log - truyền bản đã ẩn link/token để người xem log không dùng lại được.
    Trả về thông báo lỗi (None nếu gửi được); không raise để không làm hỏng thao tác chính."""
    if not EMAIL_RE.match(to or ""):
        return "Địa chỉ email không hợp lệ."
    try:
        _deliver([Mail(to, subject, body)])
    except OSError as e:  # gồm cả smtplib.SMTPException
        log.warning("không gửi được email hệ thống %s tới %s: %s", kind, to, e)
        return "Chưa gửi được email (lỗi máy chủ email)."
    conn.execute(
        """INSERT INTO email_log (recipients, subject, body, sent_by, loai, hoc_vien_id, sent_at)
           VALUES (%s, %s, %s, 'system', %s, %s, %s)""",
        ([to], subject, logged_body if logged_body is not None else body, kind, hoc_vien_id, now()),
    )
    return None
