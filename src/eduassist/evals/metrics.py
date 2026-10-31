"""Hàm chấm điểm thuần (không gọi LLM) - có unit test riêng."""

import re
from collections import Counter
from datetime import date, datetime
from decimal import Decimal

from eduassist.formatting import fold, is_refusal

__all__ = ["fact_present", "is_refusal", "numbers_in", "results_match"]


def _norm_value(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float, Decimal)):
        return round(float(v), 1)
    if isinstance(v, (date, datetime)):
        return fold(v.isoformat()[:10])  # cùng cách chuẩn hoá với chuỗi "2026-01-01"
    return fold(str(v))


def results_match(gold: list[tuple], pred: list[tuple]) -> bool:
    """Execution accuracy: cùng số dòng và mỗi dòng gold có một dòng pred (khác nhau) chứa đủ các giá trị của nó.

    Không phụ thuộc thứ tự dòng, thứ tự cột, tên cột; cho phép pred có thêm cột (VD: thêm cột mã khoá học).
    """
    if len(gold) != len(pred):
        return False
    remaining = [Counter(_norm_value(v) for v in row) for row in pred]
    for row in gold:
        need = Counter(_norm_value(v) for v in row)
        idx = next((i for i, have in enumerate(remaining) if not need - have), None)
        if idx is None:
            return False
        remaining.pop(idx)
    return True


def _norm_text(s: str) -> str:
    s = s.lower()
    s = re.sub(r"(?<=\d)[.,\s](?=\d{3}(?!\d))", "", s)  # 300.000 / 300,000 / 300 000 -> 300000
    s = re.sub(r"\s+%", "%", s)  # "70 %" -> "70%"
    return re.sub(r"\s+", " ", s)


def fact_present(answer: str, fact: str) -> bool:
    """fact có thể có nhiều cách viết, phân tách bằng '|'."""
    text = _norm_text(answer)
    return any(_norm_text(alt) in text for alt in fact.split("|"))


def numbers_in(text: str) -> set[str]:
    """Các số có từ 4 chữ số trở lên (đã bỏ dấu phân cách) - dùng kiểm tra LLM có bịa số liệu không."""
    return set(re.findall(r"\d{4,}", _norm_text(text)))
