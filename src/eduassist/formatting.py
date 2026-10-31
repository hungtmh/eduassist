"""Định dạng số kiểu Việt Nam NGAY TRONG kết quả tool.

Lý do: nếu tool trả "4,800,000" mà câu trả lời cần "4.800.000", LLM phải tự đổi định dạng và
đã từng làm sai một chữ số (4.800.500). Đưa sẵn đúng định dạng -> LLM chỉ việc chép.
"""

import unicodedata


def vn_number(n: int | float) -> str:
    if isinstance(n, float) and not n.is_integer():
        return f"{n:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{int(n):,}".replace(",", ".")


def vnd(n: int | float) -> str:
    return f"{vn_number(n)}đ"


def fold(text: str) -> str:
    """Bỏ dấu + chữ thường + chỉ giữ chữ/số: so khớp "03_bao_lưu_hoàn_tiền.md" với "03_bao_luu_hoan_tien.md"."""
    text = text.lower().replace("đ", "d")
    text = "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")
    return "".join(ch for ch in text if ch.isalnum())
