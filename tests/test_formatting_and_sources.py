import pytest

from eduassist.agents import supervisor
from eduassist.formatting import fold, vn_number, vnd


def test_vn_number_formats():
    assert vnd(4_800_000) == "4.800.000đ"
    assert vn_number(-1_234_567) == "-1.234.567"
    assert vn_number(12.5) == "12,50"


def test_fold_ignores_accents_and_punctuation():
    assert fold("03_bao_lưu_hoàn_tiền.md › Hoàn học phí") == fold("03_bao_luu_hoan_tien.md › Hoàn học phí")
    assert fold("Đà Nẵng") == "danang"


@pytest.fixture
def fake_sources(monkeypatch):
    names = ["02_hoc_phi_va_uu_dai.md › Trả góp học phí", "03_bao_luu_hoan_tien.md › Hoàn học phí"]
    monkeypatch.setattr(supervisor, "known_sources", lambda: {fold(n): n for n in names})


def test_verified_sources_keeps_real_and_drops_invented(fake_sources):
    answer = (
        "Được hoàn 70%. (Nguồn: 03_bao_lưu_hoàn_tiền.md › Hoàn học phí) Thêm ý.\n"
        "Nguồn: 02_hoc_phi_va_uu_dai.md › Trả góp học phí; 99_bia.md › Không tồn tại\n"
        "Nguồn: my_enrollments"
    )
    assert supervisor.verified_sources(answer) == [
        "03_bao_luu_hoan_tien.md › Hoàn học phí",
        "02_hoc_phi_va_uu_dai.md › Trả góp học phí",
    ]


def test_verified_sources_formats_seen_in_eval(fake_sources):
    # Các dạng LLM thực sự đã ghi trong lần chạy eval: chép thẻ XML, nguồn nằm trong ngoặc có ngoặc lồng
    answer = (
        'Hoàn 100%.\n  Nguồn: <tai_lieu nguon="03_bao_luu_hoan_tien.md › Hoàn học phí">.\n'
        "Nguồn: Trả góp (nguồn: 02_hoc_phi_va_uu_dai.md › Trả góp học phí)"
    )
    assert supervisor.verified_sources(answer) == [
        "03_bao_luu_hoan_tien.md › Hoàn học phí",
        "02_hoc_phi_va_uu_dai.md › Trả góp học phí",
    ]


def test_verified_sources_deduplicates(fake_sources):
    answer = "Nguồn: 03_bao_luu_hoan_tien.md › Hoàn học phí\nNguồn: 03_bao_luu_hoan_tien.md › Hoàn học phí"
    assert supervisor.verified_sources(answer) == ["03_bao_luu_hoan_tien.md › Hoàn học phí"]
