"""Action agent (Vận hành): thực hiện thao tác theo lệnh trong chat - gửi email, cấp voucher, nhắc nợ hàng loạt.

Tool KHÔNG tự ghi dữ liệu: mỗi tool tạo một ĐỀ XUẤT qua tầng Service (proposals.submit). Mức tự chủ của loại thao
tác quyết định đề xuất chờ duyệt (L1, mặc định) hay tự thực thi trong hạn mức (L2). Người dùng duyệt ngay trên
khung chat hoặc trong Hộp duyệt; khi thực thi, đề xuất gọi đúng hàm nghiệp vụ với vai trò của người ra lệnh,
có cờ is_agent nên chịu cả danh sách Cấm. Dữ liệu hiện cho người duyệt (người nhận, số tiền) do code tính.
"""

from datetime import datetime, timedelta

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware, dynamic_prompt
from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from eduassist.agents.context import UserContext, emit
from eduassist.db import app_pool
from eduassist.formatting import vnd
from eduassist.llm import chat_model, resilience_middleware
from eduassist.services import notifications, proposals
from eduassist.services.core import VOUCHER_MAX_PERCENT, Actor, ServiceError, today

MAX_RECIPIENTS = notifications.MAX_FREEFORM_RECIPIENTS
MAX_REMINDERS = notifications.MAX_TEMPLATED_BATCH

PROMPT = """Bạn là thư ký vận hành của Trung tâm Đào tạo Ánh Dương. Hôm nay là {today}.
Bạn thực hiện thao tác theo yêu cầu của nhân viên:
- send_payment_reminders: NHẮC NỢ HỌC PHÍ - luôn dùng tool này (không dùng send_email) khi được yêu cầu nhắc nợ.
  Hệ thống tự tính công nợ, tự điền tên + số tiền vào từng email; bạn chỉ truyền hạn thanh toán và (nếu được
  chỉ định) danh sách hoc_vien_id. Không chỉ định ai -> bỏ trống để gửi cho TẤT CẢ học viên đang nợ.
  Không được nêu hạn thanh toán -> dùng ngày {default_deadline}.
- get_student_contacts: kiểm tra họ tên học viên theo hoc_vien_id và học viên đã có email chưa.
- send_email: gửi email. Chỉ định người nhận bằng hoc_vien_ids / khach_ids, hệ thống tự điền địa chỉ (bạn không
  thấy địa chỉ email - đó là chủ ý bảo vệ dữ liệu cá nhân). Chỉ dùng tham số emails cho địa chỉ người dùng tự gõ.
  Viết tiếng Việt lịch sự, xưng "Trung tâm", ký tên "Trung tâm Đào tạo Ánh Dương".
  Mỗi học viên một email riêng nếu nội dung có thông tin cá nhân (VD: số tiền nợ của từng người).
- create_voucher: cấp mã giảm giá cho một học viên.
Đủ thông tin thì GỌI TOOL NGAY. Gọi tool chỉ TẠO ĐỀ XUẤT: hệ thống tự hiện nút Duyệt / Từ chối cho người dùng,
nên TUYỆT ĐỐI không hỏi "bạn có muốn gửi không" bằng lời. Mỗi việc chỉ gọi tool MỘT lần.
Chỉ hỏi lại khi THIẾU thông tin bắt buộc (không có người nhận, không rõ mức giảm) - không tự đoán.
Cuối cùng tóm tắt ngắn: đã tạo đề xuất số mấy, đang chờ duyệt hay đã tự thực hiện."""


def _actor(ctx: UserContext) -> Actor:
    # Hành động do LLM khởi xướng -> is_agent: chịu danh sách Cấm dù người ra lệnh là quản lý
    return Actor(id=ctx.user_id, role=ctx.role, is_agent=True)


def _submit(ctx: UserContext, action_type: str, title: str, summary: str, data: dict, evidence=None) -> str:
    try:
        with app_pool().connection() as conn, conn.transaction():
            p = proposals.submit(conn, _actor(ctx), action_type, title, summary, data, evidence)
    except ServiceError as e:
        return f"LỖI: {e.message} Chưa có thao tác nào được thực hiện."
    emit("proposal", id=p["id"], status=p["trang_thai"], title=title)
    if p["trang_thai"] == "da_thuc_hien":
        return f"ĐÃ TỰ THỰC HIỆN (trong hạn mức L2) - đề xuất #{p['id']}: {p['ket_qua']}"
    if p["trang_thai"] == "that_bai":
        return f"THẤT BẠI - đề xuất #{p['id']}: {p['ket_qua']}"
    return f"ĐÃ TẠO ĐỀ XUẤT #{p['id']} ({title}) - đang chờ người có quyền duyệt. Chưa thực hiện."


def parse_deadline(text: str):
    """Nhận '15/12/2026' hoặc '2026-12-15'. Hạn phải trong 1..60 ngày tới."""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            d = datetime.strptime(text.strip(), fmt).date()
            break
        except ValueError:
            continue
    else:
        raise ValueError("hạn thanh toán phải có dạng dd/mm/yyyy")
    if not today() < d <= today() + timedelta(days=60):
        raise ValueError("hạn thanh toán phải trong vòng 60 ngày tới")
    return d


DEBTORS_SQL = """
WITH paid AS (SELECT don_hang_id, SUM(so_tien) AS tong FROM thanh_toan GROUP BY don_hang_id)
SELECT hv.id AS hoc_vien_id, hv.ho_ten, SUM(dh.thanh_tien - COALESCE(p.tong, 0))::bigint AS con_no
FROM don_hang dh
JOIN hoc_vien hv ON hv.id = dh.hoc_vien_id
LEFT JOIN paid p ON p.don_hang_id = dh.id
WHERE dh.trang_thai IN ('chua_thanh_toan', 'thanh_toan_mot_phan') AND dh.trang_thai_hoc <> 'da_huy'
  AND dh.thanh_tien - COALESCE(p.tong, 0) > 0
  AND (%(ids)s::int[] IS NULL OR hv.id = ANY(%(ids)s::int[]))
GROUP BY hv.id, hv.ho_ten
ORDER BY con_no DESC, hv.id
"""


def find_debtors(conn, hoc_vien_ids: list[int] | None = None) -> list[dict]:
    """Công nợ tính bằng code (không phải SQL do LLM viết): phải thu - đã thu, chỉ các đơn còn hiệu lực."""
    return conn.execute(DEBTORS_SQL, {"ids": hoc_vien_ids or None}).fetchall()


@tool
def send_payment_reminders(
    han_thanh_toan: str,
    runtime: ToolRuntime[UserContext],
    hoc_vien_ids: list[int] | None = None,
    loi_nhan_them: str = "",
) -> str:
    """Nhắc nợ học phí: MỖI HỌC VIÊN MỘT EMAIL với đúng tên và số tiền còn nợ (hệ thống tự tính).
    han_thanh_toan: dd/mm/yyyy. hoc_vien_ids: bỏ trống = tất cả học viên đang nợ. Tạo đề xuất chờ duyệt."""
    try:
        deadline = parse_deadline(han_thanh_toan)
    except ValueError as e:
        return f"LỖI: {e}. Chưa có email nào được gửi."
    with app_pool().connection() as conn:
        debtors = find_debtors(conn, hoc_vien_ids)
        recent = notifications.recently_sent(conn, "nhac_no", [d["hoc_vien_id"] for d in debtors])
    targets = [d for d in debtors if d["hoc_vien_id"] not in recent]
    skip = f" Bỏ qua {len(recent)} người đã được nhắc trong 24 giờ qua." if recent else ""
    if not targets:
        return "Không cần nhắc ai: không có học viên đang nợ cần nhắc." + skip
    if len(targets) > MAX_REMINDERS:
        return f"LỖI: {len(targets)} người nhận vượt giới hạn {MAX_REMINDERS}. Chưa có email nào được gửi."
    total = sum(d["con_no"] for d in targets)
    items = [{"hoc_vien_id": d["hoc_vien_id"], "ho_ten": d["ho_ten"], "con_no": d["con_no"]} for d in targets]
    return _submit(
        runtime.context,
        "nhac_no_hang_loat",
        f"Nhắc nợ {len(targets)} học viên ({vnd(total)}), hạn {deadline:%d/%m/%Y}",
        "Email theo mẫu, mỗi người một email với đúng số tiền còn nợ." + skip,
        {"items": items, "han": deadline.isoformat(), "loi_nhan_them": loi_nhan_them},
        [f"{d['ho_ten']} (id {d['hoc_vien_id']}): còn nợ {vnd(d['con_no'])}" for d in targets[:50]],
    )


@tool
def get_student_contacts(hoc_vien_ids: list[int]) -> str:
    """Kiểm tra học viên theo id: họ tên và đã có email chưa (địa chỉ email không hiện ra, hệ thống tự điền)."""
    with app_pool().connection() as conn:
        rows = conn.execute(
            "SELECT id, ho_ten, email FROM hoc_vien WHERE id = ANY(%s) ORDER BY id", (hoc_vien_ids[:MAX_RECIPIENTS],)
        ).fetchall()
    return (
        "\n".join(f"- id {r['id']}: {r['ho_ten']} ({'có email' if r['email'] else 'CHƯA có email'})" for r in rows)
        or "Không tìm thấy học viên nào."
    )


def resolve_recipients(
    conn, hoc_vien_ids: list[int], khach_ids: list[int], emails: list[str]
) -> tuple[list[str], list[str]]:
    """(địa chỉ email lấy từ DB, lỗi). Email LLM tự gõ chỉ chấp nhận nếu thuộc học viên / khách trong hệ thống."""
    errors: list[str] = []
    found: list[str] = []
    if hoc_vien_ids:
        rows = conn.execute("SELECT id, email FROM hoc_vien WHERE id = ANY(%s)", (hoc_vien_ids,)).fetchall()
        by_id = {r["id"]: r["email"] for r in rows}
        missing = [i for i in hoc_vien_ids if not by_id.get(i)]
        if missing:
            errors.append(f"học viên id {', '.join(map(str, missing))} không có hoặc chưa có email")
        found += [by_id[i] for i in hoc_vien_ids if by_id.get(i)]
    if khach_ids:
        rows = conn.execute("SELECT id, email FROM khach_tiem_nang WHERE id = ANY(%s)", (khach_ids,)).fetchall()
        by_id = {r["id"]: r["email"] for r in rows}
        missing = [i for i in khach_ids if not by_id.get(i)]
        if missing:
            errors.append(f"khách id {', '.join(map(str, missing))} không có hoặc chưa có email")
        found += [by_id[i] for i in khach_ids if by_id.get(i)]
    if emails:
        typed = [e.strip().lower() for e in emails]
        known = {
            r["email"]
            for r in conn.execute(
                """SELECT lower(email) AS email FROM hoc_vien WHERE lower(email) = ANY(%(e)s)
                   UNION SELECT lower(email) FROM khach_tiem_nang WHERE lower(email) = ANY(%(e)s)""",
                {"e": typed},
            ).fetchall()
        }
        unknown = [e for e in typed if e not in known]
        if unknown:
            errors.append(f"không phải email của học viên/khách trong hệ thống: {', '.join(unknown)}")
        found += [e for e in typed if e in known]
    unique = list(dict.fromkeys(e.strip().lower() for e in found))
    return unique, errors


@tool
def send_email(
    subject: str,
    body: str,
    runtime: ToolRuntime[UserContext],
    hoc_vien_ids: list[int] | None = None,
    khach_ids: list[int] | None = None,
    emails: list[str] | None = None,
) -> str:
    """Gửi MỘT email (tối đa 50 người nhận). Chỉ định người nhận bằng hoc_vien_ids và/hoặc khach_ids (id khách
    tiềm năng) - hệ thống tự lấy địa chỉ email. emails: chỉ dùng cho địa chỉ người dùng tự gõ trong yêu cầu.
    Tạo đề xuất chờ duyệt."""
    with app_pool().connection() as conn:
        recipients, errors = resolve_recipients(conn, hoc_vien_ids or [], khach_ids or [], emails or [])
    if errors:  # báo LLM ngay để nó tự sửa (tầng Service cũng kiểm tra lại lúc thực thi)
        return f"LỖI: {'; '.join(errors)}. Chưa có email nào được gửi."
    if not 1 <= len(recipients) <= MAX_RECIPIENTS:
        return f"LỖI: số người nhận phải từ 1 đến {MAX_RECIPIENTS}."
    return _submit(
        runtime.context,
        "gui_email",
        f"Gửi email: {subject[:80]}",
        f"Tới {len(recipients)} người nhận. Nội dung do AI soạn theo yêu cầu - kiểm tra trước khi duyệt.",
        {"recipients": recipients, "subject": subject, "body": body},
        [f"Người nhận: {', '.join(recipients[:10])}" + ("…" if len(recipients) > 10 else "")],
    )


@tool
def create_voucher(
    hoc_vien_id: int, phan_tram: int, ly_do: str, runtime: ToolRuntime[UserContext], so_ngay_hieu_luc: int = 30
) -> str:
    """Cấp mã giảm giá cho một học viên. phan_tram là % giảm học phí. Tạo đề xuất chờ duyệt."""
    limit = VOUCHER_MAX_PERCENT.get(runtime.context.role, 0)
    if not 1 <= phan_tram <= limit:
        return f"LỖI: vai trò {runtime.context.role} chỉ được cấp voucher từ 1% đến {limit}%."
    with app_pool().connection() as conn:
        student = conn.execute("SELECT ho_ten FROM hoc_vien WHERE id = %s", (hoc_vien_id,)).fetchone()
    if student is None:
        return f"LỖI: không có học viên id {hoc_vien_id}."
    return _submit(
        runtime.context,
        "cap_voucher",
        f"Cấp voucher {phan_tram}% cho {student['ho_ten']}",
        f"Lý do: {ly_do}. Hiệu lực {so_ngay_hieu_luc} ngày.",
        {
            "hoc_vien_id": hoc_vien_id,
            "ho_ten": student["ho_ten"],
            "phan_tram": phan_tram,
            "ly_do": ly_do,
            "so_ngay": so_ngay_hieu_luc,
        },
        [f"Học viên id {hoc_vien_id}: {student['ho_ten']}", f"Hạn mức vai trò: tối đa {limit}%"],
    )


@dynamic_prompt
def action_prompt(request) -> str:
    return PROMPT.format(today=today(), default_deadline=f"{today() + timedelta(days=7):%d/%m/%Y}")


def build_action_agent():
    return create_agent(
        chat_model(),
        tools=[send_payment_reminders, get_student_contacts, send_email, create_voucher],
        context_schema=UserContext,
        middleware=[action_prompt, *resilience_middleware(), ToolCallLimitMiddleware(run_limit=8)],
        name="action",
    )
