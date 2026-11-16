"""Phân hệ 4 - Tài chính: hoá đơn (don_hang), đợt thanh toán, ghi nhận thanh toán, công nợ, hoàn phí, voucher.

Luật: ghi nhận đã thu tiền chỉ con người làm (agent bị cấm); không thu quá số còn nợ; đợt chưa đóng quá hạn
chuyển sang 'qua_han' và phát sự kiện; hoàn phí theo tỉ lệ code tính và phải được kế toán duyệt;
voucher có hạn mức % theo vai trò.
"""

import secrets
from datetime import timedelta

from eduassist.formatting import vnd
from eduassist.services.core import (
    VOUCHER_MAX_PERCENT,
    Actor,
    Forbidden,
    Page,
    RuleViolation,
    audit,
    emit_event,
    one,
    require,
    today,
)

# Số đã đóng / hạn gần nhất tính theo từng đơn bằng LATERAL (tra index theo don_hang_id): chỉ tính cho các dòng
# thật sự trả về. Trước đây danh sách tính cho MỌI đơn rồi mới lấy 50 dòng - với 50.000 đơn mất khoảng 230 ms.
INVOICE_SQL = (
    """
SELECT d.id, d.hoc_vien_id, hv.ho_ten, hv.email, hv.so_dien_thoai, lh.ma_lop, kh.ten AS khoa_hoc,
       d.ngay_dat, d.hoc_phi_goc, d.giam_gia, d.thanh_tien, d.trang_thai, d.trang_thai_hoc, d.tra_gop,
       coalesce(p.da_dong, 0)::int AS da_dong,
       (d.thanh_tien - coalesce(p.da_dong, 0))::int AS con_no,
       x.han_gan_nhat, x.so_dot_qua_han::int AS so_dot_qua_han
FROM don_hang d
JOIN hoc_vien hv ON hv.id = d.hoc_vien_id
JOIN lop_hoc lh ON lh.id = d.lop_hoc_id
JOIN khoa_hoc kh ON kh.id = lh.khoa_hoc_id
LEFT JOIN LATERAL (SELECT sum(so_tien) AS da_dong FROM thanh_toan t WHERE t.don_hang_id = d.id) p ON true
"""
    + """LEFT JOIN LATERAL (SELECT min(han_thanh_toan) FILTER (WHERE trang_thai IN ('chua_thanh_toan', 'qua_han')) AS han_gan_nhat,
                          count(*) FILTER (WHERE trang_thai = 'qua_han') AS so_dot_qua_han
                   FROM dot_thanh_toan x WHERE x.don_hang_id = d.id) x ON true
"""
)

# Hạn gần nhất của mọi đơn, gộp một lần (bảng đợt trả góp nhỏ): dùng để SẮP XẾP danh sách mà không phải ghép đủ cột
DUE_SQL = """(SELECT don_hang_id, min(han_thanh_toan) AS han_gan_nhat FROM dot_thanh_toan
              WHERE trang_thai IN ('chua_thanh_toan', 'qua_han') GROUP BY don_hang_id)"""


def list_invoices(
    conn,
    actor: Actor,
    status: str | None = None,
    q: str | None = None,
    overdue: bool = False,
    limit: int = 200,
    offset: int = 0,
) -> Page:
    """Ba bước nhẹ thay cho một truy vấn nặng: đếm tổng, lấy id của trang (chỉ cần cột để lọc / sắp xếp), rồi mới
    lấy đủ cột cho đúng các id đó. Cùng kết quả và thứ tự như trước (hạn gần nhất, rồi đơn mới trước)."""
    require(actor, "invoice.read")
    where, params = ["true"], {}
    if status == "con_no":
        where.append("d.trang_thai IN ('chua_thanh_toan', 'thanh_toan_mot_phan') AND d.trang_thai_hoc <> 'da_huy'")
    elif status:
        where.append("d.trang_thai = %(st)s")
        params["st"] = status
    if overdue:
        where.append("EXISTS (SELECT 1 FROM dot_thanh_toan x WHERE x.don_hang_id = d.id AND x.trang_thai = 'qua_han')")
    joins = ""
    if q:
        joins = " JOIN hoc_vien hv ON hv.id = d.hoc_vien_id JOIN lop_hoc lh ON lh.id = d.lop_hoc_id"
        where.append("(hv.ho_ten ILIKE %(q)s OR lh.ma_lop ILIKE %(q)s OR hv.email ILIKE %(q)s)")
        params["q"] = f"%{q}%"
    cond = " WHERE " + " AND ".join(where)
    total = conn.execute("SELECT count(*) AS n FROM don_hang d" + joins + cond, params).fetchone()["n"]
    ids = [
        r["id"]
        for r in conn.execute(
            f"SELECT d.id FROM don_hang d{joins} LEFT JOIN {DUE_SQL} due ON due.don_hang_id = d.id{cond}"
            " ORDER BY due.han_gan_nhat NULLS LAST, d.id DESC LIMIT %(_limit)s OFFSET %(_offset)s",
            {**params, "_limit": max(1, int(limit)), "_offset": max(0, int(offset))},
        ).fetchall()
    ]
    rows = {r["id"]: r for r in conn.execute(INVOICE_SQL + " WHERE d.id = ANY(%s)", (ids,)).fetchall()}
    return Page([rows[i] for i in ids], total)


def get_invoice(conn, actor: Actor, invoice_id: int) -> dict:
    inv = one(conn, INVOICE_SQL + " WHERE d.id = %s", (invoice_id,), "hoá đơn")
    if actor.role == "student":
        if inv["hoc_vien_id"] != actor.hoc_vien_id:
            raise Forbidden("Bạn chỉ xem được hoá đơn của mình.")
    else:
        require(actor, "invoice.read")
    inv["dot"] = conn.execute(
        """SELECT x.id, x.so_thu_tu, x.so_tien, coalesce(c.con_lai, 0) AS con_lai, x.han_thanh_toan, x.trang_thai
           FROM dot_thanh_toan x LEFT JOIN dot_con_lai c ON c.id = x.id WHERE x.don_hang_id = %s
           ORDER BY x.so_thu_tu""",
        (invoice_id,),
    ).fetchall()
    inv["thanh_toan"] = conn.execute(
        "SELECT id, ngay_thanh_toan, so_tien, phuong_thuc, ghi_chu, created_by FROM thanh_toan WHERE don_hang_id = %s"
        " ORDER BY ngay_thanh_toan, id",
        (invoice_id,),
    ).fetchall()
    inv["hoan_phi"] = conn.execute(
        "SELECT * FROM hoan_phi WHERE don_hang_id = %s ORDER BY id DESC", (invoice_id,)
    ).fetchall()
    return inv


def _apply_to_installments(conn, invoice_id: int, total_paid: int) -> None:
    """Đợt nào được tổng tiền đã đóng phủ kín thì chuyển 'da_thanh_toan' (phân bổ theo thứ tự đợt)."""
    acc = 0
    for dot in conn.execute(
        "SELECT id, so_tien, trang_thai FROM dot_thanh_toan WHERE don_hang_id = %s AND trang_thai <> 'da_huy'"
        " ORDER BY so_thu_tu",
        (invoice_id,),
    ).fetchall():
        acc += dot["so_tien"]
        if total_paid >= acc and dot["trang_thai"] != "da_thanh_toan":
            conn.execute("UPDATE dot_thanh_toan SET trang_thai = 'da_thanh_toan' WHERE id = %s", (dot["id"],))


def record_payment(conn, actor: Actor, invoice_id: int, amount: int, method: str, note: str | None = None) -> dict:
    """CHỈ CON NGƯỜI: payment.record nằm trong AGENT_FORBIDDEN - agent không thể tự báo 'đã thu tiền'."""
    require(actor, "payment.record")
    if method not in ("chuyen_khoan", "tien_mat", "the"):
        raise RuleViolation("Phương thức thanh toán là chuyen_khoan, tien_mat hoặc the.")
    inv = one(conn, INVOICE_SQL + " WHERE d.id = %s", (invoice_id,), "hoá đơn")
    conn.execute("SELECT id FROM don_hang WHERE id = %s FOR UPDATE", (invoice_id,))
    if inv["trang_thai_hoc"] == "da_huy":
        raise RuleViolation("Ghi danh đã huỷ, không thu tiền.")
    if amount <= 0:
        raise RuleViolation("Số tiền phải lớn hơn 0.")
    if amount > inv["con_no"]:
        raise RuleViolation(f"Số tiền {vnd(amount)} vượt số còn nợ {vnd(inv['con_no'])}.")
    conn.execute(
        """INSERT INTO thanh_toan (don_hang_id, ngay_thanh_toan, so_tien, phuong_thuc, ghi_chu, created_by)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (invoice_id, today(), amount, method, note, actor.id),
    )
    paid = inv["da_dong"] + amount
    _apply_to_installments(conn, invoice_id, paid)
    new_status = "da_thanh_toan" if paid >= inv["thanh_tien"] else "thanh_toan_mot_phan"
    conn.execute("UPDATE don_hang SET trang_thai = %s WHERE id = %s", (new_status, invoice_id))
    # Ghi danh chờ thanh toán -> đang học khi đã đóng đợt 1; tạm dừng -> đang học khi hết đợt quá hạn
    open_overdue = conn.execute(
        "SELECT count(*) AS n FROM dot_thanh_toan WHERE don_hang_id = %s AND trang_thai = 'qua_han'", (invoice_id,)
    ).fetchone()["n"]
    first_paid = conn.execute(
        "SELECT trang_thai = 'da_thanh_toan' AS ok FROM dot_thanh_toan WHERE don_hang_id = %s AND so_thu_tu = 1",
        (invoice_id,),
    ).fetchone()
    if (inv["trang_thai_hoc"] == "cho_thanh_toan" and first_paid and first_paid["ok"]) or (
        inv["trang_thai_hoc"] == "tam_dung" and open_overdue == 0
    ):
        conn.execute("UPDATE don_hang SET trang_thai_hoc = 'dang_hoc' WHERE id = %s", (invoice_id,))
    audit(
        conn,
        actor,
        "ghi_nhan_thanh_toan",
        "don_hang",
        invoice_id,
        before={"da_dong": inv["da_dong"], "trang_thai": inv["trang_thai"]},
        after={"so_tien": amount, "phuong_thuc": method, "trang_thai": new_status},
    )
    emit_event(conn, "payment.recorded", don_hang_id=invoice_id, so_tien=amount)
    return get_invoice(conn, actor, invoice_id)


def mark_overdue(conn, actor: Actor) -> list[dict]:
    """Chạy hằng ngày: đợt chưa đóng đã qua hạn -> 'qua_han' + sự kiện invoice.overdue (kích hoạt agent công nợ)."""
    rows = conn.execute(
        """UPDATE dot_thanh_toan x SET trang_thai = 'qua_han'
           FROM don_hang d WHERE d.id = x.don_hang_id AND x.trang_thai = 'chua_thanh_toan'
             AND x.han_thanh_toan < %s AND d.trang_thai_hoc <> 'da_huy'
           RETURNING x.id, x.don_hang_id, x.han_thanh_toan""",
        (today(),),
    ).fetchall()
    for r in rows:
        emit_event(conn, "invoice.overdue", dot_id=r["id"], don_hang_id=r["don_hang_id"], han=r["han_thanh_toan"])
    if rows:
        audit(conn, actor, "danh_dau_qua_han", "dot_thanh_toan", None, after={"so_dot": len(rows)})
    return rows


def open_installments(conn) -> list[dict]:
    """Mọi đợt chưa đóng của ghi danh còn hiệu lực - đầu vào của agent công nợ."""
    return conn.execute(
        """SELECT x.id AS dot_id, x.don_hang_id, x.so_thu_tu, c.con_lai AS so_tien, x.so_tien AS so_tien_goc,
                  x.han_thanh_toan, x.trang_thai,
                  d.hoc_vien_id, d.trang_thai_hoc, d.ngay_dat, hv.ho_ten, hv.email, lh.ma_lop, kh.ten AS khoa_hoc,
                  (d.thanh_tien - coalesce((SELECT sum(so_tien) FROM thanh_toan t WHERE t.don_hang_id = d.id), 0))::int
                      AS con_no
           FROM dot_thanh_toan x JOIN dot_con_lai c ON c.id = x.id JOIN don_hang d ON d.id = x.don_hang_id
           JOIN hoc_vien hv ON hv.id = d.hoc_vien_id JOIN lop_hoc lh ON lh.id = d.lop_hoc_id
           JOIN khoa_hoc kh ON kh.id = lh.khoa_hoc_id
           WHERE x.trang_thai IN ('chua_thanh_toan', 'qua_han') AND c.con_lai > 0
             AND d.trang_thai_hoc IN ('cho_thanh_toan', 'dang_hoc', 'tam_dung')
           ORDER BY x.han_thanh_toan, x.id"""
    ).fetchall()


def debt_summary(conn, actor: Actor) -> dict:
    require(actor, "invoice.read")
    return conn.execute(
        """SELECT coalesce(sum(c.con_lai) FILTER (WHERE x.trang_thai = 'qua_han'), 0)::bigint AS qua_han,
                  count(DISTINCT d.hoc_vien_id) FILTER (WHERE x.trang_thai = 'qua_han')::int AS hoc_vien_qua_han,
                  coalesce(sum(c.con_lai) FILTER (WHERE x.trang_thai = 'chua_thanh_toan'
                       AND x.han_thanh_toan <= %s + 7), 0)::bigint AS sap_toi_han_7_ngay
           FROM dot_thanh_toan x JOIN dot_con_lai c ON c.id = x.id JOIN don_hang d ON d.id = x.don_hang_id
           WHERE x.trang_thai IN ('chua_thanh_toan', 'qua_han') AND d.trang_thai_hoc <> 'da_huy'""",
        (today(),),
    ).fetchone()


# ---------------------------------------------------------------- hoàn phí
def list_refunds(conn, actor: Actor, status: str | None = "cho_duyet") -> list[dict]:
    require(actor, "invoice.read")
    return conn.execute(
        """SELECT hp.*, hv.ho_ten, lh.ma_lop FROM hoan_phi hp JOIN don_hang d ON d.id = hp.don_hang_id
           JOIN hoc_vien hv ON hv.id = d.hoc_vien_id JOIN lop_hoc lh ON lh.id = d.lop_hoc_id
           WHERE (%s::text IS NULL OR hp.trang_thai = %s) ORDER BY hp.created_at DESC""",
        (status, status),
    ).fetchall()


def decide_refund(conn, actor: Actor, refund_id: int, approve: bool) -> dict:
    require(actor, "refund.handle")
    hp = one(conn, "SELECT * FROM hoan_phi WHERE id = %s FOR UPDATE", (refund_id,), "yêu cầu hoàn phí")
    if hp["trang_thai"] != "cho_duyet":
        raise RuleViolation("Yêu cầu hoàn phí này đã được xử lý.")
    if hp["created_by"] == actor.id and actor.role != "manager":
        raise RuleViolation("Người lập yêu cầu hoàn phí không tự duyệt được (cần người thứ hai).")
    status = "da_duyet" if approve else "tu_choi"
    conn.execute("UPDATE hoan_phi SET trang_thai = %s, approved_by = %s WHERE id = %s", (status, actor.id, refund_id))
    if approve and hp["so_tien"] > 0:
        conn.execute(
            """INSERT INTO thanh_toan (don_hang_id, ngay_thanh_toan, so_tien, phuong_thuc, ghi_chu, created_by)
               VALUES (%s, %s, %s, 'chuyen_khoan', %s, %s)""",
            (hp["don_hang_id"], today(), -hp["so_tien"], f"Hoàn phí #{refund_id}", actor.id),
        )
        conn.execute("UPDATE don_hang SET trang_thai = 'da_hoan_tien' WHERE id = %s", (hp["don_hang_id"],))
    elif approve:
        conn.execute("UPDATE don_hang SET trang_thai = 'da_huy' WHERE id = %s", (hp["don_hang_id"],))
    audit(conn, actor, "duyet_hoan_phi" if approve else "tu_choi_hoan_phi", "hoan_phi", refund_id, after=dict(hp))
    return {"id": refund_id, "trang_thai": status}


# ---------------------------------------------------------------- voucher
def issue_voucher(conn, actor: Actor, student_id: int, percent: int, reason: str, days: int = 30) -> dict:
    require(actor, "voucher.issue")
    limit = VOUCHER_MAX_PERCENT.get(actor.role, 0)
    if not 1 <= percent <= limit:
        raise RuleViolation(f"Vai trò này chỉ được cấp voucher từ 1% đến {limit}%.")
    if not 1 <= days <= 90:
        raise RuleViolation("Hiệu lực voucher từ 1 đến 90 ngày.")
    if not reason.strip():
        raise RuleViolation("Cần ghi lý do cấp voucher.")
    student = one(conn, "SELECT id, ho_ten FROM hoc_vien WHERE id = %s", (student_id,), f"học viên id {student_id}")
    code = "AD-" + secrets.token_hex(3).upper()
    expires = today() + timedelta(days=days)
    row = conn.execute(
        """INSERT INTO voucher (ma, hoc_vien_id, phan_tram, ly_do, han_su_dung, created_by)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (code, student_id, percent, reason, expires, actor.id),
    ).fetchone()
    audit(
        conn,
        actor,
        "cap_voucher",
        "voucher",
        row["id"],
        after={"ma": code, "hoc_vien_id": student_id, "phan_tram": percent},
    )
    return {
        "id": row["id"],
        "ma": code,
        "hoc_vien_id": student_id,
        "ho_ten": student["ho_ten"],
        "phan_tram": percent,
        "han_su_dung": expires,
    }
