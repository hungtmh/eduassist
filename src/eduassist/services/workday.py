"""Trang "Hôm nay" theo vai trò và thời khoá biểu dạng lịch.

Mỗi vai trò mở máy là thấy đúng việc của mình hôm nay:
- Giảng viên: buổi dạy hôm nay và 7 ngày tới, buổi nào chưa điểm danh.
- Tư vấn viên: lịch hẹn hôm nay, khách mới, khách quá 3 ngày chưa liên hệ.
- Kế toán: tiền đến hạn hôm nay, nợ quá hạn, hoàn phí chờ duyệt, tiền đã thu hôm nay.
- Giáo vụ: buổi học hôm nay toàn trung tâm, yêu cầu học viên mới, lớp sắp khai giảng còn thiếu sĩ số.
Ai cũng thấy việc được giao đến hạn và số đề xuất của agent đang chờ mình duyệt.
"""

from datetime import date, timedelta

from eduassist.services import proposals, rules
from eduassist.services.core import Actor, Forbidden, RuleViolation, has_perm, require, today

ACTIVE = list(rules.ACTIVE_ENROLLMENT)
MAX_SCHEDULE_DAYS = 42

SESSION_SQL = """
SELECT b.id, b.ngay, b.so_thu_tu, b.trang_thai, lh.id AS lop_hoc_id, lh.ma_lop, lh.ca_hoc, lh.hinh_thuc,
       kh.ten AS khoa_hoc, kh.danh_muc, kh.so_buoi, ph.ten AS phong, cs.ten AS co_so, gv.ho_ten AS giang_vien,
       lh.giang_vien_id, lh.phong_hoc_id,
       (SELECT count(*) FROM don_hang d WHERE d.lop_hoc_id = lh.id AND d.trang_thai_hoc = ANY(%(active)s))::int AS si_so,
       EXISTS (SELECT 1 FROM diem_danh dd WHERE dd.buoi_hoc_id = b.id) AS da_diem_danh
FROM buoi_hoc b
JOIN lop_hoc lh ON lh.id = b.lop_hoc_id
JOIN khoa_hoc kh ON kh.id = lh.khoa_hoc_id
LEFT JOIN phong_hoc ph ON ph.id = lh.phong_hoc_id
LEFT JOIN co_so cs ON cs.id = ph.co_so_id
LEFT JOIN giang_vien gv ON gv.id = lh.giang_vien_id
WHERE lh.trang_thai IN ('sap_khai_giang', 'dang_hoc', 'da_ket_thuc') AND b.trang_thai <> 'nghi'
"""
SHIFT_ORDER = "CASE lh.ca_hoc WHEN 'sang' THEN 0 WHEN 'chieu' THEN 1 ELSE 2 END"


def _sessions(conn, start: date, end: date, extra: str = "", params: dict | None = None, limit: int = 500):
    return conn.execute(
        SESSION_SQL
        + " AND b.ngay BETWEEN %(start)s AND %(end)s "
        + extra
        + f" ORDER BY b.ngay, {SHIFT_ORDER}, lh.ma_lop LIMIT %(limit)s",
        {"active": ACTIVE, "start": start, "end": end, "limit": limit, **(params or {})},
    ).fetchall()


def my_day(conn, actor: Actor) -> dict:
    t = today()
    out: dict = {"ngay": t, "vai_tro": actor.role, "phan": []}
    if actor.role == "student":
        raise Forbidden("Học viên xem lịch học ở cổng học viên.")

    tasks = conn.execute(
        """SELECT v.id, v.tieu_de, v.han, v.loai_doi_tuong, v.doi_tuong_id, k.ho_ten AS ten_khach
           FROM viec_can_lam v
           LEFT JOIN khach_tiem_nang k ON v.loai_doi_tuong = 'khach_tiem_nang' AND k.id = v.doi_tuong_id
           WHERE v.trang_thai = 'mo' AND v.nguoi_phu_trach = %s AND v.han <= %s ORDER BY v.han, v.id""",
        (actor.id, t),
    ).fetchall()
    out["viec_den_han"] = tasks[:8]
    out["so_viec_den_han"] = len(tasks)
    out["de_xuat_cho_duyet"] = (
        sum(1 for r in proposals.list_proposals(conn, actor, "cho_duyet", limit=500) if r["co_the_duyet"])
        if has_perm(actor, "chat.data")
        else 0
    )

    if actor.role == "teacher" or actor.giang_vien_id:
        if actor.giang_vien_id:
            week = _sessions(
                conn, t, t + timedelta(days=6), "AND lh.giang_vien_id = %(gv)s", {"gv": actor.giang_vien_id}
            )
            missing = _sessions(
                conn,
                t - timedelta(days=14),
                t - timedelta(days=1),
                "AND lh.giang_vien_id = %(gv)s AND NOT EXISTS (SELECT 1 FROM diem_danh dd WHERE dd.buoi_hoc_id = b.id)",
                {"gv": actor.giang_vien_id},
            )
        else:
            week, missing = [], []
        out["giang_day"] = {
            "hom_nay": [s for s in week if s["ngay"] == t],
            "tuan_toi": [s for s in week if s["ngay"] > t],
            "chua_diem_danh": missing,
        }

    if has_perm(actor, "lead.write"):
        mine = "phu_trach = %(me)s" if actor.role == "consultant" else "true"
        out["tuyen_sinh"] = {
            **conn.execute(
                f"""SELECT count(*) FILTER (WHERE created_at >= %(t)s::date - 1)::int AS khach_moi_24h,
                           count(*) FILTER (WHERE trang_thai = 'moi' AND lien_he_cuoi IS NULL
                                            AND %(t)s - created_at::date > 3)::int AS qua_han_lien_he
                    FROM khach_tiem_nang WHERE {mine}""",
                {"me": actor.id, "t": t},
            ).fetchone(),
            "lich_hen": conn.execute(
                f"""SELECT lh.id, lh.loai, lh.thoi_gian, k.id AS khach_id, k.ho_ten, k.so_dien_thoai
                    FROM lich_hen lh JOIN khach_tiem_nang k ON k.id = lh.khach_id
                    WHERE lh.thoi_gian::date = %(t)s AND lh.ket_qua IS NULL AND {mine.replace("phu_trach", "k.phu_trach")}
                    ORDER BY lh.thoi_gian""",
                {"me": actor.id, "t": t},
            ).fetchall(),
        }

    if has_perm(actor, "payment.record"):
        out["tai_chinh"] = conn.execute(
            """SELECT coalesce(sum(c.con_lai) FILTER (WHERE x.han_thanh_toan = %(t)s), 0)::bigint AS den_han_hom_nay,
                      count(*) FILTER (WHERE x.han_thanh_toan = %(t)s AND c.con_lai > 0)::int AS so_dot_hom_nay,
                      coalesce(sum(c.con_lai) FILTER (WHERE x.han_thanh_toan < %(t)s), 0)::bigint AS qua_han,
                      count(DISTINCT d.hoc_vien_id) FILTER (WHERE x.han_thanh_toan < %(t)s AND c.con_lai > 0)::int
                          AS hoc_vien_qua_han,
                      (SELECT coalesce(sum(so_tien), 0) FROM thanh_toan WHERE ngay_thanh_toan = %(t)s)::bigint
                          AS da_thu_hom_nay,
                      (SELECT count(*) FROM hoan_phi WHERE trang_thai = 'cho_duyet')::int AS hoan_phi_cho_duyet
               FROM dot_con_lai c JOIN dot_thanh_toan x ON x.id = c.id JOIN don_hang d ON d.id = c.don_hang_id
               WHERE c.con_lai > 0 AND d.trang_thai_hoc <> 'da_huy'""",
            {"t": t},
        ).fetchone()

    if has_perm(actor, "class.write"):
        today_sessions = _sessions(conn, t, t)
        out["giao_vu"] = {
            "buoi_hom_nay": today_sessions,
            "yeu_cau_moi": conn.execute("SELECT count(*) AS n FROM yeu_cau WHERE trang_thai = 'moi'").fetchone()["n"],
            "lop_thieu_si_so": conn.execute(
                """SELECT lh.id, lh.ma_lop, kh.ten AS khoa_hoc, lh.ngay_khai_giang, lh.si_so_toi_thieu,
                          (SELECT count(*) FROM don_hang d WHERE d.lop_hoc_id = lh.id
                             AND d.trang_thai_hoc = ANY(%(active)s))::int AS si_so
                   FROM lop_hoc lh JOIN khoa_hoc kh ON kh.id = lh.khoa_hoc_id
                   WHERE lh.trang_thai = 'sap_khai_giang' AND lh.ngay_khai_giang BETWEEN %(t)s AND %(t)s + 14
                     AND (SELECT count(*) FROM don_hang d WHERE d.lop_hoc_id = lh.id
                            AND d.trang_thai_hoc = ANY(%(active)s)) < lh.si_so_toi_thieu
                   ORDER BY lh.ngay_khai_giang""",
                {"t": t, "active": ACTIVE},
            ).fetchall(),
        }
    return out


def schedule(
    conn,
    actor: Actor,
    start: date,
    end: date,
    giang_vien_id: int | None = None,
    phong_hoc_id: int | None = None,
    lop_hoc_id: int | None = None,
) -> list[dict]:
    """Các buổi học trong khoảng ngày. Giảng viên chỉ xem được lịch của chính mình."""
    if end < start:
        raise RuleViolation("Ngày kết thúc phải sau ngày bắt đầu.")
    if (end - start).days > MAX_SCHEDULE_DAYS:
        raise RuleViolation(f"Mỗi lần xem tối đa {MAX_SCHEDULE_DAYS} ngày.")
    if not has_perm(actor, "class.read"):
        require(actor, "class.read_own")
        if not actor.giang_vien_id:
            raise Forbidden("Tài khoản chưa gắn hồ sơ giảng viên.")
        giang_vien_id = actor.giang_vien_id
    where, params = [], {}
    if giang_vien_id:
        where.append("lh.giang_vien_id = %(gv)s")
        params["gv"] = giang_vien_id
    if phong_hoc_id:
        where.append("lh.phong_hoc_id = %(ph)s")
        params["ph"] = phong_hoc_id
    if lop_hoc_id:
        where.append("lh.id = %(lop)s")
        params["lop"] = lop_hoc_id
    return _sessions(conn, start, end, "".join(f" AND {w}" for w in where), params, limit=2000)
