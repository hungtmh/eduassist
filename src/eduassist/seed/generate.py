"""Sinh dữ liệu GIẢ LẬP cho trung tâm đào tạo (không dùng dữ liệu thật của ai).

Cố định seed ngẫu nhiên -> cùng một ngày chạy ra cùng dữ liệu. Ngày tháng được neo theo
`today` để các câu hỏi kiểu "tháng này", "quý trước" luôn có dữ liệu khi demo.
"""

import random
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta

COURSES = [
    # (mã, tên, danh mục, trình độ, học phí, số buổi, mô tả)
    (
        "ENG-IF",
        "IELTS Foundation (mục tiêu 5.0)",
        "Tiếng Anh",
        "Cơ bản",
        6_500_000,
        36,
        "Xây nền ngữ pháp, từ vựng và làm quen 4 kỹ năng IELTS cho người mất gốc.",
    ),
    (
        "ENG-II",
        "IELTS Intensive (cam kết 6.5)",
        "Tiếng Anh",
        "Trung cấp",
        8_900_000,
        40,
        "Luyện đề chuyên sâu 4 kỹ năng, có cam kết đầu ra 6.5. Yêu cầu đầu vào 5.0.",
    ),
    (
        "ENG-IM",
        "IELTS Master (mục tiêu 7.5+)",
        "Tiếng Anh",
        "Nâng cao",
        11_500_000,
        40,
        "Chiến lược band cao cho Writing & Speaking, chữa bài 1-1. Yêu cầu đầu vào 6.5.",
    ),
    (
        "ENG-T4",
        "TOEIC 450+",
        "Tiếng Anh",
        "Cơ bản",
        3_900_000,
        30,
        "Ôn TOEIC Listening & Reading cho sinh viên cần chuẩn đầu ra.",
    ),
    ("ENG-T7", "TOEIC 750+", "Tiếng Anh", "Trung cấp", 5_200_000, 30, "Luyện đề TOEIC nâng cao, mẹo xử lý Part 5-7."),
    (
        "ENG-GT",
        "Tiếng Anh giao tiếp phản xạ",
        "Tiếng Anh",
        "Cơ bản",
        4_500_000,
        24,
        "Lớp tối đa 12 người, 70% thời lượng luyện nói theo tình huống.",
    ),
    (
        "ENG-V10",
        "Tiếng Anh luyện thi vào lớp 10",
        "Tiếng Anh",
        "Trung cấp",
        4_800_000,
        32,
        "Dành cho học sinh lớp 8-9, bám sát cấu trúc đề thi tuyển sinh lớp 10.",
    ),
    (
        "ENG-BIZ",
        "Tiếng Anh thương mại",
        "Tiếng Anh",
        "Nâng cao",
        6_000_000,
        24,
        "Email, họp, thuyết trình và đàm phán bằng tiếng Anh cho người đi làm.",
    ),
    (
        "OFF-EX",
        "Excel ứng dụng (chuẩn MOS)",
        "Tin học văn phòng",
        "Cơ bản",
        1_800_000,
        12,
        "Hàm, bảng tính, biểu đồ, Pivot Table; luyện thi chứng chỉ MOS Excel.",
    ),
    (
        "OFF-EXA",
        "Excel nâng cao cho kế toán",
        "Tin học văn phòng",
        "Nâng cao",
        2_500_000,
        15,
        "Power Query, hàm mảng, báo cáo động và tự động hoá cho kế toán.",
    ),
    (
        "OFF-WP",
        "Word & PowerPoint chuyên nghiệp",
        "Tin học văn phòng",
        "Cơ bản",
        1_500_000,
        10,
        "Soạn thảo văn bản chuẩn và thiết kế slide thuyết trình.",
    ),
    (
        "DEV-PY",
        "Python cơ bản",
        "Lập trình",
        "Cơ bản",
        3_500_000,
        20,
        "Nhập môn lập trình với Python, phù hợp người chưa biết code.",
    ),
    (
        "DEV-FE",
        "Lập trình web Front-end",
        "Lập trình",
        "Trung cấp",
        7_900_000,
        36,
        "HTML, CSS, JavaScript và React; làm 2 dự án web hoàn chỉnh.",
    ),
    (
        "DEV-JV",
        "Java Spring Boot",
        "Lập trình",
        "Nâng cao",
        9_500_000,
        40,
        "Xây dựng REST API, bảo mật, database và triển khai với Spring Boot.",
    ),
    (
        "DEV-KID",
        "Lập trình cho thiếu niên (Scratch & Python)",
        "Lập trình",
        "Cơ bản",
        3_200_000,
        20,
        "Dành cho học sinh 10-15 tuổi, học qua làm game và dự án nhỏ.",
    ),
    (
        "DA-SQL",
        "SQL cho phân tích dữ liệu",
        "Phân tích dữ liệu",
        "Cơ bản",
        3_800_000,
        16,
        "Truy vấn, JOIN, GROUP BY, window function trên dữ liệu kinh doanh thực tế.",
    ),
    (
        "DA-PBI",
        "Power BI",
        "Phân tích dữ liệu",
        "Trung cấp",
        4_200_000,
        16,
        "Mô hình dữ liệu, DAX và xây dựng dashboard quản trị.",
    ),
    (
        "DA-PY",
        "Python cho phân tích dữ liệu",
        "Phân tích dữ liệu",
        "Trung cấp",
        5_500_000,
        24,
        "Pandas, trực quan hoá dữ liệu và phân tích khám phá. Yêu cầu biết Python cơ bản.",
    ),
    (
        "DA-FULL",
        "Data Analyst toàn diện",
        "Phân tích dữ liệu",
        "Nâng cao",
        12_900_000,
        48,
        "Lộ trình SQL + Excel + Power BI + Python, có dự án cuối khoá và hỗ trợ việc làm.",
    ),
    (
        "SK-TT",
        "Thuyết trình tự tin",
        "Kỹ năng mềm",
        "Cơ bản",
        2_200_000,
        8,
        "Cấu trúc bài nói, kiểm soát giọng và ngôn ngữ cơ thể, luyện quay video.",
    ),
    (
        "SK-PV",
        "Kỹ năng phỏng vấn xin việc",
        "Kỹ năng mềm",
        "Cơ bản",
        1_600_000,
        6,
        "Viết CV, trả lời câu hỏi hành vi và phỏng vấn thử với chuyên gia tuyển dụng.",
    ),
    (
        "SK-TG",
        "Quản lý thời gian hiệu quả",
        "Kỹ năng mềm",
        "Cơ bản",
        1_400_000,
        6,
        "Lập kế hoạch, ưu tiên công việc và chống trì hoãn.",
    ),
]
# Độ "hot" tương đối của mỗi khoá -> doanh số không đều như thực tế
POPULARITY = {
    "ENG-II": 10,
    "ENG-IF": 8,
    "ENG-GT": 7,
    "DA-FULL": 6,
    "ENG-T4": 6,
    "OFF-EX": 6,
    "DA-SQL": 5,
    "DEV-PY": 5,
    "ENG-V10": 5,
    "DA-PBI": 4,
    "DEV-FE": 4,
    "ENG-T7": 4,
    "DA-PY": 3,
    "ENG-IM": 3,
    "DEV-KID": 3,
    "OFF-EXA": 3,
    "SK-PV": 3,
    "SK-TT": 2,
    "ENG-BIZ": 2,
    "OFF-WP": 2,
    "DEV-JV": 2,
    "SK-TG": 1,
}

HO = [
    "Nguyễn",
    "Trần",
    "Lê",
    "Phạm",
    "Hoàng",
    "Huỳnh",
    "Phan",
    "Vũ",
    "Võ",
    "Đặng",
    "Bùi",
    "Đỗ",
    "Hồ",
    "Ngô",
    "Dương",
    "Lý",
]
HO_W = [32, 11, 9, 7, 5, 5, 4, 4, 4, 3, 3, 3, 3, 2, 2, 2]
DEM = [
    "Văn",
    "Thị",
    "Minh",
    "Thanh",
    "Ngọc",
    "Quốc",
    "Hoàng",
    "Thu",
    "Gia",
    "Bảo",
    "Anh",
    "Đức",
    "Hải",
    "Khánh",
    "Phương",
]
TEN = [
    "An",
    "Bình",
    "Châu",
    "Dũng",
    "Giang",
    "Hà",
    "Hải",
    "Hạnh",
    "Hiếu",
    "Hoa",
    "Huy",
    "Hương",
    "Khang",
    "Khoa",
    "Lan",
    "Linh",
    "Long",
    "Mai",
    "Minh",
    "Nam",
    "Ngân",
    "Nhi",
    "Phong",
    "Phúc",
    "Quân",
    "Quỳnh",
    "Sơn",
    "Tâm",
    "Thảo",
    "Trang",
    "Trung",
    "Tú",
    "Tuấn",
    "Uyên",
    "Vy",
    "Yến",
    "Khôi",
    "Đạt",
    "Thư",
    "Nhung",
]
CITIES = [
    ("TP.HCM", 55),
    ("Hà Nội", 14),
    ("Bình Dương", 8),
    ("Đồng Nai", 7),
    ("Đà Nẵng", 5),
    ("Cần Thơ", 5),
    ("Long An", 6),
]
SOURCES = [("facebook", 35), ("zalo", 20), ("gioi_thieu", 20), ("website", 15), ("tiktok", 10)]
SCHEDULES = {
    "sang": ["T2-T4-T6", "T3-T5-T7"],
    "chieu": ["T2-T4-T6", "T3-T5-T7"],
    "toi": ["T2-T4-T6", "T3-T5-T7", "T7-CN"],
}
TEACHERS = [
    "ThS. Trần Hoàng Nam",
    "Cô Lê Thu Hà",
    "Thầy Phạm Quốc Bảo",
    "Cô Nguyễn Ngọc Mai",
    "Thầy Võ Đức Huy",
    "ThS. Đặng Minh Khoa",
    "Cô Bùi Phương Linh",
    "Thầy Hồ Gia Long",
    "Cô Đỗ Thanh Trang",
    "ThS. Ngô Hải Sơn",
]


def slug(text: str) -> str:
    text = text.lower().replace("đ", "d")
    text = "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")
    return "".join(ch for ch in text if ch.isalnum() or ch == " ").replace(" ", ".")


@dataclass
class Dataset:
    khoa_hoc: list[dict] = field(default_factory=list)
    lop_hoc: list[dict] = field(default_factory=list)
    hoc_vien: list[dict] = field(default_factory=list)
    don_hang: list[dict] = field(default_factory=list)
    thanh_toan: list[dict] = field(default_factory=list)


def generate(today: date, n_students: int = 420, seed: int = 42) -> Dataset:
    rnd = random.Random(seed)
    ds = Dataset()
    start = today - timedelta(days=300)

    for i, (ma, ten, dm, td, hp, sb, mt) in enumerate(COURSES, start=1):
        ds.khoa_hoc.append(
            dict(id=i, ma=ma, slug=ma.lower(), ten=ten, danh_muc=dm, trinh_do=td, hoc_phi=hp, so_buoi=sb, mo_ta=mt)
        )

    # Lớp học: khoá càng hot càng nhiều đợt khai giảng, trải từ ~10 tháng trước tới 2 tháng tới
    lop_id = 0
    for kh in ds.khoa_hoc:
        n_classes = 2 + POPULARITY[kh["ma"]] // 2
        for _ in range(n_classes):
            lop_id += 1
            opening = start + timedelta(days=rnd.randint(0, 360))
            weeks = max(2, kh["so_buoi"] // 3)
            end = opening + timedelta(weeks=weeks)
            status = "sap_khai_giang" if opening > today else ("dang_hoc" if end >= today else "da_ket_thuc")
            ca = rnd.choices(["sang", "chieu", "toi"], [2, 2, 6])[0]
            ds.lop_hoc.append(
                dict(
                    id=lop_id,
                    ma_lop=f"{kh['ma']}-{opening:%y%m}-{lop_id:03d}",
                    khoa_hoc_id=kh["id"],
                    ngay_khai_giang=opening,
                    ca_hoc=ca,
                    lich_hoc=rnd.choice(SCHEDULES[ca]),
                    hinh_thuc=rnd.choices(["offline", "online"], [7, 3])[0],
                    si_so_toi_da=12 if kh["ma"] == "ENG-GT" else rnd.choice([15, 20, 25]),
                    giang_vien=rnd.choice(TEACHERS),
                    trang_thai=status,
                )
            )

    used_emails: set[str] = set()
    for i in range(1, n_students + 1):
        name = f"{rnd.choices(HO, HO_W)[0]} {rnd.choice(DEM)} {rnd.choice(TEN)}"
        email = f"{slug(name)}{i}@example.com"
        used_emails.add(email)
        ds.hoc_vien.append(
            dict(
                id=i,
                ho_ten=name,
                email=email,
                so_dien_thoai="0"
                + rnd.choice(["90", "93", "97", "98", "86", "88", "70", "79"])
                + f"{rnd.randint(0, 9_999_999):07d}",
                nam_sinh=rnd.choices(
                    [rnd.randint(2009, 2012), rnd.randint(1998, 2006), rnd.randint(1980, 1997)], [2, 5, 3]
                )[0],
                thanh_pho=rnd.choices(*zip(*CITIES, strict=True))[0],
                nguon=rnd.choices(*zip(*SOURCES, strict=True))[0],
                ngay_dang_ky=start - timedelta(days=30) + timedelta(days=rnd.randint(0, 380)),
            )
        )

    # Đơn hàng: mỗi học viên 1-3 lớp, chọn theo độ hot, khai giảng sau ngày đăng ký
    weights = {kh["id"]: POPULARITY[kh["ma"]] for kh in ds.khoa_hoc}
    seats = {l["id"]: l["si_so_toi_da"] for l in ds.lop_hoc}  # không cho lớp vượt sĩ số
    dh_id = tt_id = 0
    for hv in ds.hoc_vien:
        candidates = [
            l
            for l in ds.lop_hoc
            if l["ngay_khai_giang"] >= hv["ngay_dang_ky"] - timedelta(days=7) and seats[l["id"]] > 0
        ]
        if not candidates:
            continue
        k = rnd.choices([1, 2, 3], [6, 3, 1])[0]
        chosen = {id(l): l for l in rnd.choices(candidates, [weights[l["khoa_hoc_id"]] for l in candidates], k=k)}
        for lop in chosen.values():
            if seats[lop["id"]] <= 0:
                continue
            seats[lop["id"]] -= 1
            dh_id += 1
            kh = ds.khoa_hoc[lop["khoa_hoc_id"] - 1]
            order_date = min(
                today, max(hv["ngay_dang_ky"], lop["ngay_khai_giang"] - timedelta(days=rnd.randint(1, 30)))
            )
            discount_pct = rnd.choices([0, 5, 10, 15], [5, 2, 2, 1])[0]
            goc = kh["hoc_phi"]
            giam = goc * discount_pct // 100
            thanh_tien = goc - giam
            if lop["trang_thai"] == "da_ket_thuc":
                status = rnd.choices(["da_thanh_toan", "thanh_toan_mot_phan", "da_huy", "da_hoan_tien"], [85, 5, 6, 4])[
                    0
                ]
            elif lop["trang_thai"] == "dang_hoc":
                status = rnd.choices(
                    ["da_thanh_toan", "thanh_toan_mot_phan", "chua_thanh_toan", "da_huy"], [65, 20, 10, 5]
                )[0]
            else:
                status = rnd.choices(
                    ["da_thanh_toan", "thanh_toan_mot_phan", "chua_thanh_toan", "da_huy"], [40, 25, 30, 5]
                )[0]
            ds.don_hang.append(
                dict(
                    id=dh_id,
                    hoc_vien_id=hv["id"],
                    lop_hoc_id=lop["id"],
                    ngay_dat=order_date,
                    hoc_phi_goc=goc,
                    giam_gia=giam,
                    thanh_tien=thanh_tien,
                    trang_thai=status,
                )
            )

            payments: list[tuple[int, date]] = []
            if status == "da_thanh_toan":
                payments = [(thanh_tien, order_date)]
            elif status == "thanh_toan_mot_phan":
                payments = [(thanh_tien // 2, order_date)]
            elif status == "da_hoan_tien":
                refund_day = lop["ngay_khai_giang"] + timedelta(days=rnd.randint(1, 6))
                payments = [(thanh_tien, order_date), (-thanh_tien * 7 // 10, refund_day)]
            for amount, when in payments:
                tt_id += 1
                ds.thanh_toan.append(
                    dict(
                        id=tt_id,
                        don_hang_id=dh_id,
                        ngay_thanh_toan=min(when, today),
                        so_tien=amount,
                        phuong_thuc=rnd.choices(["chuyen_khoan", "tien_mat", "the"], [7, 2, 1])[0],
                    )
                )
    return ds


DEMO_USERS = [
    # username, password, role, tên hiển thị, hoc_vien_id
    ("hocvien", "demo123", "student", "Học viên demo", 1),
    ("tuvan", "demo123", "consultant", "Tư vấn viên Lan", None),
    ("nhanvien", "demo123", "consultant", "Tư vấn viên Minh", None),
    ("giaovu", "demo123", "academic", "Giáo vụ Hà", None),
    ("ketoan", "demo123", "accountant", "Kế toán Phương", None),
    ("giangvien", "demo123", "teacher", "Giảng viên demo", None),
    ("quanly", "demo123", "manager", "Quản lý demo", None),
]
