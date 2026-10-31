from datetime import date
from decimal import Decimal

from eduassist.evals.metrics import fact_present, is_refusal, numbers_in, results_match


def test_results_match_ignores_order_and_extra_columns():
    gold = [("sang", 74), ("toi", 343)]
    pred = [(343, "toi", "Tối"), (74, "sang", "Sáng")]
    assert results_match(gold, pred)


def test_results_match_numeric_types():
    assert results_match([(Decimal("6025000"),)], [(6025000.0,)])
    assert results_match([(Decimal("30.0"),)], [(30,)])


def test_results_match_detects_wrong_value_and_row_count():
    assert not results_match([(8,)], [(9,)])
    assert not results_match([("a", 1)], [("a", 1), ("b", 2)])


def test_results_match_each_pred_row_used_once():
    assert not results_match([(1,), (1,)], [(1,), (2,)])


def test_results_match_accent_insensitive_text_and_dates():
    assert results_match([("Tiếng Anh", date(2026, 1, 1))], [("tieng anh", "2026-01-01")])


def test_fact_present_number_formats():
    assert fact_present("Phí bảo lưu là 300 000 đồng", "300.000")
    assert fact_present("được hoàn 70 % học phí", "70%")
    assert fact_present("chia làm hai đợt", "2 đợt|hai đợt")
    assert not fact_present("hoàn 100%", "70%")


def test_is_refusal():
    assert is_refusal("Mình chưa tìm thấy thông tin này trong tài liệu của trung tâm.")
    assert not is_refusal("Được hoàn 100%.")


def test_numbers_in():
    assert numbers_in("Doanh thu 422.152.500đ, tăng 12%") == {"422152500"}
