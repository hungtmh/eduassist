"""Đánh giá agent chạy nền bằng MÔ PHỎNG N NGÀY (mục 10-11 của đề xuất) - không gọi LLM, không gửi email thật.

Toàn bộ mô phỏng chạy trong MỘT transaction rồi rollback: database không đổi sau khi chạy.
Mỗi ngày mô phỏng:
  1. Thế giới thay đổi: một phần học viên đóng tiền; giảng viên điểm danh các buổi trong ngày (có học viên được cài
     sẵn vắng liên tiếp); khách tiềm năng mới để lại thông tin.
  2. Worker chạy: outbox sự kiện + các agent đến lịch.
  3. Người duyệt giả lập: duyệt mọi đề xuất chờ duyệt (để chuỗi nhắc nợ đi tiếp được các bậc).
  4. Chấm: đáp án của ngày được tính TRỰC TIẾP từ dữ liệu bằng SQL riêng (không gọi code của agent), so với
     các đề xuất agent đã tạo.

Chỉ số:
  - recall      : tỉ lệ ca cần xử lý có đề xuất tương ứng (mục tiêu: không bỏ sót ca quá hạn)
  - precision   : tỉ lệ mục trong đề xuất là đúng tại thời điểm đề xuất (đúng người, đúng bậc, còn nợ)
  - trùng       : số học viên nhận >1 email cùng loại trong 24 giờ (phải = 0)
  - nhắc người đã đóng: email nhắc nợ gửi cho đợt đã đóng tại thời điểm gửi (phải = 0)
"""

import random
from contextlib import contextmanager
from datetime import date, timedelta

from psycopg.rows import dict_row

from eduassist.background.runner import process_outbox, run_due
from eduassist.config import get_settings
from eduassist.services import crm, enrollment, finance, proposals
from eduassist.services.core import Actor, ServiceError, business_date
from eduassist.services.notifications import _capture, capture_mail

ACCOUNTANT = Actor("ketoan", "accountant")
APPROVER = Actor("quanly", "manager")
CLEAN_AGENT_STATE = (
    "TRUNCATE de_xuat_agent, lan_chay_agent, outbox_su_kien, thong_bao, viec_can_lam, audit_log, email_log"
    " RESTART IDENTITY CASCADE"
)

TIER_DAYS = {"truoc_han_3": -3, "qua_han_1": 1, "qua_han_7": 7, "tam_dung": 14}


@contextmanager
def _sandbox():
    import psycopg

    s = get_settings()
    s.background_llm = False  # đánh giá logic agent, không phụ thuộc LLM
    box: list = []
    token = capture_mail(box)
    try:
        with (
            psycopg.connect(s.database_url, row_factory=dict_row, autocommit=True) as conn,
            conn.transaction(force_rollback=True),
        ):
            # Bắt đầu từ trạng thái agent sạch (trong transaction sẽ rollback - DB thật không đổi)
            conn.execute(CLEAN_AGENT_STATE)
            yield conn, box
    finally:
        _capture.reset(token)


def _expected_debt(conn, d: date) -> set[tuple[int, str]]:
    """Đáp án độc lập: với mỗi đợt còn nợ của ghi danh còn hiệu lực, bậc CAO NHẤT đã chạm tới hôm nay
    (ngày đầu mô phỏng: bắt kịp các đợt đã quá hạn từ trước; các ngày sau: đúng ngày chạm bậc mới)."""
    rows = conn.execute(
        """SELECT x.id, x.han_thanh_toan, d.trang_thai_hoc, d.ngay_dat FROM dot_thanh_toan x
           JOIN don_hang d ON d.id = x.don_hang_id
           WHERE x.trang_thai IN ('chua_thanh_toan', 'qua_han')
             AND d.trang_thai_hoc IN ('cho_thanh_toan', 'dang_hoc', 'tam_dung')"""
    ).fetchall()
    out = set()
    for r in rows:
        days = (d - r["han_thanh_toan"]).days
        reached = [t for t, threshold in TIER_DAYS.items() if days >= threshold]
        if not reached:
            continue
        tier = reached[-1]
        if tier == "tam_dung" and r["trang_thai_hoc"] != "dang_hoc":
            continue
        if tier == "truoc_han_3" and r["ngay_dat"] >= d - timedelta(days=1):
            continue
        out.add((r["id"], tier))
    return out


def _proposed_debt(conn) -> dict[tuple[int, str], date]:
    got: dict[tuple[int, str], date] = {}
    for p in conn.execute(
        """SELECT loai_hanh_dong, du_lieu, ngay_nghiep_vu FROM de_xuat_agent
           WHERE agent = 'cong_no' AND loai_hanh_dong IN ('nhac_no_lan_dau', 'nhac_no_tiep', 'tam_dung_hoc')"""
    ).fetchall():
        if p["loai_hanh_dong"] == "tam_dung_hoc":
            got.setdefault((p["du_lieu"]["dot_id"], "tam_dung"), p["ngay_nghiep_vu"])
        else:
            for i in p["du_lieu"]["items"]:
                got.setdefault((i["dot_id"], i["bac"]), p["ngay_nghiep_vu"])
    return got


def _mark_today_sessions(conn, d: date, rnd: random.Random, truants: set[int]) -> int:
    marked = 0
    for s in conn.execute(
        """SELECT b.id, l.giang_vien_id FROM buoi_hoc b JOIN lop_hoc l ON l.id = b.lop_hoc_id
           WHERE b.ngay = %s AND l.trang_thai = 'dang_hoc' AND b.trang_thai = 'du_kien'""",
        (d,),
    ).fetchall():
        teacher = Actor("giangvien-sim", "teacher", giang_vien_id=s["giang_vien_id"])
        roster = enrollment.session_roster(conn, Actor("giaovu", "academic"), s["id"])["hoc_vien"]
        entries = [
            {
                "don_hang_id": r["don_hang_id"],
                "trang_thai": "vang" if r["don_hang_id"] in truants else ("vang" if rnd.random() < 0.03 else "co_mat"),
            }
            for r in roster
        ]
        if entries:
            enrollment.mark_attendance(conn, teacher, s["id"], entries)
            marked += 1
    return marked


def _expected_care(conn) -> set[int]:
    """Ghi danh đang học có >= 2 buổi vắng (không phép) liên tiếp gần nhất - SQL độc lập với agent."""
    rows = conn.execute(
        """WITH h AS (
             SELECT dd.don_hang_id, dd.trang_thai,
                    row_number() OVER (PARTITION BY dd.don_hang_id ORDER BY b.ngay DESC) AS rn
             FROM diem_danh dd JOIN buoi_hoc b ON b.id = dd.buoi_hoc_id)
           SELECT h.don_hang_id FROM h JOIN don_hang d ON d.id = h.don_hang_id
           JOIN lop_hoc l ON l.id = d.lop_hoc_id
           WHERE h.rn <= 2 AND d.trang_thai_hoc = 'dang_hoc' AND l.trang_thai = 'dang_hoc'
           GROUP BY h.don_hang_id HAVING count(*) FILTER (WHERE h.trang_thai = 'vang') = 2"""
    ).fetchall()
    return {r["don_hang_id"] for r in rows}


def _expected_underfilled(conn, d: date) -> set[int]:
    rows = conn.execute(
        """SELECT l.id FROM lop_hoc l WHERE l.trang_thai = 'sap_khai_giang'
             AND l.ngay_khai_giang - %s BETWEEN 0 AND 14
             AND (SELECT count(*) FROM don_hang x WHERE x.lop_hoc_id = l.id
                  AND x.trang_thai_hoc IN ('cho_thanh_toan', 'dang_hoc', 'tam_dung')) < l.si_so_toi_thieu""",
        (d,),
    ).fetchall()
    return {r["id"] for r in rows}


def _expected_stale_leads(conn, d: date) -> set[int]:
    rows = conn.execute(
        """SELECT id FROM khach_tiem_nang WHERE trang_thai = 'moi' AND lien_he_cuoi IS NULL
             AND created_at::date <= %s - 3""",
        (d,),
    ).fetchall()
    return {r["id"] for r in rows}


def simulate(days: int = 30, seed: int = 11, verbose: bool = True) -> tuple[list[dict], dict]:
    rnd = random.Random(seed)
    start = date.today()
    rows: list[dict] = []
    debt_expected: dict[tuple[int, str], date] = {}
    care_expected: set[int] = set()
    class_expected: set[int] = set()
    lead_expected: set[int] = set()
    errors = 0
    paid_reminded = 0
    with _sandbox() as (conn, mails):
        active = [
            r["id"]
            for r in conn.execute(
                "SELECT d.id FROM don_hang d JOIN lop_hoc l ON l.id = d.lop_hoc_id"
                " WHERE d.trang_thai_hoc = 'dang_hoc' AND l.trang_thai = 'dang_hoc' ORDER BY d.id"
            ).fetchall()
        ]
        truants = set(rnd.sample(active, min(5, len(active))))  # kịch bản: 5 học viên bỏ học từ ngày 3
        sent_log: list[tuple[date, str, str]] = []
        for k in range(days):
            d = start + timedelta(days=k)
            with business_date(d):
                # 1. thế giới thay đổi
                paid_today = 0
                for inst in finance.open_installments(conn):
                    if rnd.random() < 0.06:  # ~6% đợt còn nợ được đóng mỗi ngày
                        try:
                            with conn.transaction():
                                finance.record_payment(
                                    conn, ACCOUNTANT, inst["don_hang_id"], inst["so_tien"], "chuyen_khoan", "mô phỏng"
                                )
                            paid_today += 1
                        except ServiceError:
                            pass
                _mark_today_sessions(conn, d, rnd, truants if k >= 3 else set())
                if rnd.random() < 0.7:
                    try:
                        with conn.transaction():
                            crm.create_lead(
                                conn,
                                Actor("tuvan", "consultant"),
                                {
                                    "ho_ten": f"Khách mô phỏng {k}",
                                    "so_dien_thoai": f"0977{k:06d}",
                                    "nguon": "website",
                                    "email": f"sim.lead{k}@example.com",
                                    "nhu_cau": "Muốn học IELTS buổi tối",
                                },
                            )
                    except ServiceError:
                        pass
                # 2. worker
                exp_today = _expected_debt(conn, d)
                n_before = len(mails)
                try:
                    process_outbox(conn=conn)
                    run_due(conn=conn)
                except Exception as e:  # lỗi agent = ngày thất bại, vẫn chạy tiếp để thấy hết
                    errors += 1
                    if verbose:
                        print(f"  ❌ ngày {d}: {e}")
                for m in mails[n_before:]:
                    sent_log.append((d, m.to, m.subject))
                    if "học phí" in m.subject.lower():
                        still_owes = conn.execute(
                            """SELECT 1 FROM dot_thanh_toan x JOIN don_hang dh ON dh.id = x.don_hang_id
                               JOIN hoc_vien hv ON hv.id = dh.hoc_vien_id
                               WHERE hv.email = %s AND x.trang_thai IN ('chua_thanh_toan', 'qua_han') LIMIT 1""",
                            (m.to,),
                        ).fetchone()
                        paid_reminded += still_owes is None
                for key in exp_today:
                    debt_expected.setdefault(key, d)
                care_expected |= _expected_care(conn)
                class_expected |= _expected_underfilled(conn, d)
                lead_expected |= _expected_stale_leads(conn, d)
                # 3. người duyệt
                pending = [p["id"] for p in proposals.list_proposals(conn, APPROVER, "cho_duyet", limit=500)]
                proposals.bulk_decide(conn, APPROVER, pending, True)
                if verbose:
                    print(
                        f"  ngày {k + 1:2d} {d}: {len(exp_today):3d} ca nợ tới bậc · {paid_today:2d} đợt được đóng · "
                        f"{len(pending):2d} đề xuất được duyệt · {len(mails) - n_before:3d} email"
                    )

        # 4. chấm
        got = _proposed_debt(conn)
        hit = [k for k in debt_expected if k in got]
        missed = [k for k in debt_expected if k not in got]
        late = [k for k in hit if got[k] > debt_expected[k]]
        wrong = [k for k, day in got.items() if k not in debt_expected and day >= start]
        care_got = {
            p["du_lieu"]["don_hang_id"]
            for p in conn.execute(
                "SELECT du_lieu FROM de_xuat_agent WHERE loai_hanh_dong = 'hoi_tham_hoc_vien'"
            ).fetchall()
        }
        class_got = {
            p["du_lieu"]["lop_hoc_id"]
            for p in conn.execute(
                """SELECT du_lieu FROM de_xuat_agent
               WHERE loai_hanh_dong IN ('canh_bao_lop_thieu', 'de_xuat_huy_lop', 'de_xuat_gop_lop')"""
            ).fetchall()
        }
        lead_got = {
            i["khach_id"]
            for p in conn.execute("SELECT du_lieu FROM de_xuat_agent WHERE loai_hanh_dong = 'tao_viec_nhac'").fetchall()
            for i in p["du_lieu"]["items"]
        }
        # email nhắc nợ: không ai nhận 2 lần trong 24 giờ; không ai bị nhắc khi đã đóng
        dup = 0
        seen: dict[tuple[str, str], date] = {}
        for day, to, subject in sent_log:
            kind = "nhac_no" if "học phí" in subject.lower() else subject
            if (to, kind) in seen and seen[(to, kind)] == day:
                dup += 1
            seen[(to, kind)] = day
        runs_failed = conn.execute("SELECT count(*) AS n FROM lan_chay_agent WHERE trang_thai = 'loi'").fetchone()["n"]
        stats = proposals.stats(conn, APPROVER, 365)

    def rate(a, b):
        return round(a / b, 3) if b else None

    for k in missed[:20]:
        rows.append(
            {"id": f"no-{k[0]}-{k[1]}", "ok": False, "detail": f"bỏ sót đợt {k[0]} bậc {k[1]} ngày {debt_expected[k]}"}
        )
    for k in wrong[:20]:
        rows.append(
            {"id": f"sai-{k[0]}-{k[1]}", "ok": False, "detail": f"đề xuất không có trong đáp án: đợt {k[0]} bậc {k[1]}"}
        )
    summary = {
        "days": days,
        "debt_cases": len(debt_expected),
        "debt_recall": rate(len(hit), len(debt_expected)),
        "debt_on_time": rate(len(hit) - len(late), len(debt_expected)),
        "debt_precision": rate(len(hit), len(hit) + len(wrong)),
        "care_cases": len(care_expected),
        "care_recall": rate(len(care_expected & care_got), len(care_expected)),
        "class_cases": len(class_expected),
        "class_recall": rate(len(class_expected & class_got), len(class_expected)),
        "lead_cases": len(lead_expected),
        "lead_recall": rate(len(lead_expected & lead_got), len(lead_expected)),
        "duplicate_emails_24h": dup,
        "reminders_after_paid": paid_reminded,
        "agent_run_errors": runs_failed + errors,
        "emails_sent": len(sent_log),
        "proposals": sum(s["tong"] for s in stats),
        "auto_executed": sum(s["tu_dong"] for s in stats),
    }
    return rows, summary
