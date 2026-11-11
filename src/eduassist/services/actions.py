"""Danh mục LOẠI THAO TÁC của agent và cách thực thi từng loại.

Mỗi loại thao tác khai báo:
- perm     : quyền cần có để DUYỆT (người duyệt) và để THỰC THI (vai trò của agent) - kiểm tra cả hai phía.
- editable : trường người duyệt được sửa trước khi duyệt (ngoài ra chỉ được BỎ BỚT mục khỏi danh sách).
- execute  : hàm thực thi, gọi CÁC HÀM CỦA TẦNG SERVICE với actor là agent -> cùng luật với nhân viên.

Thực thi dùng `du_lieu` do CODE tính lúc tạo đề xuất (đúng thứ người duyệt đã xem), và kiểm tra lại điều kiện
tại thời điểm thực thi (VD: học viên đã đóng tiền trong lúc chờ duyệt thì bỏ qua, không nhắc nữa).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from eduassist.formatting import vnd
from eduassist.services import crm, enrollment, finance, notifications, training
from eduassist.services.core import Actor, RuleViolation, today
from eduassist.services.rules import DEBT_TIER_LABEL

CENTER = "Trung tâm Đào tạo Ánh Dương"
SIGNATURE = f"\n\nTrân trọng,\n{CENTER}\nHotline 1900 0000"


@dataclass(frozen=True)
class ActionType:
    key: str
    label: str
    perm: str
    execute: Callable[..., str] | None = None
    editable: tuple[str, ...] = ()
    has_items: bool = False
    default_level: str = "L1"
    default_limit: int = 0
    description: str = ""
    item_key: str = "hoc_vien_id"
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------- mẫu email (code soạn, LLM không đụng số tiền)
def reminder_mail(item: dict, tier: str, note: str = "") -> tuple[str, str]:
    due = date.fromisoformat(str(item["han"]))
    if tier == "truoc_han_3":
        subject = "Nhắc lịch đóng học phí"
        lead = f"học phí đợt {item['so_thu_tu']} lớp {item['ma_lop']} ({vnd(item['so_tien_dot'])}) đến hạn ngày {due:%d/%m/%Y}."
    else:
        subject = "Học phí đã quá hạn - vui lòng hoàn tất"
        lead = (
            f"học phí đợt {item['so_thu_tu']} lớp {item['ma_lop']} ({vnd(item['so_tien_dot'])}) đã quá hạn từ ngày "
            f"{due:%d/%m/%Y}. Theo quy định, quá 14 ngày sau hạn học viên sẽ tạm dừng tham gia lớp cho đến khi đóng đủ."
        )
    body = (
        f"Kính gửi {item['ho_ten']},\n\n{CENTER} xin thông báo {lead}\n"
        + (f"\n{note.strip()}\n" if note.strip() else "")
        + "\nNếu bạn đã thanh toán, vui lòng bỏ qua email này."
        + SIGNATURE
    )
    return f"{CENTER} - {subject}", body


def bulk_reminder_mail(item: dict, deadline: str, note: str = "") -> tuple[str, str]:
    d = date.fromisoformat(deadline)
    body = (
        f"Kính gửi {item['ho_ten']},\n\n{CENTER} xin thông báo học phí còn lại của bạn là {vnd(item['con_no'])}.\n"
        f"Bạn vui lòng hoàn tất thanh toán trước ngày {d:%d/%m/%Y} để việc học không bị gián đoạn.\n"
        + (f"\n{note.strip()}\n" if note.strip() else "")
        + "\nNếu bạn đã thanh toán, vui lòng bỏ qua email này."
        + SIGNATURE
    )
    return f"{CENTER} - Nhắc thanh toán học phí", body


# ---------------------------------------------------------------- executors
def _still_unpaid(conn, dot_ids: list[int]) -> set[int]:
    rows = conn.execute(
        """SELECT x.id FROM dot_thanh_toan x JOIN don_hang d ON d.id = x.don_hang_id
           WHERE x.id = ANY(%s) AND x.trang_thai IN ('chua_thanh_toan', 'qua_han') AND d.trang_thai_hoc <> 'da_huy'""",
        (dot_ids,),
    ).fetchall()
    return {r["id"] for r in rows}


def exec_debt_reminder(conn, actor: Actor, data: dict, proposal_id: int) -> str:
    items = data["items"]
    unpaid = _still_unpaid(conn, [i["dot_id"] for i in items])
    todo = [i for i in items if i["dot_id"] in unpaid]
    messages = {i["hoc_vien_id"]: reminder_mail(i, i["bac"], data.get("loi_nhan_them", "")) for i in todo}
    res = notifications.send_student_emails(conn, actor, "nhac_no", messages, proposal_id)
    if res.error:
        raise RuleViolation(res.error)
    parts = [f"Đã gửi {len(res.sent)} email nhắc nợ."]
    if len(items) - len(todo):
        parts.append(f"Bỏ qua {len(items) - len(todo)} người đã đóng tiền trong lúc chờ.")
    if res.skipped_recent:
        parts.append(f"Bỏ qua {len(res.skipped_recent)} người đã được nhắc trong 24 giờ qua.")
    return " ".join(parts)


def exec_bulk_reminder(conn, actor: Actor, data: dict, proposal_id: int) -> str:
    ids = [i["hoc_vien_id"] for i in data["items"]]
    still = {
        r["hoc_vien_id"]
        for r in conn.execute(
            """SELECT DISTINCT d.hoc_vien_id FROM don_hang d WHERE d.hoc_vien_id = ANY(%s)
               AND d.trang_thai IN ('chua_thanh_toan', 'thanh_toan_mot_phan') AND d.trang_thai_hoc <> 'da_huy'""",
            (ids,),
        ).fetchall()
    }
    messages = {
        i["hoc_vien_id"]: bulk_reminder_mail(i, data["han"], data.get("loi_nhan_them", ""))
        for i in data["items"]
        if i["hoc_vien_id"] in still
    }
    res = notifications.send_student_emails(conn, actor, "nhac_no", messages, proposal_id)
    if res.error:
        raise RuleViolation(res.error)
    total = sum(i["con_no"] for i in data["items"] if i["hoc_vien_id"] in set(res.sent))
    out = f"Đã gửi {len(res.sent)} email nhắc nợ (tổng còn nợ {vnd(total)}), hạn {date.fromisoformat(data['han']):%d/%m/%Y}."
    if res.skipped_recent:
        out += f" Bỏ qua {len(res.skipped_recent)} người đã được nhắc trong 24 giờ qua."
    return out


def exec_suspend(conn, actor: Actor, data: dict, proposal_id: int) -> str:
    if not _still_unpaid(conn, [data["dot_id"]]):
        return "Không tạm dừng: học viên đã đóng đợt này trong lúc chờ duyệt."
    enrollment.suspend(conn, actor, data["don_hang_id"], f"Nợ quá hạn {data['so_ngay_qua_han']} ngày")
    subject = f"{CENTER} - Tạm dừng tham gia lớp {data['ma_lop']}"
    body = (
        f"Kính gửi {data['ho_ten']},\n\nDo học phí lớp {data['ma_lop']} đã quá hạn hơn 14 ngày, theo quy định "
        f"trung tâm tạm dừng việc tham gia lớp của bạn cho đến khi hoàn tất học phí còn lại ({vnd(data['con_no'])}). "
        "Ngay khi nhận được thanh toán, bạn sẽ được học lại bình thường." + SIGNATURE
    )
    notifications.send_student_emails(conn, actor, "tam_dung", {data["hoc_vien_id"]: (subject, body)}, proposal_id)
    return f"Đã tạm dừng ghi danh #{data['don_hang_id']} ({data['ho_ten']}, lớp {data['ma_lop']}) và gửi email báo."


def exec_email(conn, actor: Actor, data: dict, proposal_id: int) -> str:
    n = notifications.send_freeform_email(conn, actor, data["recipients"], data["subject"], data["body"], proposal_id)
    return f"Đã gửi email '{data['subject']}' tới {n} người nhận."


def exec_voucher(conn, actor: Actor, data: dict, proposal_id: int) -> str:
    v = finance.issue_voucher(
        conn, actor, data["hoc_vien_id"], int(data["phan_tram"]), data["ly_do"], int(data.get("so_ngay", 30))
    )
    return f"Đã tạo voucher {v['ma']} giảm {v['phan_tram']}% cho {v['ho_ten']}, hạn {v['han_su_dung']:%d/%m/%Y}."


def exec_lead_tasks(conn, actor: Actor, data: dict, proposal_id: int) -> str:
    created = 0
    for i in data["items"]:
        tid = crm.create_task(
            conn,
            actor,
            f"Liên hệ khách {i['ho_ten']}",
            i.get("phu_trach"),
            today(),
            i["ly_do"],
            ("khach_tiem_nang", i["khach_id"]),
            dedupe_key=f"lead-followup:{i['khach_id']}:{i['moc']}",
        )
        if tid:
            created += 1
            if i.get("phu_trach"):
                notifications.notify(
                    conn, i["phu_trach"], f"Việc mới: liên hệ {i['ho_ten']}", i["ly_do"], f"/leads/{i['khach_id']}"
                )
    return f"Đã tạo {created} việc nhắc liên hệ khách."


def exec_lead_message(conn, actor: Actor, data: dict, proposal_id: int) -> str:
    notifications.send_freeform_email(conn, actor, [data["email"]], data["subject"], data["body"], proposal_id)
    crm.log_contact(conn, actor, data["khach_id"], f"Gửi tin tư vấn (đề xuất #{proposal_id})")
    return f"Đã gửi tin tư vấn tới {data['ho_ten']} và ghi nhận lần liên hệ."


def exec_cancel_class(conn, actor: Actor, data: dict, proposal_id: int) -> str:
    r = training.cancel_class(conn, actor, data["lop_hoc_id"], data["ly_do"])
    return f"Đã huỷ lớp {data['ma_lop']}; {r['so_ghi_danh_huy']} ghi danh chuyển sang chờ hoàn phí 100%."


def exec_merge_class(conn, actor: Actor, data: dict, proposal_id: int) -> str:
    r = training.merge_class(conn, actor, data["lop_hoc_id"], data["lop_dich_id"], data["ly_do"])
    return f"Đã gộp {r['so_hoc_vien']} học viên từ lớp {r['tu_lop']} sang {r['sang_lop']}."


def exec_care_message(conn, actor: Actor, data: dict, proposal_id: int) -> str:
    res = notifications.send_student_emails(
        conn, actor, "hoi_tham", {data["hoc_vien_id"]: (data["subject"], data["body"])}, proposal_id
    )
    if data.get("giang_vien_username"):
        notifications.notify(
            conn,
            data["giang_vien_username"],
            f"Học viên {data['ho_ten']} vắng {data['so_buoi_vang_lien_tiep']} buổi liên tiếp",
            f"Lớp {data['ma_lop']}. Trung tâm đã gửi tin hỏi thăm. Chuyên cần hiện tại {data['chuyen_can']:.0%}.",
            f"/classes/{data['lop_hoc_id']}",
        )
    if not res.sent:
        return "Không gửi: học viên đã nhận tin hỏi thăm trong 24 giờ qua. Đã báo giảng viên."
    return f"Đã gửi tin hỏi thăm tới {data['ho_ten']} và báo giảng viên."


def exec_weekly_report(conn, actor: Actor, data: dict, proposal_id: int) -> str:
    notifications.notify(conn, "role:manager", data["tieu_de"], data["noi_dung"], f"/inbox?id={proposal_id}")
    return "Đã gửi báo cáo tuần cho quản lý."


# ---------------------------------------------------------------- danh mục
ACTIONS: dict[str, ActionType] = {
    a.key: a
    for a in [
        ActionType(
            "nhac_no_lan_dau",
            "Nhắc học phí lần đầu",
            "email.send",
            exec_debt_reminder,
            ("loi_nhan_them",),
            True,
            "L2",
            100,
            "Email nhắc học phí lần đầu (trước hạn 3 ngày, hoặc lần đầu khi đã quá hạn).",
            item_key="dot_id",
        ),
        ActionType(
            "nhac_no_tiep",
            "Nhắc nợ lần 2 trở đi",
            "email.send",
            exec_debt_reminder,
            ("loi_nhan_them",),
            True,
            "L1",
            0,
            "Nhắc nợ khi quá hạn 1 / 7 ngày mà đã từng được nhắc.",
            item_key="dot_id",
        ),
        ActionType(
            "tam_dung_hoc",
            "Tạm dừng học do nợ quá hạn",
            "enroll.suspend",
            exec_suspend,
            (),
            False,
            "L1",
            0,
            "Quá hạn 14 ngày: tạm dừng tham gia lớp đến khi đóng đủ.",
        ),
        ActionType(
            "nhac_no_hang_loat",
            "Nhắc nợ hàng loạt (qua chat)",
            "email.send",
            exec_bulk_reminder,
            ("loi_nhan_them",),
            True,
            "L1",
            0,
            "Nhắc mọi học viên đang nợ, theo lệnh trong chat.",
        ),
        ActionType(
            "gui_email",
            "Gửi email nội dung tự do",
            "email.send",
            exec_email,
            ("subject", "body"),
            False,
            "L1",
            0,
            "Email do agent soạn theo yêu cầu.",
        ),
        ActionType(
            "cap_voucher",
            "Cấp voucher",
            "voucher.issue",
            exec_voucher,
            ("phan_tram", "so_ngay"),
            False,
            "L1",
            0,
            "Cấp mã giảm giá; hạn mức % theo vai trò.",
        ),
        ActionType(
            "tao_viec_nhac",
            "Tạo việc nhắc tư vấn viên",
            "lead.write",
            exec_lead_tasks,
            (),
            True,
            "L2",
            200,
            "Khách quá 3 ngày chưa liên hệ / lâu chưa theo đuổi -> giao việc cho người phụ trách.",
            item_key="khach_id",
        ),
        ActionType(
            "gui_tin_tu_van",
            "Gửi tin tư vấn cho khách",
            "lead.write",
            exec_lead_message,
            ("subject", "body"),
            False,
            "L1",
            0,
            "Tin tư vấn cá nhân hoá, kèm lớp phù hợp đang mở.",
        ),
        ActionType(
            "canh_bao_lop_thieu",
            "Cảnh báo lớp thiếu sĩ số",
            "class.read",
            None,
            (),
            False,
            "L0",
            0,
            "Lớp sắp khai giảng chưa đạt sĩ số tối thiểu.",
        ),
        ActionType(
            "de_xuat_huy_lop",
            "Huỷ lớp không đủ sĩ số",
            "class.write",
            exec_cancel_class,
            (),
            False,
            "L1",
            0,
            "Sát ngày khai giảng vẫn thiếu sĩ số, không có lớp để gộp.",
        ),
        ActionType(
            "de_xuat_gop_lop",
            "Gộp lớp thiếu sĩ số",
            "class.write",
            exec_merge_class,
            (),
            False,
            "L1",
            0,
            "Gộp vào lớp cùng khoá còn chỗ.",
        ),
        ActionType(
            "canh_bao_trung_lich",
            "Cảnh báo trùng lịch",
            "class.read",
            None,
            (),
            False,
            "L0",
            0,
            "Giảng viên hoặc phòng bị xếp trùng lịch.",
        ),
        ActionType(
            "hoi_tham_hoc_vien",
            "Hỏi thăm học viên có nguy cơ bỏ học",
            "email.send",
            exec_care_message,
            ("subject", "body"),
            False,
            "L1",
            0,
            "Vắng liên tiếp / chuyên cần thấp / điểm giảm.",
        ),
        ActionType(
            "bao_cao_tuan",
            "Báo cáo tuần cho quản lý",
            "report.read",
            exec_weekly_report,
            (),
            False,
            "L2",
            1,
            "Tổng hợp doanh thu, công nợ, tuyển sinh và điểm bất thường.",
        ),
        # Mức Cấm: không có hàm thực thi - không agent nào làm được, kể cả khi quản lý đổi cấu hình
        ActionType(
            "ghi_nhan_thanh_toan",
            "Ghi nhận đã thu tiền",
            "payment.record",
            None,
            (),
            False,
            "cam",
            0,
            "Chỉ kế toán (con người) ghi nhận.",
        ),
        ActionType("sua_diem", "Sửa điểm", "grade.write", None, (), False, "cam", 0, "Chỉ giảng viên / giáo vụ."),
        ActionType("xoa_du_lieu", "Xoá dữ liệu", "data.delete", None, (), False, "cam", 0, "Không bao giờ."),
        ActionType("doi_quyen", "Đổi quyền người dùng", "user.admin", None, (), False, "cam", 0, "Chỉ quản lý."),
    ]
}
FORBIDDEN_FOREVER = {k for k, a in ACTIONS.items() if a.default_level == "cam"}


def apply_edits(action: ActionType, data: dict, edits: dict) -> dict:
    """Người duyệt sửa đề xuất: chỉ trường trong `editable`, hoặc bỏ bớt mục (keep_items) khỏi danh sách."""
    new = dict(data)
    for k, v in edits.items():
        if k == "keep_items":
            if not action.has_items:
                raise RuleViolation("Đề xuất này không có danh sách để bỏ bớt.")
            keep = set(v)
            new["items"] = [i for i in data["items"] if i[action.item_key] in keep]
            if not new["items"]:
                raise RuleViolation("Phải giữ lại ít nhất một mục; muốn bỏ hết thì bấm Từ chối.")
        elif k in action.editable:
            new[k] = v
        else:
            raise RuleViolation(f"Không được sửa trường '{k}' của đề xuất này.")
    return new


__all__ = ["ACTIONS", "DEBT_TIER_LABEL", "FORBIDDEN_FOREVER", "ActionType", "apply_edits", "reminder_mail"]
