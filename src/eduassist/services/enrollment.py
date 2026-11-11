"""Phân hệ 3 - Ghi danh và học vụ: ghi danh, chuyển lớp, bảo lưu, huỷ, tạm dừng, điểm danh, điểm, chứng nhận.

Luật: không ghi danh quá sĩ số tối đa; trả góp chỉ cho khoá từ 5 triệu; chuyển lớp miễn phí 1 lần nếu lớp mới
còn chỗ; bảo lưu tối đa 1 lần, tối đa 6 tháng, phí 300.000đ (miễn khi có giấy y tế); hoàn phí theo thời điểm huỷ;
chứng nhận yêu cầu chuyên cần >= 80% và điểm cuối khoá >= 50.
"""

from datetime import timedelta

from eduassist.services import rules
from eduassist.services.core import (
    Actor,
    Conflict,
    Forbidden,
    RuleViolation,
    audit,
    check_transition,
    emit_event,
    has_perm,
    one,
    require,
    today,
)

ACTIVE = list(rules.ACTIVE_ENROLLMENT)


def _enrollment(conn, enrollment_id: int, lock: bool = False) -> dict:
    return one(
        conn,
        """SELECT d.*, lh.ma_lop, lh.khoa_hoc_id, lh.ngay_khai_giang, lh.trang_thai AS lop_trang_thai,
                  lh.giang_vien_id, kh.ten AS khoa_hoc, kh.hoc_phi, kh.so_buoi, hv.ho_ten, hv.email,
                  (SELECT count(*) FROM buoi_hoc b WHERE b.lop_hoc_id = lh.id AND b.trang_thai = 'da_hoc')::int
                      AS buoi_da_hoc,
                  coalesce((SELECT sum(so_tien) FROM thanh_toan t WHERE t.don_hang_id = d.id), 0)::int AS da_dong
           FROM don_hang d JOIN lop_hoc lh ON lh.id = d.lop_hoc_id JOIN khoa_hoc kh ON kh.id = lh.khoa_hoc_id
           JOIN hoc_vien hv ON hv.id = d.hoc_vien_id WHERE d.id = %s"""
        + (" FOR UPDATE OF d" if lock else ""),
        (enrollment_id,),
        "ghi danh",
    )


def _seats_left(conn, class_id: int, lock: bool = True) -> tuple[dict, int]:
    cls = one(
        conn,
        "SELECT * FROM lop_hoc WHERE id = %s" + (" FOR UPDATE" if lock else ""),
        (class_id,),
        "lớp học",
    )
    used = conn.execute(
        "SELECT count(*) AS n FROM don_hang WHERE lop_hoc_id = %s AND trang_thai_hoc = ANY(%s)", (class_id, ACTIVE)
    ).fetchone()["n"]
    return cls, cls["si_so_toi_da"] - used


def _second_installment_due(conn, class_id: int) -> object:
    row = conn.execute(
        "SELECT ngay FROM buoi_hoc WHERE lop_hoc_id = %s AND so_thu_tu = %s",
        (class_id, rules.INSTALLMENT_DUE_SESSION),
    ).fetchone()
    return row["ngay"] - timedelta(days=1) if row else None


def quote(
    conn, actor: Actor, student_id: int, class_id: int, installments: bool, promotion: str | None, voucher: str | None
):
    """Tính trước hoá đơn (hiện cho nhân viên trước khi bấm Ghi danh). Không ghi gì vào DB."""
    require(actor, "enroll.create")
    cls, seats = _seats_left(conn, class_id, lock=False)
    course = one(conn, "SELECT * FROM khoa_hoc WHERE id = %s", (cls["khoa_hoc_id"],))
    problems = []
    if cls["trang_thai"] not in ("sap_khai_giang", "dang_hoc"):
        problems.append("Lớp không còn nhận ghi danh.")
    if seats <= 0:
        problems.append(f"Lớp đã đủ {cls['si_so_toi_da']} học viên.")
    if installments and course["hoc_phi"] < rules.INSTALLMENT_MIN_FEE:
        problems.append("Trả góp chỉ áp dụng cho khoá có học phí từ 5.000.000đ.")
    promo_pct, voucher_pct, voucher_row = 0, 0, None
    if promotion:
        if promotion not in rules.PROMOTIONS:
            problems.append(f"Ưu đãi không hợp lệ: {promotion}.")
        else:
            promo_pct = rules.PROMOTIONS[promotion]
            if promotion == "dang_ky_som":
                if (cls["ngay_khai_giang"] - today()).days < rules.EARLY_BIRD_DAYS:
                    problems.append("Ưu đãi đăng ký sớm cần đăng ký trước khai giảng ít nhất 14 ngày.")
                if installments:
                    problems.append("Ưu đãi đăng ký sớm yêu cầu đóng đủ học phí, không áp dụng cùng trả góp.")
            if promotion == "hoc_vien_cu":
                done = conn.execute(
                    "SELECT 1 FROM don_hang WHERE hoc_vien_id = %s AND trang_thai_hoc = 'hoan_thanh' LIMIT 1",
                    (student_id,),
                ).fetchone()
                if not done:
                    problems.append("Ưu đãi học viên cũ cần đã hoàn thành ít nhất 1 khoá.")
    if voucher:
        voucher_row = conn.execute(
            """SELECT v.* FROM voucher v WHERE v.ma = %s AND v.hoc_vien_id = %s
               AND NOT EXISTS (SELECT 1 FROM don_hang d WHERE d.voucher_id = v.id AND d.trang_thai_hoc <> 'da_huy')""",
            (voucher.strip().upper(), student_id),
        ).fetchone()
        if voucher_row is None:
            problems.append("Voucher không tồn tại, không thuộc học viên này hoặc đã dùng.")
        elif voucher_row["han_su_dung"] < today():
            problems.append("Voucher đã hết hạn.")
        else:
            voucher_pct = voucher_row["phan_tram"]
    discount = rules.compute_discount(course["hoc_phi"], promo_pct, voucher_pct)
    total = course["hoc_phi"] - discount.amount
    plan = rules.installment_plan(
        total, installments, today(), _second_installment_due(conn, class_id) if installments else None
    )
    return {
        "lop_hoc_id": class_id,
        "ma_lop": cls["ma_lop"],
        "khoa_hoc": course["ten"],
        "hoc_phi_goc": course["hoc_phi"],
        "giam_gia": discount.amount,
        "giam_gia_ghi_chu": discount.note,
        "thanh_tien": total,
        "cho_trong": seats,
        "dot": [{"so_tien": a, "han": d} for a, d in plan],
        "loi": problems,
        "_voucher_id": voucher_row["id"] if voucher_row and voucher_pct else None,
    }


def enroll(
    conn,
    actor: Actor,
    student_id: int,
    class_id: int,
    installments: bool = False,
    promotion: str | None = None,
    voucher: str | None = None,
    lead_id: int | None = None,
) -> dict:
    require(actor, "enroll.create")
    one(conn, "SELECT id FROM hoc_vien WHERE id = %s", (student_id,), "học viên")
    _seats_left(conn, class_id, lock=True)  # khoá dòng lớp: hai người ghi danh cùng lúc không vượt sĩ số
    q = quote(conn, actor, student_id, class_id, installments, promotion, voucher)
    if q["loi"]:
        raise RuleViolation(" ".join(q["loi"]))
    dup = conn.execute(
        "SELECT 1 FROM don_hang WHERE hoc_vien_id = %s AND lop_hoc_id = %s AND trang_thai_hoc = ANY(%s)",
        (student_id, class_id, ACTIVE + ["bao_luu"]),
    ).fetchone()
    if dup:
        raise Conflict("Học viên đã ghi danh lớp này.")
    row = conn.execute(
        """INSERT INTO don_hang (hoc_vien_id, lop_hoc_id, ngay_dat, hoc_phi_goc, giam_gia, thanh_tien, trang_thai,
                                 trang_thai_hoc, tra_gop, voucher_id, created_by)
           VALUES (%s, %s, %s, %s, %s, %s, 'chua_thanh_toan', 'cho_thanh_toan', %s, %s, %s) RETURNING id""",
        (
            student_id,
            class_id,
            today(),
            q["hoc_phi_goc"],
            q["giam_gia"],
            q["thanh_tien"],
            installments,
            q["_voucher_id"],
            actor.id,
        ),
    ).fetchone()
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO dot_thanh_toan (don_hang_id, so_thu_tu, so_tien, han_thanh_toan) VALUES (%s, %s, %s, %s)",
            [(row["id"], i, d["so_tien"], d["han"]) for i, d in enumerate(q["dot"], start=1)],
        )
    if lead_id:
        from eduassist.services import crm

        crm.mark_enrolled(conn, actor, lead_id, student_id)
    after = {k: v for k, v in q.items() if not k.startswith("_") and k != "loi"}
    audit(conn, actor, "ghi_danh", "don_hang", row["id"], after={"hoc_vien_id": student_id, **after})
    emit_event(conn, "enrollment.created", don_hang_id=row["id"], hoc_vien_id=student_id, lop_hoc_id=class_id)
    return {"don_hang_id": row["id"], **after}


def _set_status(conn, actor: Actor, enr: dict, target: str, reason: str, action: str) -> None:
    check_transition("ghi danh", rules.ENROLLMENT_TRANSITIONS, enr["trang_thai_hoc"], target)
    conn.execute("UPDATE don_hang SET trang_thai_hoc = %s WHERE id = %s", (target, enr["id"]))
    audit(
        conn,
        actor,
        action,
        "don_hang",
        enr["id"],
        before={"trang_thai_hoc": enr["trang_thai_hoc"]},
        after={"trang_thai_hoc": target},
        reason=reason,
    )
    emit_event(conn, "enrollment.status_changed", don_hang_id=enr["id"], tu=enr["trang_thai_hoc"], sang=target)


def transfer(conn, actor: Actor, enrollment_id: int, new_class_id: int, reason: str = "") -> dict:
    require(actor, "enroll.change")
    enr = _enrollment(conn, enrollment_id, lock=True)
    if enr["trang_thai_hoc"] not in ("dang_hoc", "cho_thanh_toan", "bao_luu"):
        raise RuleViolation("Chỉ chuyển lớp cho ghi danh đang học, chờ thanh toán hoặc đang bảo lưu.")
    if enr["da_chuyen_lop"]:
        raise RuleViolation("Học viên đã dùng lượt chuyển lớp miễn phí (chỉ 1 lần mỗi ghi danh).")
    new_cls, seats = _seats_left(conn, new_class_id)
    if new_cls["id"] == enr["lop_hoc_id"]:
        raise RuleViolation("Lớp mới trùng lớp hiện tại.")
    if new_cls["khoa_hoc_id"] != enr["khoa_hoc_id"]:
        raise RuleViolation("Chỉ chuyển sang lớp khác CÙNG khoá. Đổi khoá thì huỷ và ghi danh lại.")
    if new_cls["trang_thai"] not in ("sap_khai_giang", "dang_hoc"):
        raise RuleViolation("Lớp mới không còn nhận học viên.")
    if seats <= 0:
        raise RuleViolation(f"Lớp {new_cls['ma_lop']} đã hết chỗ.")
    new_status = "dang_hoc" if enr["trang_thai_hoc"] == "bao_luu" else enr["trang_thai_hoc"]
    conn.execute(
        "UPDATE don_hang SET lop_hoc_id = %s, da_chuyen_lop = true, trang_thai_hoc = %s WHERE id = %s",
        (new_class_id, new_status, enrollment_id),
    )
    audit(
        conn,
        actor,
        "chuyen_lop",
        "don_hang",
        enrollment_id,
        before={"lop": enr["ma_lop"]},
        after={"lop": new_cls["ma_lop"]},
        reason=reason,
    )
    emit_event(
        conn, "enrollment.transferred", don_hang_id=enrollment_id, tu_lop=enr["lop_hoc_id"], sang_lop=new_class_id
    )
    return {"don_hang_id": enrollment_id, "lop_moi": new_cls["ma_lop"]}


def reserve(conn, actor: Actor, enrollment_id: int, months: int, reason: str, medical: bool = False) -> dict:
    """Bảo lưu (03 › Bảo lưu): tối đa 1 lần, tối đa 6 tháng, phí 300.000đ, miễn phí khi có giấy y tế."""
    require(actor, "enroll.change")
    enr = _enrollment(conn, enrollment_id, lock=True)
    if not 1 <= months <= rules.RESERVATION_MAX_MONTHS:
        raise RuleViolation(f"Thời gian bảo lưu từ 1 đến {rules.RESERVATION_MAX_MONTHS} tháng.")
    used = conn.execute("SELECT 1 FROM bao_luu WHERE don_hang_id = %s", (enrollment_id,)).fetchone()
    if used:
        raise RuleViolation("Mỗi khoá học chỉ được bảo lưu 1 lần.")
    if not reason.strip():
        raise RuleViolation("Cần ghi lý do bảo lưu.")
    fee = 0 if medical else rules.RESERVATION_FEE
    start = today()
    end = start + timedelta(days=30 * months)
    _set_status(conn, actor, enr, "bao_luu", reason, "bao_luu")
    conn.execute(
        "INSERT INTO bao_luu (don_hang_id, tu_ngay, den_ngay, phi, ly_do, created_by) VALUES (%s, %s, %s, %s, %s, %s)",
        (enrollment_id, start, end, fee, reason, actor.id),
    )
    return {"don_hang_id": enrollment_id, "tu_ngay": start, "den_ngay": end, "phi": fee}


def cancel_enrollment(conn, actor: Actor, enrollment_id: int, reason: str, class_cancelled: bool = False) -> dict:
    """Huỷ ghi danh và lập yêu cầu hoàn phí với tỉ lệ do code tính (03 › Hoàn học phí). Hoàn tiền cần kế toán duyệt."""
    if not class_cancelled:
        require(actor, "enroll.change")
    enr = _enrollment(conn, enrollment_id, lock=True)
    rate, basis = rules.refund_rate(today(), enr["ngay_khai_giang"], enr["buoi_da_hoc"], class_cancelled)
    _set_status(conn, actor, enr, "da_huy", reason, "huy_ghi_danh")
    conn.execute(
        "UPDATE dot_thanh_toan SET trang_thai = 'da_huy' WHERE don_hang_id = %s AND trang_thai <> 'da_thanh_toan'",
        (enrollment_id,),
    )
    if enr["da_dong"] <= 0:
        conn.execute("UPDATE don_hang SET trang_thai = 'da_huy' WHERE id = %s", (enrollment_id,))
        return {"don_hang_id": enrollment_id, "hoan_phi": None}
    amount = enr["da_dong"] * rate // 100
    refund = conn.execute(
        """INSERT INTO hoan_phi (don_hang_id, da_dong, ty_le, so_tien, can_cu, created_by)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (enrollment_id, enr["da_dong"], rate, amount, basis, actor.id),
    ).fetchone()
    emit_event(conn, "refund.requested", hoan_phi_id=refund["id"], don_hang_id=enrollment_id)
    return {
        "don_hang_id": enrollment_id,
        "hoan_phi": {"id": refund["id"], "ty_le": rate, "so_tien": amount, "can_cu": basis},
    }


def suspend(conn, actor: Actor, enrollment_id: int, reason: str) -> dict:
    """Tạm dừng học do nợ quá hạn (02 › Trả góp: quá 14 ngày sau hạn)."""
    require(actor, "enroll.suspend")
    enr = _enrollment(conn, enrollment_id, lock=True)
    overdue = conn.execute(
        """SELECT min(han_thanh_toan) AS han FROM dot_thanh_toan
           WHERE don_hang_id = %s AND trang_thai IN ('chua_thanh_toan', 'qua_han')""",
        (enrollment_id,),
    ).fetchone()["han"]
    if overdue is None or (today() - overdue).days < rules.SUSPEND_AFTER_DAYS:
        raise RuleViolation("Chỉ tạm dừng khi có đợt học phí quá hạn từ 14 ngày trở lên.")
    _set_status(conn, actor, enr, "tam_dung", reason, "tam_dung_hoc")
    return {"don_hang_id": enrollment_id, "trang_thai_hoc": "tam_dung"}


def complete(conn, actor: Actor, enrollment_id: int) -> dict:
    require(actor, "enroll.change")
    enr = _enrollment(conn, enrollment_id, lock=True)
    statuses = [
        r["trang_thai"]
        for r in conn.execute("SELECT trang_thai FROM diem_danh WHERE don_hang_id = %s", (enrollment_id,)).fetchall()
    ]
    final = conn.execute(
        "SELECT diem FROM diem_so WHERE don_hang_id = %s AND loai = 'cuoi_khoa'", (enrollment_id,)
    ).fetchone()
    ok, why = rules.certificate_eligible(statuses, float(final["diem"]) if final else None)
    _set_status(conn, actor, enr, "hoan_thanh", why, "hoan_thanh_khoa")
    return {"don_hang_id": enrollment_id, "du_dieu_kien_chung_nhan": ok, "ly_do": why}


# ---------------------------------------------------------------- điểm danh & điểm số
def _require_class_staff(conn, actor: Actor, class_id: int, perm: str) -> None:
    require(actor, perm)
    if actor.role == "teacher":
        own = conn.execute(
            "SELECT 1 FROM lop_hoc WHERE id = %s AND giang_vien_id = %s", (class_id, actor.giang_vien_id)
        ).fetchone()
        if not own:
            raise Forbidden("Giảng viên chỉ thao tác trên lớp mình dạy.")


def mark_attendance(conn, actor: Actor, session_id: int, entries: list[dict]) -> dict:
    """entries: [{don_hang_id, trang_thai, ghi_chu?}]. Chỉ điểm danh buổi đã diễn ra, học viên của lớp đó."""
    session = one(conn, "SELECT * FROM buoi_hoc WHERE id = %s", (session_id,), "buổi học")
    _require_class_staff(conn, actor, session["lop_hoc_id"], "attendance.write")
    if session["ngay"] > today():
        raise RuleViolation("Chưa tới ngày học, chưa điểm danh được.")
    roster = {
        r["id"]
        for r in conn.execute(
            "SELECT id FROM don_hang WHERE lop_hoc_id = %s AND trang_thai_hoc IN ('dang_hoc', 'tam_dung', 'cho_thanh_toan')",
            (session["lop_hoc_id"],),
        ).fetchall()
    }
    valid = {"co_mat", "vang", "vang_co_phep", "di_tre"}
    for e in entries:
        if e["don_hang_id"] not in roster:
            raise RuleViolation(f"Ghi danh {e['don_hang_id']} không thuộc lớp này.")
        if e["trang_thai"] not in valid:
            raise RuleViolation(f"Trạng thái điểm danh không hợp lệ: {e['trang_thai']}.")
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO diem_danh (buoi_hoc_id, don_hang_id, trang_thai, ghi_chu, updated_by)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (buoi_hoc_id, don_hang_id) DO UPDATE
               SET trang_thai = EXCLUDED.trang_thai, ghi_chu = EXCLUDED.ghi_chu,
                   updated_by = EXCLUDED.updated_by, updated_at = now()""",
            [(session_id, e["don_hang_id"], e["trang_thai"], e.get("ghi_chu"), actor.id) for e in entries],
        )
    conn.execute("UPDATE buoi_hoc SET trang_thai = 'da_hoc' WHERE id = %s", (session_id,))
    absent = [e["don_hang_id"] for e in entries if e["trang_thai"] == "vang"]
    audit(conn, actor, "diem_danh", "buoi_hoc", session_id, after={"so_hoc_vien": len(entries), "vang": len(absent)})
    emit_event(conn, "attendance.marked", buoi_hoc_id=session_id, lop_hoc_id=session["lop_hoc_id"], vang=absent)
    return {"buoi_hoc_id": session_id, "so_hoc_vien": len(entries), "vang": len(absent)}


def session_roster(conn, actor: Actor, session_id: int) -> dict:
    session = one(conn, "SELECT * FROM buoi_hoc WHERE id = %s", (session_id,), "buổi học")
    if not has_perm(actor, "class.read"):
        _require_class_staff(conn, actor, session["lop_hoc_id"], "attendance.write")
    rows = conn.execute(
        """SELECT d.id AS don_hang_id, hv.ho_ten, d.trang_thai_hoc, dd.trang_thai, dd.ghi_chu
           FROM don_hang d JOIN hoc_vien hv ON hv.id = d.hoc_vien_id
           LEFT JOIN diem_danh dd ON dd.don_hang_id = d.id AND dd.buoi_hoc_id = %s
           WHERE d.lop_hoc_id = %s AND d.trang_thai_hoc IN ('dang_hoc', 'tam_dung', 'cho_thanh_toan')
           ORDER BY hv.ho_ten""",
        (session_id, session["lop_hoc_id"]),
    ).fetchall()
    return {**session, "hoc_vien": rows}


def set_grade(conn, actor: Actor, enrollment_id: int, kind: str, score: float, comment: str | None = None) -> dict:
    """Agent không bao giờ sửa điểm: grade.write nằm trong AGENT_FORBIDDEN."""
    enr = _enrollment(conn, enrollment_id)
    _require_class_staff(conn, actor, enr["lop_hoc_id"], "grade.write")
    if kind not in ("giua_khoa", "cuoi_khoa"):
        raise RuleViolation("Loại điểm là giua_khoa hoặc cuoi_khoa.")
    if not 0 <= score <= 100:
        raise RuleViolation("Điểm từ 0 đến 100.")
    before = conn.execute(
        "SELECT diem FROM diem_so WHERE don_hang_id = %s AND loai = %s", (enrollment_id, kind)
    ).fetchone()
    conn.execute(
        """INSERT INTO diem_so (don_hang_id, loai, diem, nhan_xet, updated_by) VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (don_hang_id, loai) DO UPDATE SET diem = EXCLUDED.diem, nhan_xet = EXCLUDED.nhan_xet,
           updated_by = EXCLUDED.updated_by, updated_at = now()""",
        (enrollment_id, kind, score, comment, actor.id),
    )
    audit(
        conn,
        actor,
        "nhap_diem",
        "don_hang",
        enrollment_id,
        before={"diem": before["diem"]} if before else None,
        after={"loai": kind, "diem": score},
    )
    emit_event(conn, "grade.recorded", don_hang_id=enrollment_id, loai=kind, diem=score)
    return {"don_hang_id": enrollment_id, "loai": kind, "diem": score}
