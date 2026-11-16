"""Che thông tin liên hệ cá nhân (email, số điện thoại) trước khi dữ liệu đi tới nhà cung cấp LLM.

LLM chạy ở nước ngoài (Groq), nên dữ liệu học viên do code đưa vào prompt - kết quả SQL, ghi chú khách - được
che bằng hàm ở đây. Họ tên vẫn giữ vì câu trả lời cần nêu tên. Địa chỉ email để GỬI thư luôn do code lấy từ DB
theo id, LLM không cần thấy.

Không che được nội dung người dùng tự gõ vào khung chat - điều này cần ghi trong chính sách quyền riêng tư.
"""

import re

from eduassist.config import get_settings

EMAIL_MASK = "[email đã ẩn]"
PHONE_MASK = "[SĐT đã ẩn]"

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Số Việt Nam: 0xxxxxxxxx / +84xxxxxxxxx / 84xxxxxxxxx, cho phép dấu cách, chấm, gạch giữa các nhóm số
PHONE_RE = re.compile(r"(?<![\d])(?:\+?84|0)(?:[\s.-]?\d){8,10}(?![\d])")
PII_COLUMNS = {"email", "so_dien_thoai", "sdt", "dien_thoai", "phone"}


def enabled() -> bool:
    return get_settings().llm_mask_pii


def mask_text(text: str) -> str:
    if not text or not enabled():
        return text
    return PHONE_RE.sub(PHONE_MASK, EMAIL_RE.sub(EMAIL_MASK, text))


def mask_cell(column: str, value):
    """Che một ô kết quả SQL: theo tên cột (kể cả alias như hv_email) và theo nội dung chuỗi."""
    if value is None or not enabled():
        return value
    col = column.lower()
    if any(col == c or col.endswith(f"_{c}") or col.startswith(f"{c}_") for c in PII_COLUMNS):
        return EMAIL_MASK if "mail" in col else PHONE_MASK
    if isinstance(value, str):
        return mask_text(value)
    return value
