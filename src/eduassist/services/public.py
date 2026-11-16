"""Dữ liệu cho web công khai (không đăng nhập).

Chỉ trả những trường được phép công khai: không có email/SĐT giảng viên, không có tên học viên, không có số liệu
tài chính. Khoá học ngừng bán và giảng viên tắt "hiện công khai" không xuất hiện.

Form đăng ký tư vấn tạo khách tiềm năng nguồn "website" -> phát sự kiện lead.created -> agent tuyển sinh chấm điểm
và soạn tin tư vấn như với khách nhập tay.
"""

import re
from functools import lru_cache
from pathlib import Path

from eduassist.services import crm, notifications, rules
from eduassist.services.core import Actor, NotFound, RuleViolation, audit, emit_event, now, one, today

WEB_FORM = Actor(id="web:form", role="consultant")  # chỉ dùng để ghi audit, không gọi hàm cần quyền
POLICY_DIR = Path(__file__).resolve().parents[3] / "data" / "policies"
PHONE_RE = re.compile(r"^(0|84)(3|5|7|8|9)\d{8}$")
ACTIVE = list(rules.ACTIVE_ENROLLMENT)

UPCOMING_SQL = """
SELECT lh.id, lh.ma_lop, lh.khoa_hoc_id, kh.slug, kh.ten AS khoa_hoc, kh.danh_muc, kh.hoc_phi,
       lh.ngay_khai_giang, lh.ca_hoc, lh.lich_hoc, lh.hinh_thuc, cs.ten AS co_so,
       CASE WHEN gv.hien_thi_cong_khai THEN gv.ho_ten END AS giang_vien,
       greatest(0, lh.si_so_toi_da - (SELECT count(*) FROM don_hang d
                                      WHERE d.lop_hoc_id = lh.id AND d.trang_thai_hoc = ANY(%(active)s)))::int AS cho_trong
FROM lop_hoc lh
JOIN khoa_hoc kh ON kh.id = lh.khoa_hoc_id
LEFT JOIN phong_hoc ph ON ph.id = lh.phong_hoc_id
LEFT JOIN co_so cs ON cs.id = ph.co_so_id
LEFT JOIN giang_vien gv ON gv.id = lh.giang_vien_id
WHERE kh.dang_mo_ban AND lh.trang_thai = 'sap_khai_giang' AND lh.ngay_khai_giang >= %(today)s
"""

COURSE_FIELDS = """kh.id, kh.slug, kh.ma, kh.ten, kh.danh_muc, kh.trinh_do, kh.hoc_phi, kh.so_buoi,
                   coalesce(kh.mo_ta_ngan, kh.mo_ta) AS mo_ta_ngan"""


def list_courses(conn, danh_muc: str | None = None, trinh_do: str | None = None) -> list[dict]:
    return conn.execute(
        f"""SELECT {COURSE_FIELDS},
                   (SELECT min(lh.ngay_khai_giang) FROM lop_hoc lh WHERE lh.khoa_hoc_id = kh.id
                      AND lh.trang_thai = 'sap_khai_giang' AND lh.ngay_khai_giang >= %(today)s) AS khai_giang_gan_nhat,
                   (SELECT count(*) FROM lop_hoc lh WHERE lh.khoa_hoc_id = kh.id
                      AND lh.trang_thai = 'sap_khai_giang' AND lh.ngay_khai_giang >= %(today)s)::int AS so_lop_sap_mo,
                   (SELECT array_agg(DISTINCT lh.hinh_thuc) FROM lop_hoc lh WHERE lh.khoa_hoc_id = kh.id
                      AND lh.trang_thai IN ('sap_khai_giang', 'dang_hoc')) AS hinh_thuc
            FROM khoa_hoc kh
            WHERE kh.dang_mo_ban AND (%(dm)s::text IS NULL OR kh.danh_muc = %(dm)s)
              AND (%(td)s::text IS NULL OR kh.trinh_do = %(td)s)
            ORDER BY kh.danh_muc, kh.hoc_phi""",
        {"today": today(), "dm": danh_muc, "td": trinh_do},
    ).fetchall()


def course_detail(conn, slug: str) -> dict:
    course = one(
        conn,
        f"""SELECT {COURSE_FIELDS}, kh.mo_ta, kh.doi_tuong, kh.ket_qua, kh.lo_trinh
            FROM khoa_hoc kh WHERE kh.slug = %s AND kh.dang_mo_ban""",
        (slug,),
        "khoá học",
    )
    course["lop_sap_mo"] = conn.execute(
        UPCOMING_SQL + " AND kh.id = %(kh)s ORDER BY lh.ngay_khai_giang",
        {"today": today(), "active": ACTIVE, "kh": course["id"]},
    ).fetchall()
    course["giang_vien"] = conn.execute(
        """SELECT DISTINCT gv.ho_ten, gv.chuyen_mon, gv.tieu_su FROM lop_hoc lh JOIN giang_vien gv ON gv.id = lh.giang_vien_id
           WHERE lh.khoa_hoc_id = %s AND gv.hien_thi_cong_khai AND lh.trang_thai IN ('sap_khai_giang', 'dang_hoc')
           ORDER BY gv.ho_ten""",
        (course["id"],),
    ).fetchall()
    course["tra_gop"] = course["hoc_phi"] >= rules.INSTALLMENT_MIN_FEE
    same = [c for c in list_courses(conn, course["danh_muc"]) if c["id"] != course["id"]]
    course["lien_quan"] = sorted(same, key=lambda c: (c["khai_giang_gan_nhat"] is None, c["hoc_phi"]))[:3]
    return course


def schedule(conn) -> list[dict]:
    return conn.execute(
        UPCOMING_SQL + " ORDER BY lh.ngay_khai_giang, kh.ten LIMIT 200", {"today": today(), "active": ACTIVE}
    ).fetchall()


def center(conn) -> dict:
    stats = conn.execute(
        """SELECT (SELECT count(*) FROM khoa_hoc WHERE dang_mo_ban)::int AS so_khoa,
                  (SELECT count(DISTINCT hoc_vien_id) FROM don_hang WHERE trang_thai_hoc <> 'da_huy')::int AS so_hoc_vien,
                  (SELECT count(*) FROM lop_hoc WHERE trang_thai <> 'da_huy')::int AS so_lop,
                  (SELECT count(*) FROM giang_vien WHERE hien_thi_cong_khai)::int AS so_giang_vien"""
    ).fetchone()
    return {
        **stats,
        "co_so": conn.execute("SELECT ten, dia_chi FROM co_so ORDER BY id").fetchall(),
        "giang_vien": conn.execute(
            "SELECT ho_ten, chuyen_mon, tieu_su FROM giang_vien WHERE hien_thi_cong_khai ORDER BY id"
        ).fetchall(),
        "danh_muc": conn.execute(
            """SELECT danh_muc, count(*)::int AS so_khoa, min(hoc_phi)::int AS hoc_phi_tu FROM khoa_hoc
               WHERE dang_mo_ban GROUP BY danh_muc ORDER BY count(*) DESC"""
        ).fetchall(),
    }


# ---------------------------------------------------------------- chính sách (đọc từ data/policies/*.md)
def _slug(stem: str) -> str:
    return re.sub(r"^\d+_", "", stem).replace("_", "-")


@lru_cache
def _policies() -> tuple[dict, ...]:
    out = []
    for f in sorted(POLICY_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        m = re.search(r"^# (.+)$", text, re.M)
        body = text[m.end() :].strip() if m else text
        sections = re.findall(r"^## (.+)$", text, re.M)
        out.append(
            {"slug": _slug(f.stem), "tieu_de": m.group(1).strip() if m else f.stem, "muc": sections, "noi_dung": body}
        )
    return tuple(out)


def policies() -> list[dict]:
    return [{k: p[k] for k in ("slug", "tieu_de", "muc")} for p in _policies()]


def policy(slug: str) -> dict:
    for p in _policies():
        if p["slug"] == slug:
            return p
    raise NotFound("Không tìm thấy chính sách.")


# ---------------------------------------------------------------- form đăng ký tư vấn
def submit_lead(conn, data: dict) -> dict:
    """data: ho_ten, so_dien_thoai, email?, khoa_slug?, nhu_cau?, dong_y, trang (trang khách đang xem).

    Trả cùng một kết quả dù là khách mới hay đã có -> không dò được số điện thoại nào đã đăng ký."""
    name = " ".join(data["ho_ten"].split())
    if not 2 <= len(name) <= 80 or any(ch.isdigit() for ch in name):
        raise RuleViolation("Họ tên chưa hợp lệ.")
    phone = re.sub(r"\D", "", data["so_dien_thoai"])
    if not PHONE_RE.match(phone):
        raise RuleViolation("Số điện thoại chưa đúng (VD: 0901 234 567).")
    phone = "0" + phone[2:] if phone.startswith("84") else phone
    email = (data.get("email") or "").strip().lower() or None
    if email and not notifications.EMAIL_RE.match(email):
        raise RuleViolation("Email chưa đúng định dạng.")
    if not data.get("dong_y"):
        raise RuleViolation("Cần đồng ý để trung tâm liên hệ tư vấn.")
    need = " ".join((data.get("nhu_cau") or "").split())[:1000]
    course_id = None
    if data.get("khoa_slug"):
        row = conn.execute("SELECT id FROM khoa_hoc WHERE slug = %s AND dang_mo_ban", (data["khoa_slug"],)).fetchone()
        course_id = row["id"] if row else None
    channel = f"form:{(data.get('trang') or '/')[:120]}"

    existing = conn.execute(
        """SELECT id, phu_trach, nhu_cau FROM khach_tiem_nang
           WHERE so_dien_thoai = %s AND trang_thai <> 'khong_tiep_tuc' ORDER BY id DESC LIMIT 1""",
        (phone,),
    ).fetchone()
    if existing:
        # Khách đăng ký lại: không tạo trùng, ghi thêm nhu cầu mới và báo người phụ trách
        if need and need not in (existing["nhu_cau"] or ""):
            conn.execute(
                "UPDATE khach_tiem_nang SET nhu_cau = left(trim(both from concat_ws(' | ', nhu_cau, %s::text)), 2000),"
                " updated_at = %s WHERE id = %s",
                (need, now(), existing["id"]),
            )
        audit(conn, WEB_FORM, "khach_dang_ky_lai", "khach_tiem_nang", existing["id"], after={"kenh": channel})
        if existing["phu_trach"]:
            notifications.notify(
                conn,
                existing["phu_trach"],
                f"{name} vừa đăng ký tư vấn lại trên website",
                need or "Khách để lại thông tin lần nữa.",
                f"/leads/{existing['id']}",
            )
        return {"ok": True}

    owner = crm._pick_owner(conn)
    row = conn.execute(
        """INSERT INTO khach_tiem_nang (ho_ten, so_dien_thoai, email, nguon, nhu_cau, khoa_quan_tam_id, phu_trach,
                                       dong_y_luc, kenh_chi_tiet, created_at, updated_at)
           VALUES (%s, %s, %s, 'website', %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (name, phone, email, need, course_id, owner, now(), channel, now(), now()),
    ).fetchone()
    audit(conn, WEB_FORM, "tao_khach", "khach_tiem_nang", row["id"], after={"nguon": "website", "kenh": channel})
    emit_event(conn, "lead.created", khach_id=row["id"])
    if owner:
        notifications.notify(
            conn, owner, f"Khách mới từ website: {name}", need or "Đăng ký tư vấn", f"/leads/{row['id']}"
        )
    return {"ok": True}
