"""Đăng nhập & JWT. Vai trò (role) nằm trong token đã ký -> agent tin vào token, không tin vào nội dung chat."""

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from eduassist.config import get_settings
from eduassist.db import app_pool
from eduassist.security.passwords import verify_password

ALGORITHM = "HS256"
bearer = HTTPBearer(auto_error=False)


class AuthUser:
    def __init__(self, username: str, role: str, display_name: str, hoc_vien_id: int | None):
        self.username = username
        self.role = role
        self.display_name = display_name
        self.hoc_vien_id = hoc_vien_id

    @property
    def is_staff(self) -> bool:
        return self.role in ("staff", "manager")


def authenticate(username: str, password: str) -> AuthUser | None:
    with app_pool().connection() as conn:
        row = conn.execute(
            "SELECT username, password_hash, role, display_name, hoc_vien_id FROM app_user WHERE username = %s",
            (username,),
        ).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return AuthUser(row["username"], row["role"], row["display_name"], row["hoc_vien_id"])


def create_token(user: AuthUser) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": user.username,
        "role": user.role,
        "name": user.display_name,
        "hv": user.hoc_vien_id,
        "iat": now,
        "exp": now + timedelta(minutes=s.jwt_ttl_minutes),
    }
    return jwt.encode(claims, s.jwt_secret.get_secret_value(), algorithm=ALGORITHM)


def decode_token(token: str) -> AuthUser:
    try:
        c = jwt.decode(token, get_settings().jwt_secret.get_secret_value(), algorithms=[ALGORITHM])
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token không hợp lệ hoặc đã hết hạn") from e
    if c.get("role") not in ("student", "staff", "manager"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token không hợp lệ")
    return AuthUser(c["sub"], c["role"], c["name"], c.get("hv"))


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> AuthUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Cần đăng nhập", headers={"WWW-Authenticate": "Bearer"})
    return decode_token(creds.credentials)
