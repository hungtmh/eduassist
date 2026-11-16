"""Luật mật khẩu, cấu hình production, che dữ liệu cá nhân trước khi gửi LLM (không cần DB / LLM)."""

import pytest
from pydantic import ValidationError

from eduassist.config import Settings
from eduassist.security.pii import EMAIL_MASK, PHONE_MASK, mask_cell, mask_text
from eduassist.security.sql_runner import QueryResult
from eduassist.services.accounts import temporary_password, validate_password
from eduassist.services.core import RuleViolation


# ---------------------------------------------------------------- mật khẩu
@pytest.mark.parametrize(
    "pw",
    ["ngan1", "chikhongcoso", "12345678901", "demo123", "Matkhau123", "abc12345", "an.nguyen2026"],
)
def test_weak_passwords_rejected(pw):
    with pytest.raises(RuleViolation):
        validate_password(pw, username="an.nguyen")


@pytest.mark.parametrize("pw", ["Hoa-sen-2026", "mặttrời9giờ", "xK7pq2Lm"])
def test_good_passwords_accepted(pw):
    validate_password(pw, username="an.nguyen")


def test_temporary_password_passes_policy_and_is_unique():
    pws = {temporary_password() for _ in range(200)}
    assert len(pws) == 200
    for pw in list(pws)[:50]:
        validate_password(pw, "quanly")
        assert not set(pw) & set("0O1lI")  # không có ký tự dễ đọc nhầm


# ---------------------------------------------------------------- cấu hình production
PROD_OK = {
    "app_env": "production",
    "jwt_secret": "x" * 48,
    "agent_ro_password": "ro-strong-password",
    "database_url": "postgresql://app_rw:strong-pw@db:5432/eduassist",
    "agent_ro_url": "postgresql://agent_ro:ro-strong-password@db:5432/eduassist",
    "cors_origins": "https://app.anhduong.vn",
    "smtp_host": "smtp.example.com",
    "smtp_security": "starttls",
}


def test_production_accepts_strong_config():
    s = Settings(_env_file=None, **PROD_OK)
    assert s.is_production


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("jwt_secret", "dev-only-change-me"),
        ("jwt_secret", "short"),
        ("agent_ro_password", "agent_ro_dev_pw"),
        ("database_url", "postgresql://app_rw:app_rw_dev_pw@db:5432/eduassist"),
        ("cors_origins", "*"),
        ("smtp_security", "none"),
    ],
)
def test_production_refuses_dev_defaults(field, value):
    with pytest.raises(ValidationError, match="production"):
        Settings(_env_file=None, **{**PROD_OK, field: value})


def test_development_allows_defaults():
    assert not Settings(_env_file=None).is_production


# ---------------------------------------------------------------- che dữ liệu cá nhân
@pytest.mark.parametrize(
    "text",
    [
        "Liên hệ an.nguyen@gmail.com để tư vấn",
        "Gọi 0901234567 giúp em",
        "SĐT 090 123 4567",
        "số +84 901.234.567 nhé",
    ],
)
def test_mask_text_hides_contacts(text):
    masked = mask_text(text)
    assert "@gmail" not in masked
    assert not any(ch.isdigit() for ch in masked.replace("[SĐT đã ẩn]", ""))


def test_mask_text_keeps_money_and_dates():
    text = "Học phí 4.500.000đ, khai giảng 2026-12-01, lớp ENG-B1-03"
    assert mask_text(text) == text


@pytest.mark.parametrize(
    ("col", "value", "expected"),
    [
        ("email", "a@b.vn", EMAIL_MASK),
        ("hv_email", "a@b.vn", EMAIL_MASK),
        ("so_dien_thoai", "0901234567", PHONE_MASK),
        ("ho_ten", "Nguyễn Văn An", "Nguyễn Văn An"),
        ("lien_he", "an@x.com", EMAIL_MASK),  # alias lạ vẫn bị che nhờ kiểm tra nội dung
        ("con_no", 1500000, 1500000),
    ],
)
def test_mask_cell(col, value, expected):
    assert mask_cell(col, value) == expected


def test_sql_result_shown_to_llm_is_masked():
    r = QueryResult(
        "SELECT ...", ["id", "ho_ten", "email", "so_dien_thoai"], [(7, "Trần Bình", "binh@x.vn", "0987654321")]
    )
    md = r.to_markdown()
    assert "Trần Bình" in md and "binh@x.vn" not in md and "0987654321" not in md


def test_masking_can_be_disabled(monkeypatch):
    from eduassist import config

    monkeypatch.setenv("LLM_MASK_PII", "false")
    config.get_settings.cache_clear()
    try:
        assert mask_text("a@b.vn") == "a@b.vn"
    finally:
        monkeypatch.delenv("LLM_MASK_PII")
        config.get_settings.cache_clear()
