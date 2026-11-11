"""Phân hệ 1 - Tuyển sinh (CRM): khách tiềm năng, lịch hẹn, học thử, chuyển thành học viên, việc cần làm.

Luật: khách chuyển trạng thái theo đúng trình tự (rules.LEAD_TRANSITIONS); mỗi khách có một người phụ trách
(tự phân cho tư vấn viên đang ít khách nhất); ngừng theo đuổi phải có lý do; quá 3 ngày chưa liên hệ thì cảnh báo.
"""

from datetime import date, datetime

from eduassist.services import rules
from eduassist.services.core import (
    Actor,
    Conflict,
    RuleViolation,
    audit,
    check_transition,
    emit_event,
    now,
    one,
    require,
    today,
)

LEAD_SQL = """
SELECT k.*, kh.ten AS khoa_quan_tam, u.display_name AS ten_phu_trach,
       (%(today)s - k.created_at::date) AS so_ngay,
       (SELECT min(thoi_gian) FROM lich_hen lh WHERE lh.khach_id = k.id AND lh.thoi_gian >= now()) AS lich_hen_toi
FROM khach_tiem_nang k
LEFT JOIN khoa_hoc kh ON kh.id = k.khoa_quan_tam_id
LEFT JOIN app_user u ON u.username = k.phu_trach
"""


def list_leads(conn, actor: Actor, status: str | None = None, owner: str | None = None, q: str | None = None):
    require(actor, "lead.read")
    where, params = ["true"], {"today": today()}
    if status:
        where.append("k.trang_thai = %(st)s")
        params["st"] = status
    if owner:
        where.append("k.phu_trach = %(owner)s")
        params["owner"] = owner
    if q:
        where.append("(k.ho_ten ILIKE %(q)s OR k.so_dien_thoai ILIKE %(q)s OR k.email ILIKE %(q)s)")
        params["q"] = f"%{q}%"
    return conn.execute(
        LEAD_SQL + " WHERE " + " AND ".join(where) + " ORDER BY k.diem DESC NULLS LAST, k.created_at DESC LIMIT 300",
        params,
    ).fetchall()


def get_lead(conn, actor: Actor, lead_id: int) -> dict:
    require(actor, "lead.read")
    lead = one(conn, LEAD_SQL + " WHERE k.id = %(id)s", {"today": today(), "id": lead_id}, "khách tiềm năng")
    lead["lich_hen"] = conn.execute(
        """SELECT lh.*, l.ma_lop FROM lich_hen lh LEFT JOIN lop_hoc l ON l.id = lh.lop_hoc_id
           WHERE lh.khach_id = %s ORDER BY lh.thoi_gian DESC""",
        (lead_id,),
    ).fetchall()
    lead["lich_su"] = conn.execute(
        """SELECT actor, hanh_dong, truoc, sau, ly_do, created_at FROM audit_log
           WHERE doi_tuong = 'khach_tiem_nang' AND doi_tuong_id = %s ORDER BY created_at DESC LIMIT 30""",
        (str(lead_id),),
    ).fetchall()
    return lead


def _pick_owner(conn) -> str | None:
    row = conn.execute(
        """SELECT u.username FROM app_user u
           LEFT JOIN khach_tiem_nang k ON k.phu_trach = u.username AND k.trang_thai IN ('moi', 'da_lien_he', 'hen_hoc_thu')
           WHERE u.role = 'consultant' AND u.active GROUP BY u.username ORDER BY count(k.id), u.username LIMIT 1"""
    ).fetchone()
    return row["username"] if row else None


def create_lead(conn, actor: Actor, data: dict) -> dict:
    require(actor, "lead.write")
    phone = "".join(ch for ch in data["so_dien_thoai"] if ch.isdigit())
    if len(phone) < 9:
        raise RuleViolation("Số điện thoại không hợp lệ.")
    dup = conn.execute(
        "SELECT id FROM khach_tiem_nang WHERE so_dien_thoai = %s AND trang_thai <> 'khong_tiep_tuc'", (phone,)
    ).fetchone()
    if dup:
        raise Conflict(f"Số điện thoại đã có ở khách #{dup['id']}.")
    owner = data.get("phu_trach") or (actor.id if actor.role == "consultant" else _pick_owner(conn))
    row = conn.execute(
        """INSERT INTO khach_tiem_nang (ho_ten, so_dien_thoai, email, nguon, nhu_cau, khoa_quan_tam_id, phu_trach,
                                       created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (
            data["ho_ten"].strip(),
            phone,
            (data.get("email") or "").strip().lower() or None,
            data["nguon"],
            data.get("nhu_cau", ""),
            data.get("khoa_quan_tam_id"),
            owner,
            now(),
            now(),
        ),
    ).fetchone()
    audit(conn, actor, "tao_khach", "khach_tiem_nang", row["id"], after={**data, "phu_trach": owner})
    emit_event(conn, "lead.created", khach_id=row["id"])
    return get_lead(conn, actor, row["id"])


def transition(conn, actor: Actor, lead_id: int, target: str, note: str = "") -> dict:
    require(actor, "lead.write")
    lead = one(conn, "SELECT * FROM khach_tiem_nang WHERE id = %s FOR UPDATE", (lead_id,), "khách tiềm năng")
    if target == "da_ghi_danh":
        raise RuleViolation("Khách chỉ chuyển sang 'đã ghi danh' khi ghi danh vào một lớp.")
    check_transition("khách", rules.LEAD_TRANSITIONS, lead["trang_thai"], target)
    if target == "khong_tiep_tuc" and not note.strip():
        raise RuleViolation("Cần ghi lý do khi ngừng theo đuổi khách.")
    contacted = target in ("da_lien_he", "hen_hoc_thu")
    conn.execute(
        """UPDATE khach_tiem_nang SET trang_thai = %s, updated_at = %s,
               lien_he_cuoi = CASE WHEN %s THEN %s ELSE lien_he_cuoi END,
               ly_do_dung = CASE WHEN %s = 'khong_tiep_tuc' THEN %s ELSE ly_do_dung END
           WHERE id = %s""",
        (target, now(), contacted, now(), target, note, lead_id),
    )
    audit(
        conn,
        actor,
        "chuyen_trang_thai_khach",
        "khach_tiem_nang",
        lead_id,
        before={"trang_thai": lead["trang_thai"]},
        after={"trang_thai": target},
        reason=note or None,
    )
    return get_lead(conn, actor, lead_id)


def log_contact(conn, actor: Actor, lead_id: int, note: str) -> dict:
    require(actor, "lead.write")
    lead = one(conn, "SELECT trang_thai FROM khach_tiem_nang WHERE id = %s FOR UPDATE", (lead_id,), "khách tiềm năng")
    if lead["trang_thai"] in ("da_ghi_danh",):
        raise RuleViolation("Khách đã ghi danh.")
    new_status = "da_lien_he" if lead["trang_thai"] in ("moi", "khong_tiep_tuc") else lead["trang_thai"]
    conn.execute(
        "UPDATE khach_tiem_nang SET lien_he_cuoi = %s, trang_thai = %s, updated_at = %s WHERE id = %s",
        (now(), new_status, now(), lead_id),
    )
    conn.execute(
        """UPDATE viec_can_lam SET trang_thai = 'xong'
           WHERE loai_doi_tuong = 'khach_tiem_nang' AND doi_tuong_id = %s AND trang_thai = 'mo'""",
        (lead_id,),
    )
    audit(conn, actor, "lien_he_khach", "khach_tiem_nang", lead_id, after={"trang_thai": new_status}, reason=note)
    return get_lead(conn, actor, lead_id)


def book_appointment(conn, actor: Actor, lead_id: int, kind: str, when: datetime, class_id: int | None = None):
    require(actor, "lead.write")
    lead = one(conn, "SELECT * FROM khach_tiem_nang WHERE id = %s FOR UPDATE", (lead_id,), "khách tiềm năng")
    if kind not in ("tu_van", "hoc_thu"):
        raise RuleViolation("Loại lịch hẹn là tu_van hoặc hoc_thu.")
    if when.date() < today():
        raise RuleViolation("Không đặt lịch hẹn trong quá khứ.")
    if kind == "hoc_thu":
        if not class_id:
            raise RuleViolation("Học thử cần chọn lớp.")
        cls = one(conn, "SELECT trang_thai FROM lop_hoc WHERE id = %s", (class_id,), "lớp học")
        if cls["trang_thai"] not in ("dang_hoc", "sap_khai_giang"):
            raise RuleViolation("Chỉ học thử ở lớp đang học hoặc sắp khai giảng.")
        if lead["trang_thai"] != "hen_hoc_thu":
            check_transition("khách", rules.LEAD_TRANSITIONS, lead["trang_thai"], "hen_hoc_thu")
    conn.execute(
        "INSERT INTO lich_hen (khach_id, loai, thoi_gian, lop_hoc_id, created_by) VALUES (%s, %s, %s, %s, %s)",
        (lead_id, kind, when, class_id, actor.id),
    )
    if kind == "hoc_thu":
        conn.execute(
            "UPDATE khach_tiem_nang SET trang_thai = 'hen_hoc_thu', lien_he_cuoi = %s, updated_at = %s WHERE id = %s",
            (now(), now(), lead_id),
        )
    audit(conn, actor, "dat_lich_hen", "khach_tiem_nang", lead_id, after={"loai": kind, "thoi_gian": when})
    return get_lead(conn, actor, lead_id)


def convert_to_student(conn, actor: Actor, lead_id: int, birth_year: int, city: str) -> dict:
    """Tạo hồ sơ học viên từ khách (trước khi ghi danh). Trả hoc_vien_id."""
    require(actor, "student.write")
    lead = one(conn, "SELECT * FROM khach_tiem_nang WHERE id = %s FOR UPDATE", (lead_id,), "khách tiềm năng")
    if lead["hoc_vien_id"]:
        return {"hoc_vien_id": lead["hoc_vien_id"]}
    if not lead["email"]:
        raise RuleViolation("Khách cần có email trước khi tạo hồ sơ học viên.")
    exists = conn.execute("SELECT id FROM hoc_vien WHERE lower(email) = lower(%s)", (lead["email"],)).fetchone()
    if exists:
        hv_id = exists["id"]
    else:
        hv_id = conn.execute(
            """INSERT INTO hoc_vien (ho_ten, email, so_dien_thoai, nam_sinh, thanh_pho, nguon, ngay_dang_ky)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (
                lead["ho_ten"],
                lead["email"],
                lead["so_dien_thoai"],
                birth_year,
                city,
                lead["nguon"] if lead["nguon"] != "walk_in" else "gioi_thieu",
                today(),
            ),
        ).fetchone()["id"]
    conn.execute("UPDATE khach_tiem_nang SET hoc_vien_id = %s WHERE id = %s", (hv_id, lead_id))
    audit(conn, actor, "tao_hoc_vien_tu_khach", "khach_tiem_nang", lead_id, after={"hoc_vien_id": hv_id})
    return {"hoc_vien_id": hv_id}


def mark_enrolled(conn, actor: Actor, lead_id: int, student_id: int) -> None:
    lead = one(conn, "SELECT trang_thai FROM khach_tiem_nang WHERE id = %s FOR UPDATE", (lead_id,), "khách tiềm năng")
    check_transition("khách", rules.LEAD_TRANSITIONS, lead["trang_thai"], "da_ghi_danh")
    conn.execute(
        "UPDATE khach_tiem_nang SET trang_thai = 'da_ghi_danh', hoc_vien_id = %s, updated_at = now() WHERE id = %s",
        (student_id, lead_id),
    )
    audit(
        conn,
        actor,
        "khach_ghi_danh",
        "khach_tiem_nang",
        lead_id,
        before={"trang_thai": lead["trang_thai"]},
        after={"trang_thai": "da_ghi_danh", "hoc_vien_id": student_id},
    )


def set_score(conn, actor: Actor, lead_id: int, score: int, reason: str) -> None:
    conn.execute("UPDATE khach_tiem_nang SET diem = %s WHERE id = %s", (score, lead_id))
    audit(conn, actor, "cham_diem_khach", "khach_tiem_nang", lead_id, after={"diem": score}, reason=reason)


def funnel(conn, actor: Actor, days: int = 30) -> list[dict]:
    require(actor, "lead.read")
    return conn.execute(
        """SELECT trang_thai, count(*)::int AS so_khach FROM khach_tiem_nang
           WHERE created_at >= %s::date - %s GROUP BY trang_thai""",
        (today(), days),
    ).fetchall()


# ---------------------------------------------------------------- việc cần làm
def create_task(
    conn,
    actor: Actor,
    title: str,
    owner: str | None,
    due: date,
    description: str = "",
    obj: tuple[str, int] | None = None,
    dedupe_key: str | None = None,
) -> int | None:
    """Trả id việc mới, hoặc None nếu đã có việc cùng khoá chống trùng."""
    row = conn.execute(
        """INSERT INTO viec_can_lam (tieu_de, mo_ta, nguoi_phu_trach, han, loai_doi_tuong, doi_tuong_id,
                                     khoa_chong_trung, created_by)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (khoa_chong_trung) DO NOTHING RETURNING id""",
        (title, description, owner, due, obj[0] if obj else None, obj[1] if obj else None, dedupe_key, actor.id),
    ).fetchone()
    return row["id"] if row else None


def list_tasks(conn, actor: Actor, mine: bool = True, status: str = "mo") -> list[dict]:
    require(actor, "task.read")
    return conn.execute(
        """SELECT v.*, k.ho_ten AS ten_khach FROM viec_can_lam v
           LEFT JOIN khach_tiem_nang k ON v.loai_doi_tuong = 'khach_tiem_nang' AND k.id = v.doi_tuong_id
           WHERE v.trang_thai = %s AND (NOT %s OR v.nguoi_phu_trach = %s)
           ORDER BY v.han, v.id LIMIT 200""",
        (status, mine, actor.id),
    ).fetchall()


def complete_task(conn, actor: Actor, task_id: int) -> None:
    require(actor, "task.read")
    task = one(conn, "SELECT * FROM viec_can_lam WHERE id = %s", (task_id,), "việc cần làm")
    if task["nguoi_phu_trach"] not in (actor.id, None) and actor.role != "manager":
        raise RuleViolation("Chỉ người phụ trách hoặc quản lý đánh dấu xong.")
    conn.execute("UPDATE viec_can_lam SET trang_thai = 'xong' WHERE id = %s", (task_id,))
    audit(conn, actor, "xong_viec", "viec_can_lam", task_id)
