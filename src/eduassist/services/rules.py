"""Luật nghiệp vụ dạng HÀM THUẦN (không đụng DB) - kiểm thử được từng luật, từng hướng chuyển trạng thái.

Ngưỡng lấy từ bộ chính sách giả lập trong data/policies/ (02 học phí, 03 bảo lưu-hoàn tiền, 04 quy chế).
"""

from dataclasses import dataclass
from datetime import date, timedelta

# ---------------------------------------------------------------- máy trạng thái (mục 5 của đề xuất)
LEAD_TRANSITIONS = {
    "moi": {"da_lien_he", "khong_tiep_tuc"},
    "da_lien_he": {"hen_hoc_thu", "da_ghi_danh", "khong_tiep_tuc"},
    "hen_hoc_thu": {"da_ghi_danh", "da_lien_he", "khong_tiep_tuc"},
    "khong_tiep_tuc": {"da_lien_he"},  # khách quay lại
    "da_ghi_danh": set(),
}
LEAD_LABEL = {
    "moi": "Mới",
    "da_lien_he": "Đã liên hệ",
    "hen_hoc_thu": "Hẹn học thử",
    "da_ghi_danh": "Đã ghi danh",
    "khong_tiep_tuc": "Không tiếp tục",
}

ENROLLMENT_TRANSITIONS = {
    "cho_thanh_toan": {"dang_hoc", "da_huy"},
    "dang_hoc": {"bao_luu", "tam_dung", "hoan_thanh", "da_huy"},
    "bao_luu": {"dang_hoc", "hoan_thanh", "da_huy"},  # quá 6 tháng không quay lại -> xem như hoàn thành
    "tam_dung": {"dang_hoc", "da_huy"},
    "hoan_thanh": set(),
    "da_huy": set(),
}
ACTIVE_ENROLLMENT = ("cho_thanh_toan", "dang_hoc", "tam_dung")  # đang chiếm chỗ trong lớp

PROPOSAL_TRANSITIONS = {
    "goi_y": {"da_xem"},
    "cho_duyet": {"da_duyet", "tu_choi", "het_han"},
    "da_duyet": {"da_thuc_hien", "that_bai"},
}

CLASS_TRANSITIONS = {
    "sap_khai_giang": {"dang_hoc", "da_huy"},
    "dang_hoc": {"da_ket_thuc"},
}

# ---------------------------------------------------------------- tài chính
INSTALLMENT_MIN_FEE = 5_000_000  # 02 › Trả góp học phí
INSTALLMENT_DUE_SESSION = 10  # đợt 2 đóng trước buổi học thứ 10
SUSPEND_AFTER_DAYS = 14  # quá 14 ngày sau hạn -> tạm dừng
VOUCHER_STACK_CAP = 15  # voucher cộng với ưu đãi khác: tổng không quá 15%
PROMOTIONS = {  # 02 › Các chương trình ưu đãi (không cộng dồn với nhau)
    "dang_ky_som": 10,
    "nhom": 7,
    "hoc_vien_cu": 5,
    "hssv": 5,
}
EARLY_BIRD_DAYS = 14
RESERVATION_FEE = 300_000  # 03 › Bảo lưu
RESERVATION_MAX_MONTHS = 6


@dataclass(frozen=True)
class Discount:
    percent: int
    amount: int
    note: str


def compute_discount(fee: int, promotion_pct: int = 0, voucher_pct: int = 0) -> Discount:
    """Ưu đãi không cộng dồn; voucher được cộng thêm MỘT ưu đãi nhưng tổng không quá 15%.
    Chỉ có voucher (không ưu đãi khác) thì dùng nguyên mức voucher."""
    if promotion_pct and voucher_pct:
        pct = min(promotion_pct + voucher_pct, VOUCHER_STACK_CAP)
        note = f"ưu đãi {promotion_pct}% + voucher {voucher_pct}%" + (
            f", giới hạn {VOUCHER_STACK_CAP}%" if promotion_pct + voucher_pct > VOUCHER_STACK_CAP else ""
        )
    else:
        pct = promotion_pct or voucher_pct
        note = f"giảm {pct}%" if pct else "không giảm"
    return Discount(pct, fee * pct // 100, note)


def installment_plan(total: int, installments: bool, today: date, due_second: date | None) -> list[tuple[int, date]]:
    """[(số tiền, hạn)]. Trả góp: đợt 1 50% đóng khi đăng ký (hạn 3 ngày), đợt 2 phần còn lại trước buổi 10."""
    if not installments:
        return [(total, today + timedelta(days=3))]
    first = total // 2
    second_due = max(due_second or today + timedelta(days=30), today + timedelta(days=7))
    return [(first, today + timedelta(days=3)), (total - first, second_due)]


def refund_rate(today: date, class_start: date, sessions_done: int, class_cancelled: bool = False) -> tuple[int, str]:
    """03 › Hoàn học phí. Trả (tỉ lệ %, căn cứ)."""
    if class_cancelled:
        return 100, "Lớp không khai giảng do không đủ sĩ số: hoàn 100%."
    if (class_start - today).days >= 7:
        return 100, "Huỷ trước ngày khai giảng ít nhất 7 ngày: hoàn 100% học phí đã đóng."
    if sessions_done < 3:
        return 70, "Huỷ trong vòng 7 ngày trước khai giảng hoặc trước buổi học thứ 3: hoàn 70% học phí đã đóng."
    return 0, "Từ buổi học thứ 3 trở đi: không hoàn học phí (có thể bảo lưu hoặc chuyển nhượng)."


# ---------------------------------------------------------------- lịch học
WEEKDAY = {"T2": 0, "T3": 1, "T4": 2, "T5": 3, "T6": 4, "T7": 5, "CN": 6}


def weekdays(schedule: str) -> set[int]:
    try:
        return {WEEKDAY[d] for d in schedule.split("-")}
    except KeyError as e:
        raise ValueError(f"lịch học không hợp lệ: {schedule} (VD: T2-T4-T6)") from e


def session_dates(start: date, schedule: str, count: int) -> list[date]:
    """Ngày của từng buổi, bắt đầu từ ngày khai giảng (hoặc ngày học đầu tiên sau đó)."""
    days = weekdays(schedule)
    out, d = [], start
    while len(out) < count:
        if d.weekday() in days:
            out.append(d)
        d += timedelta(days=1)
    return out


@dataclass(frozen=True)
class Slot:
    start: date
    end: date
    shift: str  # sang | chieu | toi
    schedule: str


def slots_overlap(a: Slot, b: Slot) -> bool:
    """Trùng lịch = cùng ca, có chung ít nhất một thứ trong tuần, và khoảng ngày giao nhau."""
    return (
        a.shift == b.shift
        and bool(weekdays(a.schedule) & weekdays(b.schedule))
        and a.start <= b.end
        and b.start <= a.end
    )


# ---------------------------------------------------------------- chuyên cần / nguy cơ bỏ học
ATTENDANCE_REQUIRED = 0.8  # 04 › Chuyên cần
PASS_SCORE = 50


def attendance_rate(statuses: list[str]) -> float:
    """Trễ = vắng nửa buổi (04 › Chuyên cần). Vắng có phép vẫn tính là vắng với tỉ lệ chuyên cần."""
    if not statuses:
        return 1.0
    present = sum(1.0 if s == "co_mat" else 0.5 if s == "di_tre" else 0.0 for s in statuses)
    return present / len(statuses)


def consecutive_absences(statuses_newest_first: list[str]) -> int:
    n = 0
    for s in statuses_newest_first:
        if s != "vang":
            break
        n += 1
    return n


def certificate_eligible(statuses: list[str], final_score: float | None) -> tuple[bool, str]:
    rate = attendance_rate(statuses)
    if rate < ATTENDANCE_REQUIRED:
        return False, f"Chuyên cần {rate:.0%} < {ATTENDANCE_REQUIRED:.0%}"
    if final_score is None:
        return False, "Chưa có điểm cuối khoá"
    if final_score < PASS_SCORE:
        return False, f"Điểm cuối khoá {final_score:g} < {PASS_SCORE}"
    return True, f"Chuyên cần {rate:.0%}, điểm cuối khoá {final_score:g}"


# ---------------------------------------------------------------- nhắc nợ theo bậc (agent công nợ)
# (bậc, số ngày so với hạn: âm = trước hạn). Thứ tự tăng dần.
DEBT_TIERS: list[tuple[str, int]] = [("truoc_han_3", -3), ("qua_han_1", 1), ("qua_han_7", 7), ("tam_dung", 14)]
DEBT_TIER_LABEL = {
    "truoc_han_3": "trước hạn 3 ngày",
    "qua_han_1": "quá hạn 1 ngày",
    "qua_han_7": "quá hạn 7 ngày",
    "tam_dung": "quá hạn 14 ngày",
}


def debt_tier(due: date, today: date) -> str | None:
    """Bậc cao nhất đã tới cho một đợt chưa đóng (None = chưa tới bậc nào)."""
    days = (today - due).days
    reached = [name for name, threshold in DEBT_TIERS if days >= threshold]
    return reached[-1] if reached else None


# ---------------------------------------------------------------- chấm điểm khách tiềm năng
SOURCE_SCORE = {"gioi_thieu": 30, "walk_in": 28, "website": 22, "zalo": 18, "facebook": 14, "tiktok": 10}
LEAD_STALE_DAYS = 3  # quá 3 ngày chưa liên hệ thì cảnh báo


def lead_score(source: str, has_course: bool, need: str, has_email: bool, age_days: int, status: str) -> int:
    """Điểm 0-100 bằng luật minh bạch (giải thích được cho tư vấn viên), không phải LLM."""
    s = SOURCE_SCORE.get(source, 10)
    s += 20 if has_course else 0
    s += min(len(need.strip()) // 8, 15)  # nhu cầu càng cụ thể càng tốt
    s += 5 if has_email else 0
    s += {"hen_hoc_thu": 25, "da_lien_he": 10}.get(status, 0)
    s -= min(age_days, 30)  # khách để lâu nguội dần
    return max(0, min(100, s + 15))
