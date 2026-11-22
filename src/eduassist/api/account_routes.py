"""Endpoint tài khoản của chính người dùng: đổi mật khẩu, quên / đặt lại mật khẩu, đăng xuất mọi thiết bị.

Đăng nhập nằm ở main.py (đi qua Backend để test không cần DB).
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from eduassist.api.auth import AuthUser, create_token, current_user_any
from eduassist.api.fastjson import FastJSONRoute
from eduassist.api.platform import db
from eduassist.api.ratelimit import RateLimiter, client_ip, get_login_limiter
from eduassist.config import get_settings
from eduassist.services import accounts

router = APIRouter(tags=["tài khoản"], route_class=FastJSONRoute)


class ChangePasswordIn(BaseModel):
    mat_khau_cu: str = Field(min_length=1, max_length=128)
    mat_khau_moi: str = Field(min_length=1, max_length=128)


class ForgotIn(BaseModel):
    ten_dang_nhap_hoac_email: str = Field(min_length=3, max_length=254)


class ResetIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    mat_khau_moi: str = Field(min_length=1, max_length=128)


@router.get("/public/config", tags=["công khai"])
def public_config():
    """Cấu hình giao diện cần biết trước khi đăng nhập."""
    s = get_settings()
    return {"demo_mode": s.demo_mode, "production": s.is_production}


@router.post("/auth/change-password")
def change_password(
    body: ChangePasswordIn,
    request: Request,
    user: AuthUser = Depends(current_user_any),
    conn=Depends(db, scope="function"),
    limiter: RateLimiter = Depends(get_login_limiter),
):
    """Đổi mật khẩu. Mọi phiên khác bị đăng xuất; trả token mới cho phiên hiện tại."""
    limiter.check(f"pw:{client_ip(request)}")
    row = accounts.change_password(conn, user.username, body.mat_khau_cu, body.mat_khau_moi)
    return {"access_token": create_token(AuthUser.from_row(row)), "token_type": "bearer"}


@router.post("/auth/forgot-password")
def forgot_password(
    body: ForgotIn,
    request: Request,
    conn=Depends(db, scope="function"),
    limiter: RateLimiter = Depends(get_login_limiter),
):
    limiter.check(f"forgot:{client_ip(request)}")
    accounts.request_password_reset(conn, body.ten_dang_nhap_hoac_email)
    # Cùng một câu trả lời dù tài khoản có tồn tại hay không -> không dò được ai có tài khoản
    return {
        "message": "Nếu thông tin khớp với một tài khoản có email, trung tâm đã gửi link đặt lại mật khẩu. "
        "Kiểm tra hộp thư (cả mục Spam)."
    }


@router.get("/auth/reset-token")
def check_reset_token(
    token: str, request: Request, conn=Depends(db, scope="function"), limiter=Depends(get_login_limiter)
):
    limiter.check(f"reset:{client_ip(request)}")
    return accounts.check_link(conn, token)


@router.post("/auth/reset-password")
def reset_password(
    body: ResetIn,
    request: Request,
    conn=Depends(db, scope="function"),
    limiter: RateLimiter = Depends(get_login_limiter),
):
    limiter.check(f"reset:{client_ip(request)}")
    accounts.reset_password(conn, body.token, body.mat_khau_moi)
    return {"message": "Đã đặt mật khẩu mới. Bạn có thể đăng nhập."}


@router.post("/auth/logout-all")
def logout_all(user: AuthUser = Depends(current_user_any), conn=Depends(db, scope="function")):
    """Đăng xuất khỏi mọi thiết bị (token đang dùng cũng hết hiệu lực)."""
    accounts.logout_everywhere(conn, user.username)
    return {"ok": True}
