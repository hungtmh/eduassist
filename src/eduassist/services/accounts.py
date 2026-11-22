"""Tài khoản người dùng: đăng nhập, mật khẩu, quản trị tài khoản, cấp tài khoản cho học viên.

Luật:
- Sai mật khẩu LOGIN_MAX_FAILURES lần liên tiếp -> khoá tạm LOGIN_LOCKOUT_MINUTES phút.
- Mật khẩu tối thiểu 8 ký tự, có cả chữ và số, không trùng tên đăng nhập, không nằm trong danh sách quá phổ biến.
- Tài khoản do người khác tạo hoặc do quản lý đặt lại mật khẩu -> bắt đổi mật khẩu ở lần đăng nhập kế tiếp.
- Đổi mật khẩu, đặt lại mật khẩu, khoá tài khoản, đổi vai trò -> token_version tăng: mọi phiên đang mở bị đăng xuất.
- Link đặt lại / kích hoạt dùng một lần, có hạn; DB chỉ lưu SHA-256 của token.
- Luôn còn ít nhất một quản lý đang hoạt động; quản lý không tự khoá hay tự hạ quyền mình.
"""

import hashlib
import re
import secrets
import string
from datetime import UTC, datetime, timedelta

from eduassist import cache
from eduassist.config import get_settings
from eduassist.security.passwords import hash_password, verify_password
from eduassist.services import notifications
from eduassist.services.core import (
    ROLE_LABEL,
    ROLES,
    Actor,
    Conflict,
    Page,
    RuleViolation,
    ServiceError,
    audit,
    one,
    paginate,
    require,
)

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
COMMON_PASSWORDS = {
    "demo123",
    "12345678",
    "123456789",
    "1234567890",
    "password",
    "password1",
    "password123",
    "matkhau",
    "matkhau123",
    "abc12345",
    "qwerty123",
    "11111111",
    "admin123",
    "anhduong",
    "anhduong123",
}
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
STAFF_ROLES = tuple(r for r in ROLES if r != "student")

# Băm sẵn một mật khẩu giả: khi tên đăng nhập không tồn tại vẫn tốn cùng thời gian kiểm tra -> không dò được tên
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))

ACCOUNT_SQL = """
SELECT u.username, u.password_hash, u.role, u.display_name, u.email, u.hoc_vien_id, u.active, u.token_version,
       u.must_change_password, u.failed_logins, u.locked_until, u.last_login_at, u.created_at,
       gv.id AS giang_vien_id
FROM app_user u LEFT JOIN giang_vien gv ON gv.username = u.username
"""


class AccountLocked(ServiceError):
    status = 429


# ---------------------------------------------------------------- mật khẩu
def validate_password(password: str, username: str = "") -> None:
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise RuleViolation(f"Mật khẩu phải dài từ {PASSWORD_MIN_LENGTH} đến {PASSWORD_MAX_LENGTH} ký tự.")
    if not (re.search(r"[^\W\d_]", password) and re.search(r"\d", password)):
        raise RuleViolation("Mật khẩu phải có cả chữ và số.")
    lowered = password.lower()
    if username and username.lower() in lowered:
        raise RuleViolation("Mật khẩu không được chứa tên đăng nhập.")
    if lowered in COMMON_PASSWORDS:
        raise RuleViolation("Mật khẩu này quá phổ biến, hãy chọn mật khẩu khác.")


def temporary_password() -> str:
    """Mật khẩu tạm 12 ký tự, dễ đọc (bỏ 0/O, 1/l/I), luôn có chữ và số."""
    alphabet = "".join(c for c in string.ascii_letters + string.digits if c not in "0O1lI")
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(12))
        if re.search(r"[A-Za-z]", pw) and re.search(r"\d", pw):
            return pw


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---------------------------------------------------------------- đọc tài khoản
def load_account(conn, username: str) -> dict | None:
    return conn.execute(ACCOUNT_SQL + " WHERE u.username = %s", (username,)).fetchone()


def public_view(row: dict) -> dict:
    """Thông tin tài khoản trả cho giao diện (không có hash mật khẩu, bộ đếm sai)."""
    locked = row.get("locked_until")
    return {
        "username": row["username"],
        "role": row["role"],
        "role_label": ROLE_LABEL.get(row["role"], row["role"]),
        "display_name": row["display_name"],
        "email": row.get("email"),
        "hoc_vien_id": row.get("hoc_vien_id"),
        "giang_vien_id": row.get("giang_vien_id"),
        "active": row["active"],
        "must_change_password": row.get("must_change_password", False),
        "dang_bi_khoa_tam": bool(locked and locked > datetime.now(UTC)),
        "last_login_at": row.get("last_login_at"),
        "created_at": row.get("created_at"),
    }


# ---------------------------------------------------------------- đăng nhập
def login(conn, username: str, password: str) -> dict | None:
    """Trả tài khoản nếu đúng, None nếu sai. Raise AccountLocked khi đang bị khoá tạm.

    conn phải ở chế độ autocommit (không bọc trong transaction của request): bộ đếm sai phải được lưu
    kể cả khi hàm raise."""
    s = get_settings()
    row = load_account(conn, username.strip().lower())
    if row is None or not row["active"]:
        verify_password(password, _DUMMY_HASH)
        return None
    now = datetime.now(UTC)
    if row["locked_until"] and row["locked_until"] > now:
        minutes = max(1, int((row["locked_until"] - now).total_seconds() // 60) + 1)
        raise AccountLocked(f"Tài khoản đang tạm khoá do nhập sai mật khẩu nhiều lần. Thử lại sau {minutes} phút.")
    if not verify_password(password, row["password_hash"]):
        failures = row["failed_logins"] + 1
        if failures >= s.login_max_failures:
            conn.execute(
                """UPDATE app_user SET failed_logins = 0, locked_until = now() + make_interval(mins => %s)
                   WHERE username = %s""",
                (s.login_lockout_minutes, row["username"]),
            )
            audit(
                conn,
                Actor(id=row["username"], role=row["role"]),
                "khoa_tam_dang_nhap",
                "app_user",
                row["username"],
                reason=f"Sai mật khẩu {failures} lần liên tiếp",
            )
            raise AccountLocked(
                f"Bạn đã nhập sai mật khẩu {failures} lần. Tài khoản tạm khoá {s.login_lockout_minutes} phút."
            )
        conn.execute("UPDATE app_user SET failed_logins = %s WHERE username = %s", (failures, row["username"]))
        return None
    conn.execute(
        "UPDATE app_user SET failed_logins = 0, locked_until = NULL, last_login_at = now() WHERE username = %s",
        (row["username"],),
    )
    return row


def _set_password(conn, username: str, password: str, must_change: bool) -> None:
    conn.execute(
        """UPDATE app_user SET password_hash = %s, must_change_password = %s, token_version = token_version + 1,
                  failed_logins = 0, locked_until = NULL, password_changed_at = now()
           WHERE username = %s""",
        (hash_password(password), must_change, username),
    )
    cache.account_changed(conn, username)


def change_password(conn, username: str, old_password: str, new_password: str) -> dict:
    row = one(conn, ACCOUNT_SQL + " WHERE u.username = %s AND u.active", (username,), "tài khoản")
    if not verify_password(old_password, row["password_hash"]):
        raise RuleViolation("Mật khẩu hiện tại không đúng.")
    if old_password == new_password:
        raise RuleViolation("Mật khẩu mới phải khác mật khẩu hiện tại.")
    validate_password(new_password, username)
    _set_password(conn, username, new_password, must_change=False)
    audit(conn, Actor(id=username, role=row["role"]), "doi_mat_khau", "app_user", username)
    return load_account(conn, username)


def logout_everywhere(conn, username: str) -> None:
    conn.execute("UPDATE app_user SET token_version = token_version + 1 WHERE username = %s", (username,))
    cache.account_changed(conn, username)


# ---------------------------------------------------------------- link đặt lại / kích hoạt
def _issue_link(conn, username: str, purpose: str, ttl: timedelta) -> str:
    conn.execute(
        "UPDATE password_reset SET used_at = now() WHERE username = %s AND muc_dich = %s AND used_at IS NULL",
        (username, purpose),
    )
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO password_reset (username, token_hash, muc_dich, expires_at) VALUES (%s, %s, %s, now() + %s)",
        (username, _token_hash(token), purpose, ttl),
    )
    return f"{get_settings().public_web_url.rstrip('/')}/dat-mat-khau?token={token}"


def _send_link(conn, row: dict, purpose: str) -> str | None:
    """Gửi link qua email. Trả lỗi (None nếu đã gửi)."""
    if not row.get("email"):
        return "Tài khoản chưa có email."
    s = get_settings()
    if purpose == "kich_hoat":
        link = _issue_link(conn, row["username"], purpose, timedelta(days=s.account_activation_days))
        subject = "Trung tâm Ánh Dương - Kích hoạt tài khoản"
        body = (
            f"Chào {row['display_name']},\n\nTrung tâm Đào tạo Ánh Dương đã tạo tài khoản cho bạn.\n"
            f"Tên đăng nhập: {row['username']}\n\n"
            f"Bấm vào link sau để tự đặt mật khẩu (link dùng một lần, hết hạn sau {s.account_activation_days} ngày):\n"
            f"{link}\n\nNếu bạn không đăng ký học tại trung tâm, hãy bỏ qua email này.\n\n"
            "Trân trọng,\nTrung tâm Đào tạo Ánh Dương"
        )
    else:
        link = _issue_link(conn, row["username"], purpose, timedelta(minutes=s.password_reset_minutes))
        subject = "Trung tâm Ánh Dương - Đặt lại mật khẩu"
        body = (
            f"Chào {row['display_name']},\n\nCó yêu cầu đặt lại mật khẩu cho tài khoản {row['username']}.\n"
            f"Bấm vào link sau để đặt mật khẩu mới (dùng một lần, hết hạn sau {s.password_reset_minutes} phút):\n"
            f"{link}\n\nNếu bạn không yêu cầu, hãy bỏ qua email này; mật khẩu hiện tại vẫn giữ nguyên.\n\n"
            "Trân trọng,\nTrung tâm Đào tạo Ánh Dương"
        )
    return notifications.send_system_email(
        conn,
        row["email"],
        subject,
        body,
        f"tai_khoan_{purpose}",
        logged_body=body.replace(link, "[link đã ẩn]"),
        hoc_vien_id=row.get("hoc_vien_id"),
    )


def request_password_reset(conn, identifier: str) -> None:
    """Người dùng quên mật khẩu, nhập tên đăng nhập hoặc email. Không báo tài khoản có tồn tại hay không."""
    ident = identifier.strip().lower()
    row = conn.execute(
        ACCOUNT_SQL + " WHERE u.active AND (u.username = %(i)s OR lower(u.email) = %(i)s) LIMIT 1", {"i": ident}
    ).fetchone()
    if row is None or not row["email"]:
        return
    _send_link(conn, row, "dat_lai")


def _valid_link(conn, token: str) -> dict:
    row = conn.execute(
        """SELECT r.id, r.username, r.muc_dich, u.display_name, u.role FROM password_reset r
           JOIN app_user u ON u.username = r.username
           WHERE r.token_hash = %s AND r.used_at IS NULL AND r.expires_at > now() AND u.active""",
        (_token_hash(token),),
    ).fetchone()
    if row is None:
        raise RuleViolation("Link không hợp lệ hoặc đã hết hạn. Hãy yêu cầu link mới.")
    return row


def check_link(conn, token: str) -> dict:
    row = _valid_link(conn, token)
    return {"username": row["username"], "display_name": row["display_name"], "muc_dich": row["muc_dich"]}


def reset_password(conn, token: str, new_password: str) -> None:
    row = _valid_link(conn, token)
    validate_password(new_password, row["username"])
    _set_password(conn, row["username"], new_password, must_change=False)
    conn.execute(
        "UPDATE password_reset SET used_at = now() WHERE username = %s AND used_at IS NULL", (row["username"],)
    )
    action = "kich_hoat_tai_khoan" if row["muc_dich"] == "kich_hoat" else "dat_lai_mat_khau"
    audit(conn, Actor(id=row["username"], role=row["role"]), action, "app_user", row["username"])


# ---------------------------------------------------------------- quản trị tài khoản (quản lý)
def list_users(
    conn, actor: Actor, q: str | None = None, role: str | None = None, limit: int = 100, offset: int = 0
) -> Page:
    require(actor, "user.admin")
    rows = paginate(
        conn,
        ACCOUNT_SQL
        + """ WHERE (%(role)s::text IS NULL OR u.role = %(role)s)
                AND (%(q)s::text IS NULL OR u.username ILIKE %(like)s OR u.display_name ILIKE %(like)s
                     OR u.email ILIKE %(like)s)""",
        {"role": role, "q": q, "like": f"%{q}%"},
        "active DESC, role, username",
        limit,
        offset,
    )
    return Page([public_view(r) for r in rows], rows.total)


def _check_unique(conn, username: str, email: str | None) -> None:
    if conn.execute("SELECT 1 FROM app_user WHERE username = %s", (username,)).fetchone():
        raise Conflict(f"Tên đăng nhập '{username}' đã có người dùng.")
    if email and conn.execute("SELECT 1 FROM app_user WHERE lower(email) = lower(%s)", (email,)).fetchone():
        raise Conflict(f"Email {email} đã gắn với một tài khoản khác.")


def _insert(conn, username, display_name, role, email, hoc_vien_id) -> str:
    temp = temporary_password()
    conn.execute(
        """INSERT INTO app_user (username, password_hash, role, display_name, email, hoc_vien_id, must_change_password)
           VALUES (%s, %s, %s, %s, %s, %s, true)""",
        (username, hash_password(temp), role, display_name, email, hoc_vien_id),
    )
    return temp


def create_staff_user(
    conn,
    actor: Actor,
    username: str,
    display_name: str,
    role: str,
    email: str | None = None,
    giang_vien_id: int | None = None,
    send_email: bool = False,
) -> dict:
    """Quản lý tạo tài khoản nhân viên. Trả mật khẩu tạm (hiện MỘT lần) - người dùng phải đổi khi đăng nhập."""
    require(actor, "user.admin")
    username = username.strip().lower()
    email = email.strip().lower() if email else None
    if not USERNAME_RE.match(username):
        raise RuleViolation("Tên đăng nhập 3-32 ký tự, chỉ gồm chữ thường không dấu, số, dấu chấm, gạch nối.")
    if role not in STAFF_ROLES:
        raise RuleViolation("Tài khoản học viên được cấp từ hồ sơ học viên, không tạo ở đây.")
    if email and not notifications.EMAIL_RE.match(email):
        raise RuleViolation("Email không hợp lệ.")
    _check_unique(conn, username, email)
    if giang_vien_id is not None:
        if role != "teacher":
            raise RuleViolation("Chỉ tài khoản giảng viên mới gắn với hồ sơ giảng viên.")
        gv = one(conn, "SELECT id, username FROM giang_vien WHERE id = %s", (giang_vien_id,), "giảng viên")
        if gv["username"]:
            raise Conflict(f"Giảng viên này đã có tài khoản '{gv['username']}'.")
    temp = _insert(conn, username, display_name.strip(), role, email, None)
    if giang_vien_id is not None:
        conn.execute("UPDATE giang_vien SET username = %s WHERE id = %s", (username, giang_vien_id))
    audit(conn, actor, "tao_tai_khoan", "app_user", username, after={"role": role, "email": email})
    row = load_account(conn, username)
    email_error = _send_link(conn, row, "kich_hoat") if send_email else None
    return {
        "user": public_view(row),
        "mat_khau_tam": temp,
        "da_gui_email": send_email and email_error is None,
        "loi_email": email_error,
    }


def _active_managers(conn, excluding: str) -> int:
    return conn.execute(
        "SELECT count(*) AS n FROM app_user WHERE role = 'manager' AND active AND username <> %s", (excluding,)
    ).fetchone()["n"]


def update_user(
    conn,
    actor: Actor,
    username: str,
    display_name: str | None = None,
    role: str | None = None,
    email: str | None = None,
    active: bool | None = None,
) -> dict:
    require(actor, "user.admin")
    row = one(conn, ACCOUNT_SQL + " WHERE u.username = %s", (username,), "tài khoản")
    before = public_view(row)
    if role is not None and role != row["role"]:
        if "student" in (role, row["role"]):
            raise RuleViolation("Không đổi được giữa tài khoản học viên và nhân viên.")
        if role not in STAFF_ROLES:
            raise RuleViolation("Vai trò không hợp lệ.")
    demoting = row["role"] == "manager" and role not in (None, "manager")
    deactivating = active is False and row["active"]
    if username == actor.id and (demoting or deactivating):
        raise RuleViolation("Bạn không tự khoá hoặc tự hạ quyền tài khoản của mình được.")
    if (demoting or deactivating) and row["role"] == "manager" and _active_managers(conn, username) == 0:
        raise RuleViolation("Hệ thống phải còn ít nhất một quản lý đang hoạt động.")
    email_given = email is not None
    if email_given:
        email = email.strip().lower() or None
        if email and not notifications.EMAIL_RE.match(email):
            raise RuleViolation("Email không hợp lệ.")
        if (
            email
            and conn.execute(
                "SELECT 1 FROM app_user WHERE lower(email) = %s AND username <> %s", (email, username)
            ).fetchone()
        ):
            raise Conflict(f"Email {email} đã gắn với một tài khoản khác.")
    revoke = (role is not None and role != row["role"]) or (active is not None and active != row["active"])
    conn.execute(
        """UPDATE app_user SET display_name = coalesce(%(name)s, display_name), role = coalesce(%(role)s, role),
                  email = CASE WHEN %(set_email)s THEN %(email)s ELSE email END,
                  active = coalesce(%(active)s, active),
                  token_version = token_version + CASE WHEN %(revoke)s THEN 1 ELSE 0 END
           WHERE username = %(u)s""",
        {
            "name": display_name.strip() if display_name else None,
            "role": role,
            "set_email": email_given,
            "email": email,
            "active": active,
            "revoke": revoke,
            "u": username,
        },
    )
    cache.account_changed(conn, username)
    after = public_view(load_account(conn, username))
    changed = {k: after[k] for k in ("display_name", "role", "email", "active") if after[k] != before[k]}
    if changed:
        audit(conn, actor, "sua_tai_khoan", "app_user", username, before={k: before[k] for k in changed}, after=changed)
    return after


def admin_reset_password(conn, actor: Actor, username: str, send_email: bool = False) -> dict:
    """Quản lý cấp lại mật khẩu tạm (người dùng quên mật khẩu mà không có email). Đăng xuất mọi phiên cũ."""
    require(actor, "user.admin")
    row = one(conn, ACCOUNT_SQL + " WHERE u.username = %s", (username,), "tài khoản")
    temp = temporary_password()
    _set_password(conn, username, temp, must_change=True)
    audit(conn, actor, "cap_lai_mat_khau", "app_user", username)
    email_error = _send_link(conn, row, "dat_lai") if send_email else None
    return {"mat_khau_tam": temp, "da_gui_email": send_email and email_error is None, "loi_email": email_error}


# ---------------------------------------------------------------- tài khoản học viên
def _username_for_student(conn, hv: dict) -> str:
    local = (hv["email"] or "").split("@")[0].lower()
    base = re.sub(r"[^a-z0-9._-]", "", local)[:24].strip("._-")
    if len(base) < 3:
        base = f"hv{hv['id']}"
    candidate, n = base, 1
    while conn.execute("SELECT 1 FROM app_user WHERE username = %s", (candidate,)).fetchone():
        n += 1
        candidate = f"{base}{n}"
    return candidate


def student_account(conn, actor: Actor, hoc_vien_id: int) -> dict | None:
    require(actor, "student.read")
    row = conn.execute(ACCOUNT_SQL + " WHERE u.hoc_vien_id = %s", (hoc_vien_id,)).fetchone()
    return public_view(row) if row else None


def create_student_account(conn, actor: Actor, hoc_vien_id: int, send_email: bool = True) -> dict:
    """Cấp tài khoản cổng học viên. Email chỉ chứa link tự đặt mật khẩu, không chứa mật khẩu."""
    require(actor, "student.account")
    hv = one(conn, "SELECT id, ho_ten, email FROM hoc_vien WHERE id = %s", (hoc_vien_id,), "học viên")
    if conn.execute("SELECT 1 FROM app_user WHERE hoc_vien_id = %s", (hoc_vien_id,)).fetchone():
        raise Conflict("Học viên này đã có tài khoản.")
    email = (hv["email"] or "").strip().lower() or None
    if email and conn.execute("SELECT 1 FROM app_user WHERE lower(email) = %s", (email,)).fetchone():
        raise Conflict(f"Email {email} đã gắn với một tài khoản khác. Sửa email học viên trước.")
    username = _username_for_student(conn, hv)
    temp = _insert(conn, username, hv["ho_ten"], "student", email, hoc_vien_id)
    audit(conn, actor, "tao_tai_khoan", "app_user", username, after={"role": "student", "hoc_vien_id": hoc_vien_id})
    row = load_account(conn, username)
    email_error = _send_link(conn, row, "kich_hoat") if send_email else None
    return {
        "user": public_view(row),
        "mat_khau_tam": temp,
        "da_gui_email": send_email and email_error is None,
        "loi_email": email_error,
    }


# ---------------------------------------------------------------- tài khoản quản lý đầu tiên (production)
def bootstrap_manager(conn, username: str, display_name: str, email: str | None, password: str | None) -> str | None:
    """Tạo tài khoản quản lý đầu tiên nếu hệ thống chưa có quản lý nào ĐANG HOẠT ĐỘNG. Trả mật khẩu tạm nếu tự sinh.

    Chỉ tính tài khoản active: dữ liệu mẫu có quản lý demo bị khoá khi lên production (disable_demo_accounts), nếu
    đếm cả tài khoản đó thì hệ thống không còn ai đăng nhập quản trị được."""
    if conn.execute("SELECT 1 FROM app_user WHERE role = 'manager' AND active").fetchone():
        return None
    if conn.execute("SELECT 1 FROM app_user WHERE username = %s", (username.strip().lower(),)).fetchone():
        raise RuleViolation(f"Tên '{username}' đã có nhưng không phải quản lý đang hoạt động; đặt ADMIN_USERNAME khác.")
    username = username.strip().lower()
    if not USERNAME_RE.match(username):
        raise RuleViolation("ADMIN_USERNAME không hợp lệ.")
    temp = None
    if password:
        validate_password(password, username)
    else:
        password = temp = temporary_password()
    conn.execute(
        """INSERT INTO app_user (username, password_hash, role, display_name, email, must_change_password)
           VALUES (%s, %s, 'manager', %s, %s, true)""",
        (username, hash_password(password), display_name, (email or "").strip().lower() or None),
    )
    return temp
