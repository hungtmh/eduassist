"""Dữ liệu giả lập cho phần nền tảng, sinh THEO KỊCH BẢN có chủ đích (mục 12 của đề xuất), chạy sau seed gốc.

Kịch bản được cài sẵn để agent nền có việc thật và để bộ đánh giá biết trước đáp án:
- Đợt học phí trải đều quanh hôm nay: sắp tới hạn, quá hạn 1-13 ngày, quá hạn trên 14 ngày (-> tạm dừng).
- Học viên vắng 2-3 buổi liên tiếp gần nhất; vài học viên điểm giữa khoá dưới 50.
- Lớp sắp khai giảng thiếu sĩ số: một lớp có lớp cùng khoá để gộp, một lớp không (-> huỷ), một lớp còn >7 ngày (-> cảnh báo).
- Một cặp lớp bị xếp trùng giảng viên.
- Khách tiềm năng ở mọi trạng thái, có khách quá 3 ngày chưa liên hệ.

Cố định seed ngẫu nhiên -> cùng một ngày chạy ra cùng dữ liệu.
"""

import random
from datetime import date, datetime, time, timedelta

from psycopg import sql

from eduassist.seed.generate import COURSES, DEM, HO, HO_W, TEACHERS, TEN, slug
from eduassist.services import rules
from eduassist.services.proposals import ensure_default_policies

CAMPUSES = [("Cơ sở Quận 3", "12 Võ Văn Tần, Quận 3, TP.HCM"), ("Cơ sở Thủ Đức", "45 Võ Văn Ngân, TP. Thủ Đức")]
ROOMS = [("P101", 15), ("P102", 20), ("P201", 25), ("P202", 30), ("Lab A", 20)]
SPECIALTY = [
    "Tiếng Anh",
    "Tiếng Anh",
    "Lập trình",
    "Tiếng Anh",
    "Phân tích dữ liệu",
    "Phân tích dữ liệu",
    "Tiếng Anh",
    "Lập trình",
    "Tin học văn phòng",
    "Kỹ năng mềm",
]
NEEDS = [
    "Muốn học IELTS buổi tối để đi du học năm sau, hiện khoảng 5.0",
    "Con học lớp 9, cần ôn thi tiếng Anh vào lớp 10",
    "Cần chứng chỉ TOEIC để ra trường",
    "Đi làm văn phòng, muốn học Excel nâng cao, rảnh buổi tối",
    "Muốn chuyển ngành sang Data Analyst, chưa biết SQL",
    "Muốn học Python cơ bản",
    "Cần luyện giao tiếp tiếng Anh cho công việc",
    "Hỏi lớp Power BI cuối tuần",
    "",
    "Tìm lớp lập trình cho con 12 tuổi",
]


def _copy(conn, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    with (
        conn.cursor() as cur,
        cur.copy(
            sql.SQL("COPY {} ({}) FROM STDIN").format(
                sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, cols))
            )
        ) as cp,
    ):
        for r in rows:
            cp.write_row([r[c] for c in cols])
    if "id" in cols:
        conn.execute(
            sql.SQL("SELECT setval(pg_get_serial_sequence({}, 'id'), (SELECT max(id) FROM {}))").format(
                sql.Literal(table), sql.Identifier(table)
            )
        )


def seed_platform(conn, today: date, seed: int = 7) -> dict:
    rnd = random.Random(seed)
    stats: dict[str, int] = {}

    # ---------------------------------------------------------------- cơ sở, phòng, giảng viên
    rooms = []
    for cid, (name, addr) in enumerate(CAMPUSES, start=1):
        conn.execute("INSERT INTO co_so (id, ten, dia_chi) VALUES (%s, %s, %s)", (cid, name, addr))
        for rname, cap in ROOMS:
            rooms.append({"id": len(rooms) + 1, "co_so_id": cid, "ten": rname, "suc_chua": cap})
    _copy(conn, "phong_hoc", rooms)
    conn.execute("SELECT setval(pg_get_serial_sequence('co_so', 'id'), 2)")
    teachers = [
        {
            "id": i,
            "ho_ten": n,
            "email": f"{slug(n.split('. ')[-1].replace('Cô ', '').replace('Thầy ', ''))}@anhduong.example",
            "chuyen_mon": SPECIALTY[i - 1],
            "username": None,
        }
        for i, n in enumerate(TEACHERS, start=1)
    ]
    _copy(conn, "giang_vien", teachers)

    # ---------------------------------------------------------------- lớp: kịch bản thiếu sĩ số, rồi xếp GV/phòng
    classes = conn.execute(
        """SELECT lh.*, kh.so_buoi, kh.ma, kh.danh_muc, kh.hoc_phi,
                  (SELECT count(*) FROM don_hang d WHERE d.lop_hoc_id = lh.id AND d.trang_thai <> 'da_huy') AS n
           FROM lop_hoc lh JOIN khoa_hoc kh ON kh.id = lh.khoa_hoc_id ORDER BY lh.ngay_khai_giang, lh.id"""
    ).fetchall()
    by_id = {c["id"]: c for c in classes}
    upcoming = [c for c in classes if c["trang_thai"] == "sap_khai_giang"]
    _plant_underfilled(conn, upcoming, today, rnd, by_id)

    for c in classes:
        c["si_so_toi_thieu"] = min(8, max(4, c["si_so_toi_da"] // 3))
    busy: dict[tuple[str, int], list[rules.Slot]] = {}
    planted_conflict = None
    for c in classes:
        dates = rules.session_dates(c["ngay_khai_giang"], c["lich_hoc"], c["so_buoi"])
        slot = rules.Slot(dates[0], dates[-1], c["ca_hoc"], c["lich_hoc"])
        c["dates"] = dates
        prefer = [t for t in teachers if t["chuyen_mon"] == c["danh_muc"]] + [
            t for t in teachers if t["chuyen_mon"] != c["danh_muc"]
        ]
        c["giang_vien_id"] = next(
            (t["id"] for t in prefer if not any(rules.slots_overlap(slot, s) for s in busy.get(("gv", t["id"]), []))),
            prefer[0]["id"],
        )
        busy.setdefault(("gv", c["giang_vien_id"]), []).append(slot)
        c["phong_hoc_id"] = None
        if c["hinh_thuc"] == "offline":
            fits = [r for r in rooms if r["suc_chua"] >= c["si_so_toi_da"]]
            rnd.shuffle(fits)
            c["phong_hoc_id"] = next(
                (r["id"] for r in fits if not any(rules.slots_overlap(slot, s) for s in busy.get(("ph", r["id"]), []))),
                None,
            )
            if c["phong_hoc_id"] is None:
                c["hinh_thuc"] = "online"
            else:
                busy.setdefault(("ph", c["phong_hoc_id"]), []).append(slot)
    # Kịch bản trùng lịch: lớp sắp khai giảng thứ hai lấy đúng GV + ca + lịch của một lớp đang học
    long_running = [
        c for c in classes if c["trang_thai"] == "dang_hoc" and c["dates"][-1] >= today + timedelta(days=30)
    ]
    later = [c for c in classes if c["trang_thai"] == "sap_khai_giang" and (c["ngay_khai_giang"] - today).days > 15]
    if long_running and later:
        a, b = long_running[0], later[0]
        b["giang_vien_id"], b["ca_hoc"], b["lich_hoc"] = a["giang_vien_id"], a["ca_hoc"], a["lich_hoc"]
        b["ngay_khai_giang"] = today + timedelta(days=16)
        b["dates"] = rules.session_dates(b["ngay_khai_giang"], b["lich_hoc"], b["so_buoi"])
        if b["hinh_thuc"] == "offline" and b["phong_hoc_id"] == a["phong_hoc_id"]:
            b["hinh_thuc"], b["phong_hoc_id"] = "online", None
        planted_conflict = (a["ma_lop"], b["ma_lop"])
    tname = {t["id"]: t["ho_ten"] for t in teachers}
    with conn.cursor() as cur:
        cur.executemany(
            """UPDATE lop_hoc SET giang_vien_id = %s, giang_vien = %s, phong_hoc_id = %s, hinh_thuc = %s,
                      si_so_toi_thieu = %s, ngay_khai_giang = %s, ca_hoc = %s, lich_hoc = %s WHERE id = %s""",
            [
                (
                    c["giang_vien_id"],
                    tname[c["giang_vien_id"]],
                    c["phong_hoc_id"],
                    c["hinh_thuc"],
                    c["si_so_toi_thieu"],
                    c["ngay_khai_giang"],
                    c["ca_hoc"],
                    c["lich_hoc"],
                    c["id"],
                )
                for c in classes
            ],
        )

    # ---------------------------------------------------------------- buổi học
    sessions, sid = [], 0
    for c in classes:
        if c["trang_thai"] == "da_huy":
            continue
        for i, d in enumerate(c["dates"], start=1):
            sid += 1
            done = c["trang_thai"] != "sap_khai_giang" and d < today
            sessions.append(
                {
                    "id": sid,
                    "lop_hoc_id": c["id"],
                    "so_thu_tu": i,
                    "ngay": d,
                    "trang_thai": "da_hoc" if done else "du_kien",
                }
            )
    _copy(conn, "buoi_hoc", sessions)
    # Lớp "đang học" nhưng buổi đầu chưa tới (do ngày khai giảng gốc) -> vẫn hợp lệ; lớp đã kết thúc giữ nguyên
    stats["buoi_hoc"] = len(sessions)

    # ---------------------------------------------------------------- ghi danh: trạng thái học + đợt thanh toán
    orders = conn.execute(
        """SELECT d.*, lh.trang_thai AS lop_tt, lh.ngay_khai_giang,
                  coalesce((SELECT sum(so_tien) FROM thanh_toan t WHERE t.don_hang_id = d.id AND so_tien > 0), 0) AS paid
           FROM don_hang d JOIN lop_hoc lh ON lh.id = d.lop_hoc_id ORDER BY d.id"""
    ).fetchall()
    sess_by_class: dict[int, list[dict]] = {}
    for s in sessions:
        sess_by_class.setdefault(s["lop_hoc_id"], []).append(s)
    dots, updates = [], []
    for o in orders:
        st, lop = o["trang_thai"], o["lop_tt"]
        if st in ("da_huy", "da_hoan_tien") or lop == "da_huy":
            tth = "da_huy"
        elif lop == "da_ket_thuc":
            tth = "hoan_thanh"
        elif lop == "dang_hoc":
            tth = "dang_hoc"
        else:
            tth = "dang_hoc" if st in ("da_thanh_toan", "thanh_toan_mot_phan") else "cho_thanh_toan"
        installments = o["thanh_tien"] >= rules.INSTALLMENT_MIN_FEE and st == "thanh_toan_mot_phan"
        updates.append((tth, installments, o["id"]))
        cls_sessions = sess_by_class.get(o["lop_hoc_id"], [])
        s10 = next((s["ngay"] for s in cls_sessions if s["so_thu_tu"] == rules.INSTALLMENT_DUE_SESSION), None)
        if installments:
            first = o["thanh_tien"] // 2
            due2 = (s10 - timedelta(days=1)) if s10 else o["ngay_khai_giang"] + timedelta(days=21)
            plan = [(first, o["ngay_dat"] + timedelta(days=3), True), (o["thanh_tien"] - first, due2, False)]
        else:
            plan = [
                (
                    o["thanh_tien"],
                    min(o["ngay_khai_giang"], o["ngay_dat"] + timedelta(days=7))
                    if lop != "sap_khai_giang"
                    else o["ngay_khai_giang"] - timedelta(days=1),
                    o["paid"] >= o["thanh_tien"],
                )
            ]
        for i, (amount, due, paid) in enumerate(plan, start=1):
            if paid or st in ("da_thanh_toan", "da_hoan_tien"):
                status = "da_thanh_toan"
            elif tth in ("da_huy",):
                status = "da_huy"
            elif tth == "hoan_thanh":
                status = "qua_han"
            else:
                status = "qua_han" if due < today else "chua_thanh_toan"
            dots.append(
                {"don_hang_id": o["id"], "so_thu_tu": i, "so_tien": amount, "han_thanh_toan": due, "trang_thai": status}
            )
    with conn.cursor() as cur:
        cur.executemany("UPDATE don_hang SET trang_thai_hoc = %s, tra_gop = %s WHERE id = %s", updates)
    # Rải hạn của các đợt còn mở thuộc lớp đang học/sắp học quanh hôm nay -> agent công nợ có đủ các bậc
    offsets = [-16, -9, -8, -7, -4, -2, -1, 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 21, 25, 28, 30]
    active_ids = {u[2] for u in updates if u[0] in ("dang_hoc", "cho_thanh_toan")}
    open_dots = [
        d for d in dots if d["don_hang_id"] in active_ids and d["trang_thai"] in ("chua_thanh_toan", "qua_han")
    ]
    for i, d in enumerate(open_dots):
        d["han_thanh_toan"] = today + timedelta(days=offsets[i % len(offsets)])
        d["trang_thai"] = "qua_han" if d["han_thanh_toan"] < today else "chua_thanh_toan"
    _copy(conn, "dot_thanh_toan", dots)
    stats["dot_thanh_toan"] = len(dots)
    stats["dot_dang_mo"] = len(open_dots)

    # ---------------------------------------------------------------- điểm danh + điểm
    roster = conn.execute(
        "SELECT id, lop_hoc_id, trang_thai_hoc FROM don_hang WHERE trang_thai_hoc IN ('dang_hoc', 'hoan_thanh', 'tam_dung')"
    ).fetchall()
    by_class: dict[int, list[int]] = {}
    for r in roster:
        by_class.setdefault(r["lop_hoc_id"], []).append(r["id"])
    att, grades = [], []
    risky = set()
    active_cls = [c for c in classes if c["trang_thai"] == "dang_hoc" and by_class.get(c["id"])]
    for c in active_cls[:6]:  # kịch bản: mỗi lớp đang học đầu tiên có 1 học viên vắng liên tiếp
        risky.add(rnd.choice(by_class[c["id"]]))
    for c in classes:
        done = [s for s in sess_by_class.get(c["id"], []) if s["trang_thai"] == "da_hoc"]
        for dh in by_class.get(c["id"], []):
            weak = rnd.random() < 0.08
            for k, s in enumerate(done):
                last = len(done) - k
                if dh in risky and last <= 2 + (dh % 2):
                    status = "vang"
                else:
                    status = rnd.choices(
                        ["co_mat", "di_tre", "vang", "vang_co_phep"], [78, 6, 12, 4] if weak else [90, 5, 3, 2]
                    )[0]
                    if status == "vang" and last <= 2:
                        status = "co_mat"  # chỉ kịch bản mới vắng liên tiếp ở 2 buổi cuối
                att.append(
                    {
                        "buoi_hoc_id": s["id"],
                        "don_hang_id": dh,
                        "trang_thai": status,
                        "ghi_chu": None,
                        "updated_by": "seed",
                    }
                )
            if c["trang_thai"] == "da_ket_thuc":
                grades.append(
                    {
                        "don_hang_id": dh,
                        "loai": "cuoi_khoa",
                        "diem": rnd.randint(42 if weak else 55, 96),
                        "nhan_xet": None,
                        "updated_by": "seed",
                    }
                )
            if len(done) >= c["so_buoi"] // 2:
                grades.append(
                    {
                        "don_hang_id": dh,
                        "loai": "giua_khoa",
                        "diem": rnd.randint(30, 58) if weak else rnd.randint(55, 95),
                        "nhan_xet": None,
                        "updated_by": "seed",
                    }
                )
    _copy(conn, "diem_danh", att)
    _copy(conn, "diem_so", grades)
    stats["diem_danh"] = len(att)

    # ---------------------------------------------------------------- khách tiềm năng
    leads = []
    statuses = ["moi"] * 14 + ["da_lien_he"] * 16 + ["hen_hoc_thu"] * 8 + ["da_ghi_danh"] * 10 + ["khong_tiep_tuc"] * 8
    owners = ["tuvan", "nhanvien"]
    for i, st in enumerate(statuses, start=1):
        name = f"{rnd.choices(HO, HO_W)[0]} {rnd.choice(DEM)} {rnd.choice(TEN)}"
        age = rnd.randint(0, 2) if st == "moi" and i % 3 else rnd.randint(4, 40)
        created = datetime.combine(today - timedelta(days=age), time(rnd.randint(8, 20), rnd.randint(0, 59)))
        need = rnd.choice(NEEDS)
        course = rnd.choice(COURSES)
        kh_id = COURSES.index(course) + 1 if rnd.random() < 0.6 else None
        contact = None if st == "moi" else created + timedelta(days=rnd.randint(0, min(age, 10)), hours=2)
        leads.append(
            {
                "id": i,
                "ho_ten": name,
                "so_dien_thoai": "09" + f"{rnd.randint(0, 99_999_999):08d}",
                "email": f"{slug(name)}.lead{i}@example.com" if rnd.random() < 0.8 else None,
                "nguon": rnd.choice(["facebook", "zalo", "gioi_thieu", "website", "tiktok", "walk_in"]),
                "nhu_cau": need,
                "khoa_quan_tam_id": kh_id,
                "trang_thai": st,
                "phu_trach": owners[i % 2],
                "diem": None,
                "lien_he_cuoi": contact,
                "ly_do_dung": "Chê học phí cao" if st == "khong_tiep_tuc" else None,
                "hoc_vien_id": None,
                "created_at": created,
                "updated_at": contact or created,
            }
        )
    _copy(conn, "khach_tiem_nang", leads)
    stats["khach_tiem_nang"] = len(leads)

    ensure_default_policies(conn)
    return {**stats, "trung_lich": planted_conflict}


def _plant_underfilled(conn, upcoming: list[dict], today: date, rnd: random.Random, by_id: dict) -> None:
    """Ba lớp sắp khai giảng thiếu sĩ số với kết cục khác nhau (gộp / huỷ / cảnh báo)."""
    by_course: dict[int, list[dict]] = {}
    for c in upcoming:
        by_course.setdefault(c["khoa_hoc_id"], []).append(c)
    pair = next((v for v in by_course.values() if len(v) >= 2), None)
    singles = [v[0] for v in by_course.values() if len(v) == 1]
    plans = []
    if pair:
        small, big = sorted(pair[:2], key=lambda c: c["n"])
        plans.append((small, 5, 3))  # 5 ngày nữa khai giảng, giữ 3 học viên -> gộp vào lớp cùng khoá
        big["ngay_khai_giang"] = max(big["ngay_khai_giang"], today + timedelta(days=9))
        conn.execute("UPDATE lop_hoc SET si_so_toi_da = 30 WHERE id = %s", (big["id"],))
        big["si_so_toi_da"] = 30
    if singles:
        plans.append((singles[0], 6, 2))  # không có lớp cùng khoá -> đề xuất huỷ
    if len(singles) > 1:
        plans.append((singles[1], 11, 2))  # còn 11 ngày -> chỉ cảnh báo (L0)
    for cls, days, keep in plans:
        cls["ngay_khai_giang"] = today + timedelta(days=days)
        orders = conn.execute(
            "SELECT id FROM don_hang WHERE lop_hoc_id = %s AND trang_thai <> 'da_huy' ORDER BY id", (cls["id"],)
        ).fetchall()
        drop = [o["id"] for o in orders[keep:]]
        if drop:  # bớt học viên: huỷ ghi danh chưa phát sinh tiền (xoá luôn tiền đã thu để số liệu khớp)
            conn.execute("DELETE FROM thanh_toan WHERE don_hang_id = ANY(%s)", (drop,))
            conn.execute("UPDATE don_hang SET trang_thai = 'da_huy' WHERE id = ANY(%s)", (drop,))
        cls["n"] = min(keep, len(orders))
