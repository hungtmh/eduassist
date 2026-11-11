from datetime import date, timedelta

import pytest

from eduassist.agents.action import parse_deadline
from eduassist.services.actions import bulk_reminder_mail, reminder_mail


def test_parse_deadline_accepts_both_formats():
    d = date.today() + timedelta(days=10)
    assert parse_deadline(d.strftime("%d/%m/%Y")) == d
    assert parse_deadline(d.isoformat()) == d


@pytest.mark.parametrize("days", [0, -3, 61])
def test_parse_deadline_rejects_out_of_range(days):
    with pytest.raises(ValueError):
        parse_deadline((date.today() + timedelta(days=days)).strftime("%d/%m/%Y"))


def test_parse_deadline_rejects_garbage():
    with pytest.raises(ValueError):
        parse_deadline("tuần sau")


def test_bulk_reminder_is_personalised_and_formats_money():
    subject, body = bulk_reminder_mail({"ho_ten": "Lê Văn A", "con_no": 4_800_000}, "2026-12-15", "Ưu đãi tháng 12")
    assert "Nhắc thanh toán" in subject
    assert "Lê Văn A" in body and "4.800.000đ" in body and "15/12/2026" in body and "Ưu đãi tháng 12" in body


def test_tiered_reminder_wording_differs_before_and_after_due():
    item = {"ho_ten": "B", "so_thu_tu": 2, "ma_lop": "ENG-01", "so_tien_dot": 4_450_000, "han": "2026-11-20"}
    s1, b1 = reminder_mail(item, "truoc_han_3")
    s2, b2 = reminder_mail(item, "qua_han_7")
    assert "đến hạn ngày 20/11/2026" in b1 and "quá hạn" not in s1
    assert "quá hạn" in s2 and "tạm dừng" in b2 and "4.450.000đ" in b2
