from datetime import date, timedelta

import pytest

from eduassist.agents.action import describe_reminders, parse_deadline, reminder_email


def test_parse_deadline_accepts_both_formats():
    d = date.today() + timedelta(days=10)
    assert parse_deadline(d.strftime("%d/%m/%Y")) == d
    assert parse_deadline(d.isoformat()) == d


@pytest.mark.parametrize("days", [0, -1, 61])
def test_parse_deadline_rejects_out_of_range(days):
    with pytest.raises(ValueError):
        parse_deadline((date.today() + timedelta(days=days)).strftime("%d/%m/%Y"))


def test_parse_deadline_rejects_garbage():
    with pytest.raises(ValueError):
        parse_deadline("cuối tháng")


def test_reminder_email_is_personalised_and_formats_money():
    subject, body = reminder_email({"ho_ten": "Nguyễn Văn A", "con_no": 4800000}, date(2026, 12, 15), "Ghi chú")
    assert "Nhắc thanh toán" in subject
    assert "Kính gửi Nguyễn Văn A" in body
    assert "4.800.000đ" in body
    assert "15/12/2026" in body
    assert "Ghi chú" in body


def test_describe_reminders_reports_bad_deadline_without_db():
    text = describe_reminders({"args": {"han_thanh_toan": "abc"}}, None, None)
    assert "không hợp lệ" in text
