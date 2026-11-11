"""Phân hệ 2 - Đào tạo: khoá học, lớp, lịch, phòng, giảng viên.

Luật: không xếp trùng phòng hoặc trùng giảng viên; phòng phải đủ sức chứa; lớp chỉ mở khi đạt sĩ số tối thiểu.
"""

from datetime import date, timedelta

from eduassist.services import rules
from eduassist.services.core import (
    Actor,
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

CLASS_LIST_SQL = """
SELECT lh.id, lh.ma_lop, lh.khoa_hoc_id, kh.ten AS khoa_hoc, kh.ma AS ma_khoa, kh.hoc_phi, kh.so_buoi,
       lh.ngay_khai_giang, lh.ca_hoc, lh.lich_hoc, lh.hinh_thuc, lh.si_so_toi_da, lh.si_so_toi_thieu, lh.trang_thai,
       lh.giang_vien_id, coalesce(gv.ho_ten, lh.giang_vien) AS giang_vien,
       lh.phong_hoc_id, ph.ten AS phong, cs.ten AS co_so,
       (SELECT count(*) FROM don_hang d WHERE d.lop_hoc_id = lh.id AND d.trang_thai_hoc = ANY(%(active)s))::int AS si_so,
       (SELECT count(*) FROM buoi_hoc b WHERE b.lop_hoc_id = lh.id AND b.trang_thai = 'da_hoc')::int AS buoi_da_hoc,
       (SELECT max(ngay) FROM buoi_hoc b WHERE b.lop_hoc_id = lh.id) AS ngay_ket_thuc
FROM lop_hoc lh
JOIN khoa_hoc kh ON kh.id = lh.khoa_hoc_id
LEFT JOIN giang_vien gv ON gv.id = lh.giang_vien_id
LEFT JOIN phong_hoc ph ON ph.id = lh.phong_hoc_id
LEFT JOIN co_so cs ON cs.id = ph.co_so_id
"""


def _can_read_class(conn, actor: Actor, class_id: int) -> None:
    if has_perm(actor, "class.read"):
        return
    if has_perm(actor, "class.read_own") and actor.giang_vien_id:
        own = conn.execute(
            "SELECT 1 FROM lop_hoc WHERE id = %s AND giang_vien_id = %s", (class_id, actor.giang_vien_id)
        ).fetchone()
        if own:
            return
    raise Forbidden("Bạn chỉ xem được lớp mình phụ trách.")


def list_courses(conn, actor: Actor) -> list[dict]:
    return conn.execute(
        "SELECT id, ma, ten, danh_muc, trinh_do, hoc_phi, so_buoi, mo_ta FROM khoa_hoc ORDER BY danh_muc, hoc_phi"
    ).fetchall()


def list_classes(conn, actor: Actor, status: str | None = None, course_id: int | None = None, q: str | None = None):
    where, params = ["true"], {"active": ACTIVE}
    if not has_perm(actor, "class.read"):
        if not (has_perm(actor, "class.read_own") and actor.giang_vien_id):
            raise Forbidden("Bạn không có quyền xem danh sách lớp.")
        where.append("lh.giang_vien_id = %(gv)s")
        params["gv"] = actor.giang_vien_id
    if status:
        where.append("lh.trang_thai = %(st)s")
        params["st"] = status
    if course_id:
        where.append("lh.khoa_hoc_id = %(kh)s")
        params["kh"] = course_id
    if q:
        where.append("(lh.ma_lop ILIKE %(q)s OR kh.ten ILIKE %(q)s)")
        params["q"] = f"%{q}%"
    return conn.execute(
        CLASS_LIST_SQL
        + " WHERE "
        + " AND ".join(where)
        + " ORDER BY CASE lh.trang_thai WHEN 'dang_hoc' THEN 0 WHEN 'sap_khai_giang' THEN 1 ELSE 2 END,"
        " lh.ngay_khai_giang DESC",
        params,
    ).fetchall()


def get_class(conn, actor: Actor, class_id: int) -> dict:
    _can_read_class(conn, actor, class_id)
    cls = one(conn, CLASS_LIST_SQL + " WHERE lh.id = %(id)s", {"active": ACTIVE, "id": class_id}, "lớp học")
    cls["buoi"] = conn.execute(
        """SELECT b.id, b.so_thu_tu, b.ngay, b.trang_thai,
                  (SELECT count(*) FROM diem_danh dd WHERE dd.buoi_hoc_id = b.id)::int AS da_diem_danh
           FROM buoi_hoc b WHERE b.lop_hoc_id = %s ORDER BY b.so_thu_tu""",
        (class_id,),
    ).fetchall()
    cls["hoc_vien"] = conn.execute(
        """SELECT d.id AS don_hang_id, hv.id AS hoc_vien_id, hv.ho_ten, hv.email, hv.so_dien_thoai,
                  d.trang_thai, d.trang_thai_hoc, d.thanh_tien,
                  d.thanh_tien - coalesce((SELECT sum(so_tien) FROM thanh_toan t WHERE t.don_hang_id = d.id), 0)
                      AS con_no,
                  (SELECT count(*) FILTER (WHERE dd.trang_thai = 'vang') FROM diem_danh dd WHERE dd.don_hang_id = d.id)
                      ::int AS so_buoi_vang,
                  (SELECT count(*) FROM diem_danh dd WHERE dd.don_hang_id = d.id)::int AS so_buoi_diem_danh
           FROM don_hang d JOIN hoc_vien hv ON hv.id = d.hoc_vien_id
           WHERE d.lop_hoc_id = %s AND d.trang_thai_hoc <> 'da_huy'
           ORDER BY hv.ho_ten""",
        (class_id,),
    ).fetchall()
    return cls


def list_teachers(conn, actor: Actor) -> list[dict]:
    require(actor, "class.read")
    return conn.execute("SELECT id, ho_ten, email, chuyen_mon FROM giang_vien ORDER BY ho_ten").fetchall()


def list_rooms(conn, actor: Actor) -> list[dict]:
    require(actor, "class.read")
    return conn.execute(
        """SELECT ph.id, ph.ten, ph.suc_chua, cs.ten AS co_so FROM phong_hoc ph JOIN co_so cs ON cs.id = ph.co_so_id
           ORDER BY cs.ten, ph.ten"""
    ).fetchall()


# ---------------------------------------------------------------- trùng lịch
def _slot_of(start: date, schedule: str, shift: str, sessions: int) -> rules.Slot:
    dates = rules.session_dates(start, schedule, sessions)
    return rules.Slot(dates[0], dates[-1], shift, schedule)


def find_conflicts(
    conn,
    start: date,
    schedule: str,
    shift: str,
    sessions: int,
    teacher_id: int | None,
    room_id: int | None,
    exclude_class: int | None = None,
) -> list[dict]:
    """Các lớp đang/ sắp học bị trùng giảng viên hoặc trùng phòng với khung giờ đề xuất."""
    if teacher_id is None and room_id is None:
        return []
    mine = _slot_of(start, schedule, shift, sessions)
    others = conn.execute(
        """SELECT lh.id, lh.ma_lop, lh.ngay_khai_giang, lh.ca_hoc, lh.lich_hoc, lh.giang_vien_id, lh.phong_hoc_id,
                  kh.so_buoi, (SELECT max(ngay) FROM buoi_hoc b WHERE b.lop_hoc_id = lh.id) AS ket_thuc
           FROM lop_hoc lh JOIN khoa_hoc kh ON kh.id = lh.khoa_hoc_id
           WHERE lh.trang_thai IN ('sap_khai_giang', 'dang_hoc') AND lh.id <> coalesce(%s, -1)
             AND (lh.giang_vien_id = %s OR lh.phong_hoc_id = %s)""",
        (exclude_class, teacher_id, room_id),
    ).fetchall()
    out = []
    for o in others:
        end = o["ket_thuc"] or _slot_of(o["ngay_khai_giang"], o["lich_hoc"], o["ca_hoc"], o["so_buoi"]).end
        other = rules.Slot(o["ngay_khai_giang"], end, o["ca_hoc"], o["lich_hoc"])
        if rules.slots_overlap(mine, other):
            kinds = []
            if teacher_id and o["giang_vien_id"] == teacher_id:
                kinds.append("giảng viên")
            if room_id and o["phong_hoc_id"] == room_id:
                kinds.append("phòng")
            out.append({"lop_hoc_id": o["id"], "ma_lop": o["ma_lop"], "trung": kinds})
    return out


def _check_room_and_conflicts(conn, data: dict, sessions: int, exclude: int | None = None) -> None:
    if data.get("phong_hoc_id"):
        room = one(conn, "SELECT suc_chua, ten FROM phong_hoc WHERE id = %s", (data["phong_hoc_id"],), "phòng học")
        if room["suc_chua"] < data["si_so_toi_da"]:
            raise RuleViolation(
                f"Phòng {room['ten']} chỉ chứa {room['suc_chua']} người, nhỏ hơn sĩ số tối đa {data['si_so_toi_da']}."
            )
    conflicts = find_conflicts(
        conn,
        data["ngay_khai_giang"],
        data["lich_hoc"],
        data["ca_hoc"],
        sessions,
        data.get("giang_vien_id"),
        data.get("phong_hoc_id"),
        exclude,
    )
    if conflicts:
        detail = "; ".join(f"{c['ma_lop']} (trùng {' và '.join(c['trung'])})" for c in conflicts)
        raise RuleViolation(f"Trùng lịch với lớp {detail}.")


def create_class(conn, actor: Actor, data: dict) -> dict:
    """data: khoa_hoc_id, ngay_khai_giang, ca_hoc, lich_hoc, hinh_thuc, si_so_toi_da, si_so_toi_thieu,
    giang_vien_id, phong_hoc_id."""
    require(actor, "class.write")
    course = one(conn, "SELECT id, ma, so_buoi FROM khoa_hoc WHERE id = %s", (data["khoa_hoc_id"],), "khoá học")
    if data["ngay_khai_giang"] <= today():
        raise RuleViolation("Ngày khai giảng phải sau hôm nay.")
    if not 1 <= data["si_so_toi_thieu"] <= data["si_so_toi_da"]:
        raise RuleViolation("Sĩ số tối thiểu phải từ 1 đến sĩ số tối đa.")
    try:
        rules.weekdays(data["lich_hoc"])
    except ValueError as e:
        raise RuleViolation(str(e)) from e
    if data["hinh_thuc"] == "offline" and not data.get("phong_hoc_id"):
        raise RuleViolation("Lớp offline phải có phòng học.")
    _check_room_and_conflicts(conn, data, course["so_buoi"])
    seq = conn.execute("SELECT coalesce(max(id), 0) + 1 AS n FROM lop_hoc").fetchone()["n"]
    code = f"{course['ma']}-{data['ngay_khai_giang']:%y%m}-{seq:03d}"
    teacher = None
    if data.get("giang_vien_id"):
        teacher = one(conn, "SELECT ho_ten FROM giang_vien WHERE id = %s", (data["giang_vien_id"],), "giảng viên")
    row = conn.execute(
        """INSERT INTO lop_hoc (ma_lop, khoa_hoc_id, ngay_khai_giang, ca_hoc, lich_hoc, hinh_thuc, si_so_toi_da,
                                si_so_toi_thieu, giang_vien, giang_vien_id, phong_hoc_id, trang_thai)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'sap_khai_giang') RETURNING id""",
        (
            code,
            course["id"],
            data["ngay_khai_giang"],
            data["ca_hoc"],
            data["lich_hoc"],
            data["hinh_thuc"],
            data["si_so_toi_da"],
            data["si_so_toi_thieu"],
            teacher["ho_ten"] if teacher else "Chưa phân công",
            data.get("giang_vien_id"),
            data.get("phong_hoc_id"),
        ),
    ).fetchone()
    _create_sessions(conn, row["id"], data["ngay_khai_giang"], data["lich_hoc"], course["so_buoi"])
    audit(conn, actor, "tao_lop", "lop_hoc", row["id"], after={**data, "ma_lop": code})
    emit_event(conn, "class.created", lop_hoc_id=row["id"])
    return get_class(conn, actor, row["id"])


def _create_sessions(conn, class_id: int, start: date, schedule: str, count: int) -> None:
    dates = rules.session_dates(start, schedule, count)
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO buoi_hoc (lop_hoc_id, so_thu_tu, ngay) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            [(class_id, i, d) for i, d in enumerate(dates, start=1)],
        )


def update_schedule(conn, actor: Actor, class_id: int, changes: dict) -> dict:
    """Đổi giảng viên / phòng / ca / lịch. Buổi chưa học được xếp lại ngày; kiểm tra trùng lịch như khi tạo lớp."""
    require(actor, "class.write")
    cur = one(
        conn,
        """SELECT lh.*, kh.so_buoi FROM lop_hoc lh JOIN khoa_hoc kh ON kh.id = lh.khoa_hoc_id
           WHERE lh.id = %s FOR UPDATE OF lh""",
        (class_id,),
        "lớp học",
    )
    if cur["trang_thai"] not in ("sap_khai_giang", "dang_hoc"):
        raise RuleViolation("Chỉ đổi lịch được cho lớp sắp khai giảng hoặc đang học.")
    allowed = {"giang_vien_id", "phong_hoc_id", "ca_hoc", "lich_hoc", "si_so_toi_da", "si_so_toi_thieu"}
    changes = {k: v for k, v in changes.items() if k in allowed and v is not None}
    if not changes:
        raise RuleViolation("Không có thay đổi nào.")
    merged = {**cur, **changes}
    if "lich_hoc" in changes:
        try:
            rules.weekdays(changes["lich_hoc"])
        except ValueError as e:
            raise RuleViolation(str(e)) from e
    enrolled = conn.execute(
        "SELECT count(*) AS n FROM don_hang WHERE lop_hoc_id = %s AND trang_thai_hoc = ANY(%s)", (class_id, ACTIVE)
    ).fetchone()["n"]
    if merged["si_so_toi_da"] < enrolled:
        raise RuleViolation(f"Lớp đã có {enrolled} học viên, không giảm sĩ số tối đa xuống {merged['si_so_toi_da']}.")
    _check_room_and_conflicts(conn, merged, cur["so_buoi"], exclude=class_id)
    teacher_name = cur["giang_vien"]
    if "giang_vien_id" in changes:
        teacher_name = one(conn, "SELECT ho_ten FROM giang_vien WHERE id = %s", (changes["giang_vien_id"],))["ho_ten"]
    conn.execute(
        """UPDATE lop_hoc SET giang_vien_id = %s, giang_vien = %s, phong_hoc_id = %s, ca_hoc = %s, lich_hoc = %s,
                              si_so_toi_da = %s, si_so_toi_thieu = %s WHERE id = %s""",
        (
            merged["giang_vien_id"],
            teacher_name,
            merged["phong_hoc_id"],
            merged["ca_hoc"],
            merged["lich_hoc"],
            merged["si_so_toi_da"],
            merged["si_so_toi_thieu"],
            class_id,
        ),
    )
    if "lich_hoc" in changes:
        _reschedule_future_sessions(conn, class_id, merged["lich_hoc"])
    audit(conn, actor, "doi_lich_lop", "lop_hoc", class_id, before={k: cur[k] for k in changes}, after=changes)
    emit_event(conn, "class.schedule_changed", lop_hoc_id=class_id)
    return get_class(conn, actor, class_id)


def _reschedule_future_sessions(conn, class_id: int, schedule: str) -> None:
    pending = conn.execute(
        "SELECT id FROM buoi_hoc WHERE lop_hoc_id = %s AND trang_thai = 'du_kien' ORDER BY so_thu_tu", (class_id,)
    ).fetchall()
    if not pending:
        return
    last_done = conn.execute(
        "SELECT max(ngay) AS d FROM buoi_hoc WHERE lop_hoc_id = %s AND trang_thai <> 'du_kien'", (class_id,)
    ).fetchone()["d"]
    start = max(today(), last_done) if last_done else today()
    dates = rules.session_dates(start + timedelta(days=1), schedule, len(pending))
    for row, d in zip(pending, dates, strict=True):
        conn.execute("UPDATE buoi_hoc SET ngay = %s WHERE id = %s", (d, row["id"]))


def open_class(conn, actor: Actor, class_id: int) -> dict:
    require(actor, "class.write")
    cls = get_class(conn, actor, class_id)
    check_transition("lớp", rules.CLASS_TRANSITIONS, cls["trang_thai"], "dang_hoc")
    if cls["si_so"] < cls["si_so_toi_thieu"]:
        raise RuleViolation(
            f"Lớp mới có {cls['si_so']}/{cls['si_so_toi_thieu']} học viên tối thiểu - chưa đủ sĩ số để khai giảng."
        )
    conn.execute("UPDATE lop_hoc SET trang_thai = 'dang_hoc' WHERE id = %s", (class_id,))
    audit(conn, actor, "khai_giang", "lop_hoc", class_id, before={"trang_thai": cls["trang_thai"]})
    return get_class(conn, actor, class_id)


def cancel_class(conn, actor: Actor, class_id: int, reason: str) -> dict:
    """Huỷ lớp chưa khai giảng: huỷ mọi ghi danh, tạo yêu cầu hoàn 100% (03 › lớp không đủ sĩ số)."""
    from eduassist.services import enrollment

    require(actor, "class.write")
    cls = get_class(conn, actor, class_id)
    check_transition("lớp", rules.CLASS_TRANSITIONS, cls["trang_thai"], "da_huy")
    if not reason.strip():
        raise RuleViolation("Cần ghi lý do huỷ lớp.")
    conn.execute("UPDATE lop_hoc SET trang_thai = 'da_huy' WHERE id = %s", (class_id,))
    refunds = 0
    for hv in cls["hoc_vien"]:
        if hv["trang_thai_hoc"] in rules.ACTIVE_ENROLLMENT:
            enrollment.cancel_enrollment(conn, actor, hv["don_hang_id"], f"Lớp bị huỷ: {reason}", class_cancelled=True)
            refunds += 1
    audit(conn, actor, "huy_lop", "lop_hoc", class_id, before={"trang_thai": cls["trang_thai"]}, reason=reason)
    emit_event(conn, "class.cancelled", lop_hoc_id=class_id, so_hoc_vien=refunds)
    return {"lop_hoc_id": class_id, "so_ghi_danh_huy": refunds}


def merge_class(conn, actor: Actor, source_id: int, target_id: int, reason: str) -> dict:
    """Gộp lớp thiếu sĩ số vào lớp khác cùng khoá: chuyển mọi học viên (không tính vào lượt chuyển lớp miễn phí
    của học viên vì do trung tâm chủ động), rồi huỷ lớp nguồn."""
    require(actor, "class.write")
    src = get_class(conn, actor, source_id)
    dst = get_class(conn, actor, target_id)
    conn.execute("SELECT id FROM lop_hoc WHERE id = ANY(%s) FOR UPDATE", ([source_id, target_id],))
    if src["khoa_hoc_id"] != dst["khoa_hoc_id"]:
        raise RuleViolation("Chỉ gộp các lớp cùng khoá học.")
    if src["trang_thai"] != "sap_khai_giang" or dst["trang_thai"] not in ("sap_khai_giang", "dang_hoc"):
        raise RuleViolation("Chỉ gộp lớp chưa khai giảng vào lớp sắp khai giảng hoặc đang học.")
    if dst["trang_thai"] == "dang_hoc" and dst["buoi_da_hoc"] >= 3:
        raise RuleViolation(f"Lớp {dst['ma_lop']} đã học {dst['buoi_da_hoc']} buổi, quá muộn để nhận học viên mới.")
    moving = [h for h in src["hoc_vien"] if h["trang_thai_hoc"] in rules.ACTIVE_ENROLLMENT]
    if dst["si_so"] + len(moving) > dst["si_so_toi_da"]:
        raise RuleViolation(
            f"Lớp {dst['ma_lop']} còn {dst['si_so_toi_da'] - dst['si_so']} chỗ, không đủ cho {len(moving)} học viên."
        )
    ids = [h["don_hang_id"] for h in moving]
    conn.execute("UPDATE don_hang SET lop_hoc_id = %s WHERE id = ANY(%s)", (target_id, ids))
    conn.execute("UPDATE lop_hoc SET trang_thai = 'da_huy' WHERE id = %s", (source_id,))
    audit(
        conn,
        actor,
        "gop_lop",
        "lop_hoc",
        source_id,
        after={"gop_vao": dst["ma_lop"], "so_hoc_vien": len(ids)},
        reason=reason,
    )
    emit_event(conn, "class.merged", tu_lop=source_id, sang_lop=target_id, don_hang_ids=ids)
    return {"tu_lop": src["ma_lop"], "sang_lop": dst["ma_lop"], "so_hoc_vien": len(ids)}
