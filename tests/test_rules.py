"""Luật nghiệp vụ dạng hàm thuần: kiểm thử từng luật, từng ngưỡng, từng hướng chuyển trạng thái (không cần DB)."""

from datetime import date, timedelta

import pytest

from eduassist.services import rules
from eduassist.services.core import RuleViolation, check_transition

D = date(2026, 11, 11)  # thứ Tư


# ---------------------------------------------------------------- ưu đãi
@pytest.mark.parametrize(
    ("promo", "voucher", "pct"),
    [(0, 0, 0), (10, 0, 10), (0, 30, 30), (7, 5, 12), (10, 10, 15), (5, 30, 15)],
)
def test_discount_never_stacks_beyond_cap(promo, voucher, pct):
    d = rules.compute_discount(6_000_000, promo, voucher)
    assert d.percent == pct
    assert d.amount == 6_000_000 * pct // 100


# ---------------------------------------------------------------- trả góp
def test_full_payment_single_installment_due_in_3_days():
    assert rules.installment_plan(3_900_000, False, D, None) == [(3_900_000, D + timedelta(days=3))]


def test_installments_split_in_two_and_second_before_session_10():
    due2 = D + timedelta(days=25)
    plan = rules.installment_plan(8_900_001, True, D, due2)
    assert [a for a, _ in plan] == [4_450_000, 4_450_001]  # tổng đúng tới từng đồng
    assert plan[1][1] == due2


def test_second_installment_never_earlier_than_a_week():
    plan = rules.installment_plan(8_000_000, True, D, D + timedelta(days=2))
    assert plan[1][1] == D + timedelta(days=7)


# ---------------------------------------------------------------- hoàn phí (03 › Hoàn học phí)
@pytest.mark.parametrize(
    ("days_before", "sessions", "rate"),
    [(10, 0, 100), (7, 0, 100), (6, 0, 70), (0, 0, 70), (-5, 2, 70), (-10, 3, 0), (-20, 8, 0)],
)
def test_refund_rate_by_cancellation_time(days_before, sessions, rate):
    got, basis = rules.refund_rate(D, D + timedelta(days=days_before), sessions)
    assert got == rate
    assert basis


def test_refund_full_when_class_cancelled_even_after_start():
    assert rules.refund_rate(D, D - timedelta(days=30), 10, class_cancelled=True)[0] == 100


# ---------------------------------------------------------------- lịch học & trùng lịch
def test_session_dates_follow_weekdays():
    dates = rules.session_dates(D, "T2-T4-T6", 4)  # D là thứ Tư
    assert [d.weekday() for d in dates] == [2, 4, 0, 2]
    assert dates[0] == D


def test_invalid_schedule_rejected():
    with pytest.raises(ValueError):
        rules.weekdays("T2-T9")


def _slot(start_offset, schedule="T2-T4-T6", shift="toi", weeks=4):
    s = D + timedelta(days=start_offset)
    return rules.Slot(s, s + timedelta(weeks=weeks), shift, schedule)


def test_overlap_same_shift_shared_day_and_dates():
    assert rules.slots_overlap(_slot(0), _slot(7, "T4-T7"))


@pytest.mark.parametrize(
    "other",
    [_slot(0, shift="sang"), _slot(0, "T3-T5-T7"), _slot(60)],
    ids=["khác ca", "khác ngày trong tuần", "không giao khoảng ngày"],
)
def test_no_overlap(other):
    assert not rules.slots_overlap(_slot(0), other)


# ---------------------------------------------------------------- chuyên cần & chứng nhận (04 › Chuyên cần)
def test_attendance_late_counts_half():
    assert rules.attendance_rate(["co_mat", "di_tre", "vang", "co_mat"]) == pytest.approx(0.625)


def test_consecutive_absences_counts_from_newest():
    assert rules.consecutive_absences(["vang", "vang", "co_mat", "vang"]) == 2
    assert rules.consecutive_absences(["vang_co_phep", "vang"]) == 0  # vắng có phép không tính chuỗi bỏ học


@pytest.mark.parametrize(
    ("statuses", "score", "ok"),
    [
        (["co_mat"] * 8 + ["vang"] * 2, 60, True),  # đúng 80%
        (["co_mat"] * 7 + ["vang"] * 3, 90, False),  # 70% < 80%
        (["co_mat"] * 10, 49, False),
        (["co_mat"] * 10, None, False),
    ],
)
def test_certificate_requires_attendance_and_score(statuses, score, ok):
    assert rules.certificate_eligible(statuses, score)[0] is ok


# ---------------------------------------------------------------- bậc nhắc nợ
@pytest.mark.parametrize(
    ("days_from_due", "tier"),
    [
        (-10, None),
        (-4, None),
        (-3, "truoc_han_3"),
        (0, "truoc_han_3"),
        (1, "qua_han_1"),
        (6, "qua_han_1"),
        (7, "qua_han_7"),
        (13, "qua_han_7"),
        (14, "tam_dung"),
        (40, "tam_dung"),
    ],
)
def test_debt_tier_thresholds(days_from_due, tier):
    assert rules.debt_tier(D - timedelta(days=days_from_due), D) == tier


# ---------------------------------------------------------------- chấm điểm khách
def test_lead_score_bounded_and_rewards_specific_needs():
    vague = rules.lead_score("tiktok", False, "", False, 30, "moi")
    rich = rules.lead_score("gioi_thieu", True, "Muốn học IELTS buổi tối để đi du học năm sau", True, 0, "hen_hoc_thu")
    assert 0 <= vague < rich <= 100


# ---------------------------------------------------------------- máy trạng thái
LEAD_OK = [
    ("moi", "da_lien_he"),
    ("da_lien_he", "hen_hoc_thu"),
    ("hen_hoc_thu", "da_ghi_danh"),
    ("moi", "khong_tiep_tuc"),
    ("khong_tiep_tuc", "da_lien_he"),
]
LEAD_BAD = [("moi", "da_ghi_danh"), ("moi", "hen_hoc_thu"), ("da_ghi_danh", "moi"), ("khong_tiep_tuc", "da_ghi_danh")]
ENR_OK = [
    ("cho_thanh_toan", "dang_hoc"),
    ("dang_hoc", "bao_luu"),
    ("bao_luu", "dang_hoc"),
    ("dang_hoc", "tam_dung"),
    ("tam_dung", "dang_hoc"),
    ("dang_hoc", "hoan_thanh"),
    ("dang_hoc", "da_huy"),
    ("cho_thanh_toan", "da_huy"),
]
ENR_BAD = [("hoan_thanh", "dang_hoc"), ("da_huy", "dang_hoc"), ("cho_thanh_toan", "bao_luu"), ("bao_luu", "tam_dung")]
PROP_OK = [
    ("cho_duyet", "da_duyet"),
    ("cho_duyet", "tu_choi"),
    ("cho_duyet", "het_han"),
    ("da_duyet", "da_thuc_hien"),
    ("da_duyet", "that_bai"),
    ("goi_y", "da_xem"),
]
PROP_BAD = [
    ("tu_choi", "da_duyet"),
    ("da_thuc_hien", "da_duyet"),
    ("het_han", "da_duyet"),
    ("goi_y", "da_duyet"),
    ("cho_duyet", "da_thuc_hien"),
]


@pytest.mark.parametrize(
    ("table", "a", "b"),
    [(rules.LEAD_TRANSITIONS, a, b) for a, b in LEAD_OK]
    + [(rules.ENROLLMENT_TRANSITIONS, a, b) for a, b in ENR_OK]
    + [(rules.PROPOSAL_TRANSITIONS, a, b) for a, b in PROP_OK],
)
def test_allowed_transitions(table, a, b):
    check_transition("x", table, a, b)


@pytest.mark.parametrize(
    ("table", "a", "b"),
    [(rules.LEAD_TRANSITIONS, a, b) for a, b in LEAD_BAD]
    + [(rules.ENROLLMENT_TRANSITIONS, a, b) for a, b in ENR_BAD]
    + [(rules.PROPOSAL_TRANSITIONS, a, b) for a, b in PROP_BAD],
)
def test_forbidden_transitions(table, a, b):
    with pytest.raises(RuleViolation):
        check_transition("x", table, a, b)
