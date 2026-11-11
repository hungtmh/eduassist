"""Hồ sơ học viên (nhân viên xem) và Phân hệ 5 - Cổng học viên.

Luật cổng học viên: học viên chỉ thấy dữ liệu của chính mình - id lấy từ phiên đăng nhập (actor.hoc_vien_id),
KHÔNG BAO GIỜ từ tham số do người dùng gửi lên.
"""

from eduassist.services import enrollment
from eduassist.services.core import Actor, Forbidden, RuleViolation, audit, emit_event, one, require, today

ENROLLMENTS_SQL = """
SELECT d.id AS don_hang_id, d.lop_hoc_id, lh.ma_lop, kh.ten AS khoa_hoc, lh.ngay_khai_giang, lh.ca_hoc, lh.lich_hoc,
       lh.hinh_thuc, coalesce(gv.ho_ten, lh.giang_vien) AS giang_vien, ph.ten AS phong, cs.ten AS co_so,
       d.trang_thai, d.trang_thai_hoc, d.thanh_tien, d.tra_gop,
       (d.thanh_tien - coalesce((SELECT sum(so_tien) FROM thanh_toan t WHERE t.don_hang_id = d.id), 0))::int AS con_no,
       (SELECT count(*) FROM diem_danh dd WHERE dd.don_hang_id = d.id)::int AS so_buoi_diem_danh,
       (SELECT count(*) FILTER (WHERE dd.trang_thai IN ('vang', 'vang_co_phep')) FROM diem_danh dd
            WHERE dd.don_hang_id = d.id)::int AS so_buoi_vang,
       (SELECT diem FROM diem_so s WHERE s.don_hang_id = d.id AND s.loai = 'cuoi_khoa') AS diem_cuoi_khoa
FROM don_hang d JOIN lop_hoc lh ON lh.id = d.lop_hoc_id JOIN khoa_hoc kh ON kh.id = lh.khoa_hoc_id
LEFT JOIN giang_vien gv ON gv.id = lh.giang_vien_id LEFT JOIN phong_hoc ph ON ph.id = lh.phong_hoc_id
LEFT JOIN co_so cs ON cs.id = ph.co_so_id
WHERE d.hoc_vien_id = %s ORDER BY lh.ngay_khai_giang DESC
"""


def list_students(conn, actor: Actor, q: str | None = None, limit: int = 100) -> list[dict]:
    require(actor, "student.read")
    return conn.execute(
        """SELECT hv.id, hv.ho_ten, hv.email, hv.so_dien_thoai, hv.thanh_pho, hv.nguon, hv.ngay_dang_ky,
                  (SELECT count(*) FROM don_hang d WHERE d.hoc_vien_id = hv.id AND d.trang_thai_hoc = 'dang_hoc')::int
                      AS so_lop_dang_hoc,
                  coalesce((SELECT sum(d.thanh_tien - coalesce((SELECT sum(so_tien) FROM thanh_toan t
                                                               WHERE t.don_hang_id = d.id), 0))
                            FROM don_hang d WHERE d.hoc_vien_id = hv.id
                              AND d.trang_thai IN ('chua_thanh_toan', 'thanh_toan_mot_phan')
                              AND d.trang_thai_hoc <> 'da_huy'), 0)::bigint AS con_no
           FROM hoc_vien hv
           WHERE %(q)s::text IS NULL OR hv.ho_ten ILIKE %(like)s OR hv.email ILIKE %(like)s
                 OR hv.so_dien_thoai ILIKE %(like)s OR hv.id::text = %(q)s
           ORDER BY hv.id DESC LIMIT %(limit)s""",
        {"q": q, "like": f"%{q}%", "limit": limit},
    ).fetchall()


def get_student(conn, actor: Actor, student_id: int) -> dict:
    if actor.role == "student":
        if actor.hoc_vien_id != student_id:
            raise Forbidden("Bạn chỉ xem được hồ sơ của mình.")
    else:
        require(actor, "student.read")
    hv = one(conn, "SELECT * FROM hoc_vien WHERE id = %s", (student_id,), "học viên")
    hv["ghi_danh"] = conn.execute(ENROLLMENTS_SQL, (student_id,)).fetchall()
    hv["yeu_cau"] = conn.execute(
        "SELECT * FROM yeu_cau WHERE hoc_vien_id = %s ORDER BY created_at DESC", (student_id,)
    ).fetchall()
    hv["voucher"] = conn.execute(
        "SELECT ma, phan_tram, ly_do, han_su_dung FROM voucher WHERE hoc_vien_id = %s ORDER BY created_at DESC",
        (student_id,),
    ).fetchall()
    if actor.is_staff:
        hv["email_da_gui"] = conn.execute(
            """SELECT subject, sent_by, sent_at, loai FROM email_log WHERE hoc_vien_id = %s
               ORDER BY sent_at DESC LIMIT 20""",
            (student_id,),
        ).fetchall()
    return hv


# ---------------------------------------------------------------- cổng học viên
def _me(actor: Actor) -> int:
    if actor.role != "student" or actor.hoc_vien_id is None:
        raise Forbidden("Chỉ tài khoản học viên dùng được cổng học viên.")
    return actor.hoc_vien_id


def portal_overview(conn, actor: Actor) -> dict:
    hv_id = _me(actor)
    me = one(conn, "SELECT id, ho_ten, email, so_dien_thoai FROM hoc_vien WHERE id = %s", (hv_id,), "học viên")
    enrollments = conn.execute(ENROLLMENTS_SQL, (hv_id,)).fetchall()
    upcoming = conn.execute(
        """SELECT b.ngay, b.so_thu_tu, lh.ma_lop, kh.ten AS khoa_hoc, lh.ca_hoc, ph.ten AS phong, cs.ten AS co_so,
                  lh.hinh_thuc
           FROM buoi_hoc b JOIN lop_hoc lh ON lh.id = b.lop_hoc_id JOIN khoa_hoc kh ON kh.id = lh.khoa_hoc_id
           JOIN don_hang d ON d.lop_hoc_id = lh.id
           LEFT JOIN phong_hoc ph ON ph.id = lh.phong_hoc_id LEFT JOIN co_so cs ON cs.id = ph.co_so_id
           WHERE d.hoc_vien_id = %s AND d.trang_thai_hoc IN ('dang_hoc', 'cho_thanh_toan') AND b.ngay >= %s
             AND b.trang_thai = 'du_kien'
           ORDER BY b.ngay LIMIT 10""",
        (hv_id, today()),
    ).fetchall()
    dues = conn.execute(
        """SELECT x.id, x.don_hang_id, x.so_thu_tu, c.con_lai AS so_tien, x.han_thanh_toan, x.trang_thai, lh.ma_lop,
                  kh.ten AS khoa_hoc
           FROM dot_thanh_toan x JOIN dot_con_lai c ON c.id = x.id JOIN don_hang d ON d.id = x.don_hang_id JOIN lop_hoc lh ON lh.id = d.lop_hoc_id
           JOIN khoa_hoc kh ON kh.id = lh.khoa_hoc_id
           WHERE d.hoc_vien_id = %s AND x.trang_thai IN ('chua_thanh_toan', 'qua_han') AND d.trang_thai_hoc <> 'da_huy'
             AND c.con_lai > 0
           ORDER BY x.han_thanh_toan""",
        (hv_id,),
    ).fetchall()
    requests = conn.execute(
        "SELECT * FROM yeu_cau WHERE hoc_vien_id = %s ORDER BY created_at DESC", (hv_id,)
    ).fetchall()
    for e in enrollments:
        total = e["so_buoi_diem_danh"]
        e["chuyen_can"] = None if not total else round(1 - e["so_buoi_vang"] / total, 3)
    return {"hoc_vien": me, "ghi_danh": enrollments, "lich_sap_toi": upcoming, "cong_no": dues, "yeu_cau": requests}


def submit_request(conn, actor: Actor, kind: str, content: str, enrollment_id: int | None = None) -> dict:
    hv_id = _me(actor)
    if kind not in ("bao_luu", "hoan_phi", "chuyen_lop", "khac"):
        raise RuleViolation("Loại yêu cầu không hợp lệ.")
    if len(content.strip()) < 5:
        raise RuleViolation("Nội dung yêu cầu quá ngắn.")
    if kind != "khac":
        if enrollment_id is None:
            raise RuleViolation("Cần chọn lớp liên quan.")
        own = conn.execute(
            "SELECT trang_thai_hoc FROM don_hang WHERE id = %s AND hoc_vien_id = %s", (enrollment_id, hv_id)
        ).fetchone()
        if own is None:
            raise Forbidden("Lớp này không thuộc tài khoản của bạn.")
        if own["trang_thai_hoc"] in ("da_huy", "hoan_thanh"):
            raise RuleViolation("Ghi danh này đã kết thúc.")
    open_same = conn.execute(
        """SELECT id FROM yeu_cau WHERE hoc_vien_id = %s AND loai = %s AND don_hang_id IS NOT DISTINCT FROM %s
           AND trang_thai IN ('moi', 'dang_xu_ly')""",
        (hv_id, kind, enrollment_id),
    ).fetchone()
    if open_same:
        raise RuleViolation(f"Bạn đã có yêu cầu #{open_same['id']} cùng loại đang được xử lý.")
    row = conn.execute(
        "INSERT INTO yeu_cau (hoc_vien_id, don_hang_id, loai, noi_dung) VALUES (%s, %s, %s, %s) RETURNING *",
        (hv_id, enrollment_id, kind, content.strip()),
    ).fetchone()
    audit(conn, actor, "gui_yeu_cau", "yeu_cau", row["id"], after={"loai": kind})
    emit_event(conn, "request.submitted", yeu_cau_id=row["id"], loai=kind)
    return row


def list_requests(conn, actor: Actor, status: str | None = None) -> list[dict]:
    require(actor, "request.handle")
    return conn.execute(
        """SELECT y.*, hv.ho_ten, lh.ma_lop FROM yeu_cau y JOIN hoc_vien hv ON hv.id = y.hoc_vien_id
           LEFT JOIN don_hang d ON d.id = y.don_hang_id LEFT JOIN lop_hoc lh ON lh.id = d.lop_hoc_id
           WHERE (%s::text IS NULL OR y.trang_thai = %s) ORDER BY y.created_at DESC LIMIT 200""",
        (status, status),
    ).fetchall()


def handle_request(conn, actor: Actor, request_id: int, approve: bool, reply: str, params: dict | None = None) -> dict:
    """Duyệt yêu cầu = gọi đúng nghiệp vụ (bảo lưu / huỷ + hoàn phí / chuyển lớp) - cùng luật như thao tác trực tiếp."""
    require(actor, "request.handle")
    req = one(conn, "SELECT * FROM yeu_cau WHERE id = %s FOR UPDATE", (request_id,), "yêu cầu")
    if req["trang_thai"] not in ("moi", "dang_xu_ly"):
        raise RuleViolation("Yêu cầu đã được xử lý.")
    params = params or {}
    result = None
    if approve:
        if req["loai"] == "bao_luu":
            result = enrollment.reserve(
                conn,
                actor,
                req["don_hang_id"],
                int(params.get("so_thang", 3)),
                req["noi_dung"],
                bool(params.get("mien_phi", False)),
            )
        elif req["loai"] == "hoan_phi":
            result = enrollment.cancel_enrollment(conn, actor, req["don_hang_id"], f"Yêu cầu #{request_id}")
        elif req["loai"] == "chuyen_lop":
            if not params.get("lop_moi_id"):
                raise RuleViolation("Cần chọn lớp mới để chuyển.")
            result = enrollment.transfer(conn, actor, req["don_hang_id"], int(params["lop_moi_id"]), req["noi_dung"])
    status = "da_xu_ly" if approve else "tu_choi"
    conn.execute(
        "UPDATE yeu_cau SET trang_thai = %s, phan_hoi = %s, xu_ly_boi = %s, updated_at = now() WHERE id = %s",
        (status, reply, actor.id, request_id),
    )
    audit(
        conn,
        actor,
        "xu_ly_yeu_cau",
        "yeu_cau",
        request_id,
        after={"trang_thai": status, "ket_qua": result},
        reason=reply,
    )
    return {"id": request_id, "trang_thai": status, "ket_qua": result}


def attendance_history(conn, enrollment_id: int, limit: int = 10) -> list[str]:
    """Trạng thái điểm danh, buổi gần nhất trước."""
    return [
        r["trang_thai"]
        for r in conn.execute(
            """SELECT dd.trang_thai FROM diem_danh dd JOIN buoi_hoc b ON b.id = dd.buoi_hoc_id
               WHERE dd.don_hang_id = %s ORDER BY b.ngay DESC LIMIT %s""",
            (enrollment_id, limit),
        ).fetchall()
    ]
