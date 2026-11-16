"""Đăng nhập & JWT.

Token chỉ chứa tên đăng nhập và token_version. Mỗi request đọc lại tài khoản (DB, hoặc cache Redis 30 giây được xoá
ngay khi tài khoản đổi - eduassist/cache.py), nên khoá tài khoản, đổi vai trò hay đổi mật khẩu có hiệu lực NGAY (token
cũ có token_version cũ -> 401), không phải chờ token hết hạn.
Agent tin vào vai trò lấy từ DB, không tin vào nội dung chat.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from eduassist.config import get_settings
from eduassist.services.core import ROLES, Actor

ALGORITHM = "HS256"
bearer = HTTPBearer(auto_error=False)
MUST_CHANGE_DETAIL = "Bạn cần đổi mật khẩu trước khi tiếp tục."


class AuthUser:
    def __init__(
        self,
        username: str,
        role: str,
        display_name: str,
        hoc_vien_id: int | None,
        giang_vien_id: int | None = None,
        token_version: int = 0,
        must_change_password: bool = False,
    ):
        self.username = username
        self.role = role
        self.display_name = display_name
        self.hoc_vien_id = hoc_vien_id
        self.giang_vien_id = giang_vien_id
        self.token_version = token_version
        self.must_change_password = must_change_password

    @classmethod
    def from_row(cls, row: dict) -> "AuthUser":
        return cls(
            row["username"],
            row["role"],
            row["display_name"],
            row["hoc_vien_id"],
            row.get("giang_vien_id"),
            row.get("token_version", 0),
            row.get("must_change_password", False),
        )

    @property
    def is_staff(self) -> bool:
        return self.role != "student"

    def actor(self) -> Actor:
        return Actor(id=self.username, role=self.role, hoc_vien_id=self.hoc_vien_id, giang_vien_id=self.giang_vien_id)


# ---------------------------------------------------------------- đọc tài khoản (tests thay bằng bản giả)
UserLoader = Callable[[str], AuthUser | None]


_CACHED_FIELDS = (
    "username",
    "role",
    "display_name",
    "hoc_vien_id",
    "giang_vien_id",
    "token_version",
    "must_change_password",
    "active",
)


def _load_from_db(username: str) -> AuthUser | None:
    from eduassist import cache
    from eduassist.db import auth_pool
    from eduassist.services.accounts import load_account

    row = cache.get_account(username)
    if row is None:
        # Pool riêng: request có thể đang giữ một kết nối app_pool (dependency `db`) khi tới bước này
        with auth_pool().connection() as conn:
            found = load_account(conn, username)
        if found is None:
            return None
        row = {k: found.get(k) for k in _CACHED_FIELDS}
        cache.put_account(username, row)
    if not row["active"]:
        return None
    return AuthUser.from_row(row)


@lru_cache
def get_user_loader() -> UserLoader:
    return _load_from_db


def authenticate(username: str, password: str) -> AuthUser | None:
    """Raise AccountLocked (429) khi tài khoản đang bị khoá tạm."""
    from eduassist.db import app_pool
    from eduassist.services.accounts import login

    # Kết nối autocommit, KHÔNG bọc transaction: bộ đếm sai mật khẩu phải được lưu cả khi đăng nhập thất bại
    with app_pool().connection() as conn:
        row = login(conn, username, password)
    return AuthUser.from_row(row) if row else None


# ---------------------------------------------------------------- token
def create_token(user: AuthUser) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": user.username,
        "ver": user.token_version,
        "role": user.role,  # chỉ để giao diện đọc nhanh; server luôn lấy vai trò từ DB
        "iat": now,
        "exp": now + timedelta(minutes=s.jwt_ttl_minutes),
    }
    return jwt.encode(claims, s.jwt_secret.get_secret_value(), algorithm=ALGORITHM)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def current_user_any(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    loader: UserLoader = Depends(get_user_loader),
) -> AuthUser:
    """Người dùng đã đăng nhập, kể cả khi đang bị bắt đổi mật khẩu (dùng cho /me/profile, đổi mật khẩu)."""
    if creds is None:
        raise _unauthorized("Cần đăng nhập")
    try:
        c = jwt.decode(creds.credentials, get_settings().jwt_secret.get_secret_value(), algorithms=[ALGORITHM])
    except jwt.PyJWTError as e:
        raise _unauthorized("Token không hợp lệ hoặc đã hết hạn") from e
    user = loader(str(c.get("sub", "")))
    if user is None or user.role not in ROLES:
        raise _unauthorized("Tài khoản không còn hoạt động. Liên hệ quản lý trung tâm.")
    if c.get("ver") != user.token_version:
        raise _unauthorized("Phiên đăng nhập đã kết thúc (mật khẩu hoặc quyền vừa thay đổi). Đăng nhập lại.")
    return user


def current_user(user: AuthUser = Depends(current_user_any)) -> AuthUser:
    if user.must_change_password:
        raise HTTPException(status.HTTP_403_FORBIDDEN, MUST_CHANGE_DETAIL, headers={"X-Must-Change-Password": "1"})
    return user
