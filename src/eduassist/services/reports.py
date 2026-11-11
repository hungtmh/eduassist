"""Phân hệ 7 - Báo cáo. Số liệu tính từ MỘT nguồn (các truy vấn dưới đây), dùng chung cho dashboard và agent báo cáo.

Doanh thu = tổng thanh_toan.so_tien (hoàn phí là số âm), giống quy tắc của agent phân tích.
"""

from datetime import date, timedelta

from eduassist.services.core import Actor, require, today


def _revenue(conn, start: date, end: date) -> int:
    return conn.execute(
        "SELECT coalesce(sum(so_tien), 0)::bigint AS v FROM thanh_toan WHERE ngay_thanh_toan >= %s AND ngay_thanh_toan < %s",
        (start, end),
    ).fetchone()["v"]


def dashboard(conn, actor: Actor) -> dict:
    require(actor, "report.read")
    t = today()
    month_start = t.replace(day=1)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
    same_day_prev = prev_month_start + (t - month_start)
    debt = conn.execute(
        """SELECT coalesce(sum(c.con_lai), 0)::bigint AS qua_han, count(DISTINCT d.hoc_vien_id)::int AS hv_qua_han
           FROM dot_thanh_toan x JOIN dot_con_lai c ON c.id = x.id JOIN don_hang d ON d.id = x.don_hang_id
           WHERE x.trang_thai = 'qua_han' AND d.trang_thai_hoc <> 'da_huy'"""
    ).fetchone()
    debt["tong_con_no"] = conn.execute(
        """SELECT coalesce(sum(d.thanh_tien - coalesce((SELECT sum(so_tien) FROM thanh_toan t
                                                        WHERE t.don_hang_id = d.id), 0)), 0)::bigint AS v
           FROM don_hang d WHERE d.trang_thai IN ('chua_thanh_toan', 'thanh_toan_mot_phan')
             AND d.trang_thai_hoc <> 'da_huy'"""
    ).fetchone()["v"]
    revenue_by_month = conn.execute(
        """SELECT to_char(date_trunc('month', ngay_thanh_toan), 'YYYY-MM') AS thang, sum(so_tien)::bigint AS doanh_thu
           FROM thanh_toan WHERE ngay_thanh_toan >= %s GROUP BY 1 ORDER BY 1""",
        ((month_start - timedelta(days=150)).replace(day=1),),
    ).fetchall()
    leads = conn.execute(
        """SELECT count(*)::int AS moi_30_ngay,
                  count(*) FILTER (WHERE trang_thai = 'da_ghi_danh')::int AS ghi_danh,
                  count(*) FILTER (WHERE trang_thai = 'moi' AND lien_he_cuoi IS NULL
                                   AND created_at::date <= %s - 3)::int AS cham_lien_he
           FROM khach_tiem_nang WHERE created_at::date >= %s - 30""",
        (t, t),
    ).fetchone()
    classes = conn.execute(
        """SELECT lh.id, lh.ma_lop, kh.ten AS khoa_hoc, lh.ngay_khai_giang, lh.si_so_toi_da, lh.si_so_toi_thieu,
                  (SELECT count(*) FROM don_hang d WHERE d.lop_hoc_id = lh.id
                       AND d.trang_thai_hoc IN ('cho_thanh_toan', 'dang_hoc', 'tam_dung'))::int AS si_so
           FROM lop_hoc lh JOIN khoa_hoc kh ON kh.id = lh.khoa_hoc_id
           WHERE lh.trang_thai = 'sap_khai_giang' AND lh.ngay_khai_giang <= %s + 30 ORDER BY lh.ngay_khai_giang""",
        (t,),
    ).fetchall()
    attendance = conn.execute(
        """SELECT count(*) FILTER (WHERE dd.trang_thai = 'co_mat') + 0.5 * count(*) FILTER (WHERE dd.trang_thai = 'di_tre')
                  AS co_mat, count(*) AS tong
           FROM diem_danh dd JOIN buoi_hoc b ON b.id = dd.buoi_hoc_id WHERE b.ngay > %s - 28""",
        (t,),
    ).fetchone()
    active = conn.execute(
        "SELECT count(DISTINCT hoc_vien_id)::int AS n FROM don_hang WHERE trang_thai_hoc = 'dang_hoc'"
    ).fetchone()["n"]
    agents = conn.execute(
        """SELECT count(*) FILTER (WHERE trang_thai = 'cho_duyet')::int AS cho_duyet,
                  count(*) FILTER (WHERE nguoi_duyet = 'auto:L2' AND created_at > now() - interval '7 days')::int
                      AS tu_dong_7_ngay,
                  count(*) FILTER (WHERE trang_thai IN ('da_thuc_hien') AND nguoi_duyet <> 'auto:L2'
                                   AND created_at > now() - interval '7 days')::int AS duyet_7_ngay
           FROM de_xuat_agent"""
    ).fetchone()
    return {
        "ngay": t,
        "doanh_thu_thang": _revenue(conn, month_start, t + timedelta(days=1)),
        "doanh_thu_cung_ky_thang_truoc": _revenue(conn, prev_month_start, same_day_prev + timedelta(days=1)),
        "doanh_thu_theo_thang": revenue_by_month,
        "cong_no": debt,
        "hoc_vien_dang_hoc": active,
        "tuyen_sinh": leads,
        "lop_sap_khai_giang": classes,
        "chuyen_can_4_tuan": None
        if not attendance["tong"]
        else round(float(attendance["co_mat"]) / attendance["tong"], 3),
        "agent": agents,
    }


def weekly_numbers(conn, end: date) -> dict:
    """Số liệu 7 ngày kết thúc ở `end` so với 7 ngày trước đó - đầu vào của agent báo cáo."""

    def window(stop: date) -> dict:
        start = stop - timedelta(days=7)
        return conn.execute(
            """SELECT
                 (SELECT coalesce(sum(so_tien), 0) FROM thanh_toan WHERE ngay_thanh_toan > %(s)s
                      AND ngay_thanh_toan <= %(e)s)::bigint AS doanh_thu,
                 (SELECT count(*) FROM don_hang WHERE ngay_dat > %(s)s AND ngay_dat <= %(e)s)::int AS ghi_danh_moi,
                 (SELECT count(*) FROM khach_tiem_nang WHERE created_at::date > %(s)s
                      AND created_at::date <= %(e)s)::int AS khach_moi,
                 (SELECT count(*) FROM don_hang WHERE trang_thai_hoc = 'da_huy'
                      AND id IN (SELECT doi_tuong_id::int FROM audit_log WHERE hanh_dong = 'huy_ghi_danh'
                                 AND created_at::date > %(s)s AND created_at::date <= %(e)s))::int AS huy""",
            {"s": start, "e": stop},
        ).fetchone()

    this, prev = window(end), window(end - timedelta(days=7))
    overdue = conn.execute(
        """SELECT coalesce(sum(c.con_lai), 0)::bigint AS so_tien, count(DISTINCT d.hoc_vien_id)::int AS hoc_vien
           FROM dot_thanh_toan x JOIN dot_con_lai c ON c.id = x.id JOIN don_hang d ON d.id = x.don_hang_id
           WHERE x.trang_thai = 'qua_han' AND d.trang_thai_hoc <> 'da_huy'"""
    ).fetchone()
    return {"tuan_nay": this, "tuan_truoc": prev, "qua_han": overdue, "den_ngay": end}


def anomalies(numbers: dict, threshold: float = 0.3) -> list[str]:
    """Điểm bất thường: thay đổi quá 30% so với tuần trước (bỏ qua khi tuần trước quá nhỏ)."""
    labels = {"doanh_thu": "Doanh thu", "ghi_danh_moi": "Ghi danh mới", "khach_moi": "Khách mới", "huy": "Huỷ ghi danh"}
    out = []
    for k, label in labels.items():
        a, b = numbers["tuan_nay"][k], numbers["tuan_truoc"][k]
        if b and b >= (1_000_000 if k == "doanh_thu" else 3):
            change = (a - b) / b
            if abs(change) >= threshold:
                out.append(f"{label} {'tăng' if change > 0 else 'giảm'} {abs(change):.0%} so với tuần trước")
    return out
