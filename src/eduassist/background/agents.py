"""Năm agent chạy nền của đề xuất (mục 6.4): công nợ, tuyển sinh, giáo vụ, chăm sóc, báo cáo.

Mẫu chung: SQL/code LỌC và TÍNH (ai, bao nhiêu tiền, căn cứ nào) -> LLM chỉ soạn lời văn khi cần ->
proposals.submit (mức tự chủ quyết định tự làm hay chờ duyệt). Chống trùng ở hai mức: khoá của đề xuất
và kiểm tra từng mục đã nằm trong đề xuất nào chưa.
"""

from datetime import timedelta

from eduassist.background.base import AgentRun, BackgroundAgent, draft_text
from eduassist.formatting import vnd
from eduassist.services import crm, finance, proposals, reports, rules, training
from eduassist.services.core import SYSTEM, today

REMINDER_TYPES = ["nhac_no_lan_dau", "nhac_no_tiep"]


# =====================================================================
# 1. CÔNG NỢ - lịch hằng ngày (tự đánh dấu quá hạn rồi xét từng đợt)
# =====================================================================
def run_debt(conn, run: AgentRun, event=None) -> str:
    marked = finance.mark_overdue(conn, SYSTEM)
    t = today()
    groups: dict[str, list[dict]] = {"nhac_no_lan_dau": [], "nhac_no_tiep": []}
    suspends = 0
    for inst in finance.open_installments(conn):
        tier = rules.debt_tier(inst["han_thanh_toan"], t)
        if tier is None:
            continue
        overdue_days = (t - inst["han_thanh_toan"]).days
        if tier == "tam_dung":
            if inst["trang_thai_hoc"] != "dang_hoc":
                continue
            p = run.submit(
                "tam_dung_hoc",
                f"Tạm dừng {inst['ho_ten']} - lớp {inst['ma_lop']} (quá hạn {overdue_days} ngày)",
                f"Đợt {inst['so_thu_tu']} ({vnd(inst['so_tien'])}) quá hạn {overdue_days} ngày. Theo chính sách trả góp,"
                " quá 14 ngày sau hạn thì tạm dừng tham gia lớp đến khi đóng đủ.",
                {
                    "dot_id": inst["dot_id"],
                    "don_hang_id": inst["don_hang_id"],
                    "hoc_vien_id": inst["hoc_vien_id"],
                    "ho_ten": inst["ho_ten"],
                    "ma_lop": inst["ma_lop"],
                    "han": inst["han_thanh_toan"],
                    "so_ngay_qua_han": overdue_days,
                    "con_no": inst["con_no"],
                },
                evidence=[_inst_evidence(inst, overdue_days), "Chính sách: 02_hoc_phi_va_uu_dai.md › Trả góp học phí"],
                dedupe_key=f"tam_dung:{inst['dot_id']}",
            )
            suspends += p is not None
            continue
        if tier == "truoc_han_3" and inst["ngay_dat"] >= t - timedelta(days=1):
            continue  # vừa ghi danh hôm qua/hôm nay: chưa cần nhắc
        if proposals.item_already_proposed(conn, REMINDER_TYPES, {"dot_id": inst["dot_id"], "bac": tier}):
            continue
        reminded_before = proposals.item_already_proposed(conn, REMINDER_TYPES, {"dot_id": inst["dot_id"]})
        groups["nhac_no_tiep" if reminded_before else "nhac_no_lan_dau"].append(
            {
                "dot_id": inst["dot_id"],
                "bac": tier,
                "hoc_vien_id": inst["hoc_vien_id"],
                "don_hang_id": inst["don_hang_id"],
                "ho_ten": inst["ho_ten"],
                "ma_lop": inst["ma_lop"],
                "so_thu_tu": inst["so_thu_tu"],
                "so_tien_dot": inst["so_tien"],
                "con_no": inst["con_no"],
                "han": inst["han_thanh_toan"],
                "so_ngay_qua_han": overdue_days,
            }
        )
    for action, items in groups.items():
        if not items:
            continue
        by_tier: dict[str, int] = {}
        for i in items:
            by_tier[rules.DEBT_TIER_LABEL[i["bac"]]] = by_tier.get(rules.DEBT_TIER_LABEL[i["bac"]], 0) + 1
        total = sum(i["so_tien_dot"] for i in items)
        label = "lần đầu" if action == "nhac_no_lan_dau" else "lần tiếp theo"
        run.submit(
            action,
            f"Nhắc học phí {label}: {len(items)} học viên ({vnd(total)})",
            "Email theo mẫu, mỗi người một email với đúng số tiền của đợt. Phân theo bậc: "
            + ", ".join(f"{v} {k}" for k, v in by_tier.items())
            + ".",
            {"items": items, "loi_nhan_them": ""},
            evidence=[_inst_evidence(i, i["so_ngay_qua_han"]) for i in items[:50]],
            dedupe_key=f"{action}:{today()}",
        )
    n_items = sum(len(v) for v in groups.values())
    return f"Đánh dấu {len(marked)} đợt quá hạn; {n_items} mục nhắc nợ; {suspends} đề xuất tạm dừng."


def _inst_evidence(inst: dict, overdue_days: int) -> str:
    when = f"quá hạn {overdue_days} ngày" if overdue_days > 0 else f"còn {-overdue_days} ngày tới hạn"
    return (
        f"{inst['ho_ten']} · lớp {inst['ma_lop']} · đợt {inst['so_thu_tu']} {vnd(inst.get('so_tien') or inst['so_tien_dot'])}"
        f" · hạn {inst.get('han_thanh_toan') or inst['han']:%d/%m/%Y} ({when})"
    )


# =====================================================================
# 2. TUYỂN SINH - sự kiện lead.created + lịch hằng ngày
# =====================================================================
LEAD_SYSTEM = (
    "Bạn là tư vấn viên của Trung tâm Đào tạo Ánh Dương. Viết MỘT đoạn mở đầu email tư vấn (3-4 câu, tiếng Việt, "
    "thân thiện, xưng 'Trung tâm', gọi khách là 'anh/chị') dựa trên nhu cầu của khách. KHÔNG nêu học phí, ngày, "
    "con số hay chính sách - phần thông tin lớp sẽ được hệ thống tự ghép bên dưới. Không chào kết, không ký tên."
)


def _suggest_classes(conn, lead: dict) -> list[dict]:
    rows = conn.execute(
        """SELECT lh.id, lh.ma_lop, kh.ten AS khoa_hoc, kh.hoc_phi, lh.ngay_khai_giang, lh.ca_hoc, lh.lich_hoc,
                  lh.hinh_thuc, lh.si_so_toi_da - (SELECT count(*) FROM don_hang d WHERE d.lop_hoc_id = lh.id
                      AND d.trang_thai_hoc IN ('cho_thanh_toan', 'dang_hoc', 'tam_dung')) AS cho_trong
           FROM lop_hoc lh JOIN khoa_hoc kh ON kh.id = lh.khoa_hoc_id
           WHERE lh.trang_thai = 'sap_khai_giang' AND lh.ngay_khai_giang > %(today)s
             AND (kh.id = %(kh)s OR (%(kh)s::int IS NULL AND %(kw)s::text IS NOT NULL
                                     AND (kh.ten ILIKE %(kw)s OR kh.mo_ta ILIKE %(kw)s)))
           ORDER BY lh.ngay_khai_giang LIMIT 6""",
        {"today": today(), "kh": lead["khoa_quan_tam_id"], "kw": f"%{kw}%" if (kw := _keyword(lead)) else None},
    ).fetchall()
    want_evening = "tối" in (lead["nhu_cau"] or "").lower()
    rows = [r for r in rows if r["cho_trong"] > 0]
    rows.sort(key=lambda r: (want_evening and r["ca_hoc"] != "toi", r["ngay_khai_giang"]))
    return rows[:2]


def _keyword(lead: dict) -> str | None:
    need = (lead["nhu_cau"] or "").lower()
    for kw in (
        "ielts",
        "toeic",
        "excel",
        "python",
        "power bi",
        "sql",
        "giao tiếp",
        "lớp 10",
        "java",
        "front-end",
        "thuyết trình",
        "phỏng vấn",
    ):
        if kw in need:
            return kw
    return None


SHIFT = {"sang": "sáng", "chieu": "chiều", "toi": "tối"}


def lead_message(lead: dict, classes: list[dict]) -> tuple[str, str, bool]:
    info = "\n".join(
        f"- {c['khoa_hoc']} - lớp {c['ma_lop']}: khai giảng {c['ngay_khai_giang']:%d/%m/%Y}, ca {SHIFT[c['ca_hoc']]} "
        f"({c['lich_hoc']}), {c['hinh_thuc']}, học phí {vnd(c['hoc_phi'])}, còn {c['cho_trong']} chỗ"
        for c in classes
    )
    fallback = (
        f"Trung tâm cảm ơn anh/chị {lead['ho_ten']} đã quan tâm. Dựa trên nhu cầu anh/chị chia sẻ, trung tâm xin "
        "gợi ý các lớp phù hợp sắp khai giảng dưới đây. Anh/chị có thể đăng ký học thử miễn phí 1 buổi trước khi quyết định."
    )
    opening, used = draft_text(
        LEAD_SYSTEM, f"Tên khách: {lead['ho_ten']}\nNhu cầu: {lead['nhu_cau'] or '(không ghi)'}", fallback, 600
    )
    body = (
        f"Kính gửi anh/chị {lead['ho_ten']},\n\n{opening}\n\nLớp phù hợp đang mở:\n{info}\n\n"
        "Anh/chị trả lời email này hoặc gọi hotline 1900 0000 để giữ chỗ / đặt lịch học thử.\n\n"
        "Trân trọng,\nTrung tâm Đào tạo Ánh Dương"
    )
    return "Trung tâm Ánh Dương - Gợi ý lớp học phù hợp với anh/chị", body, used


def _process_lead(conn, run: AgentRun, lead: dict) -> None:
    t = today()
    age = (t - lead["created_at"].date()).days
    score = rules.lead_score(
        lead["nguon"],
        bool(lead["khoa_quan_tam_id"]),
        lead["nhu_cau"] or "",
        bool(lead["email"]),
        age,
        lead["trang_thai"],
    )
    if lead["diem"] != score:
        crm.set_score(conn, run.actor, lead["id"], score, "Chấm theo nguồn khách, mức cụ thể của nhu cầu, độ mới")
    if lead["trang_thai"] != "moi" or not lead["email"]:
        return
    classes = _suggest_classes(conn, lead)
    if not classes:
        return
    subject, body, used_llm = lead_message(lead, classes)
    run.submit(
        "gui_tin_tu_van",
        f"Gửi tin tư vấn cho {lead['ho_ten']} (điểm {score})",
        f"Khách mới từ {lead['nguon']}; gợi ý {len(classes)} lớp còn chỗ."
        + (" Đoạn mở đầu do AI soạn." if used_llm else " Nội dung theo mẫu."),
        {
            "khach_id": lead["id"],
            "ho_ten": lead["ho_ten"],
            "email": lead["email"],
            "subject": subject,
            "body": body,
            "lop_goi_y": [c["ma_lop"] for c in classes],
        },
        evidence=[f"Nhu cầu: {lead['nhu_cau'] or '(không ghi)'}", f"Điểm tiềm năng {score}/100"]
        + [f"Lớp {c['ma_lop']} còn {c['cho_trong']} chỗ, khai giảng {c['ngay_khai_giang']:%d/%m/%Y}" for c in classes],
        dedupe_key=f"tu_van:{lead['id']}",
    )


def run_leads(conn, run: AgentRun, event=None) -> str:
    t = today()
    if event and event.get("khach_id"):
        lead = conn.execute("SELECT * FROM khach_tiem_nang WHERE id = %s", (event["khach_id"],)).fetchone()
        if lead:
            _process_lead(conn, run, lead)
        return f"Xử lý khách mới #{event['khach_id']}."
    for lead in conn.execute(
        "SELECT * FROM khach_tiem_nang WHERE trang_thai IN ('moi', 'da_lien_he', 'hen_hoc_thu')"
    ).fetchall():
        _process_lead(conn, run, lead)
    # Việc nhắc: khách mới quá 3 ngày chưa liên hệ; khách đang theo đuổi quá 7 ngày không có liên hệ mới
    items = []
    for lead in conn.execute(
        """SELECT id, ho_ten, phu_trach, trang_thai, created_at, lien_he_cuoi FROM khach_tiem_nang
           WHERE (trang_thai = 'moi' AND lien_he_cuoi IS NULL AND created_at::date <= %s - %s)
              OR (trang_thai IN ('da_lien_he', 'hen_hoc_thu') AND lien_he_cuoi::date <= %s - 7)
           ORDER BY created_at""",
        (t, rules.LEAD_STALE_DAYS, t),
    ).fetchall():
        if lead["trang_thai"] == "moi":
            mark = "moi_3_ngay"
            why = f"Khách mới từ {(t - lead['created_at'].date()).days} ngày trước, chưa được liên hệ (quá 3 ngày)."
        else:
            mark = f"theo_duoi:{lead['lien_he_cuoi'].date()}"
            why = f"Lần liên hệ cuối {lead['lien_he_cuoi']:%d/%m/%Y}, đã quá 7 ngày."
        item = {"khach_id": lead["id"], "moc": mark}
        if proposals.item_already_proposed(conn, ["tao_viec_nhac"], item):
            continue
        items.append({**item, "ho_ten": lead["ho_ten"], "phu_trach": lead["phu_trach"], "ly_do": why})
    if items:
        run.submit(
            "tao_viec_nhac",
            f"Nhắc tư vấn viên liên hệ {len(items)} khách",
            "Tạo việc cần làm cho người phụ trách từng khách.",
            {"items": items},
            evidence=[f"{i['ho_ten']}: {i['ly_do']}" for i in items[:50]],
            dedupe_key=f"tao_viec_nhac:{t}",
        )
    return f"Chấm điểm khách đang theo đuổi; {len(items)} khách cần nhắc liên hệ."


# =====================================================================
# 3. GIÁO VỤ - lịch hằng ngày + sự kiện class.schedule_changed
# =====================================================================
def run_academic(conn, run: AgentRun, event=None) -> str:
    t = today()
    alerts = 0
    if not event:
        for cls in training.list_classes(conn, run.actor, status="sap_khai_giang"):
            days = (cls["ngay_khai_giang"] - t).days
            if days > 14 or cls["si_so"] >= cls["si_so_toi_thieu"]:
                continue
            evidence = [
                f"Lớp {cls['ma_lop']}: {cls['si_so']}/{cls['si_so_toi_thieu']} học viên tối thiểu, "
                f"khai giảng {cls['ngay_khai_giang']:%d/%m/%Y} (còn {days} ngày)"
            ]
            if days > 7:
                p = run.submit(
                    "canh_bao_lop_thieu",
                    f"Lớp {cls['ma_lop']} mới {cls['si_so']}/{cls['si_so_toi_thieu']} học viên",
                    f"Còn {days} ngày tới khai giảng. Tư vấn viên nên ưu tiên giới thiệu lớp này.",
                    {
                        "lop_hoc_id": cls["id"],
                        "ma_lop": cls["ma_lop"],
                        "si_so": cls["si_so"],
                        "toi_thieu": cls["si_so_toi_thieu"],
                    },
                    evidence=evidence,
                    dedupe_key=f"thieu:{cls['id']}",
                )
                alerts += p is not None
                continue
            target = _merge_target(conn, run, cls)
            if target:
                run.submit(
                    "de_xuat_gop_lop",
                    f"Gộp lớp {cls['ma_lop']} vào {target['ma_lop']}",
                    f"Còn {days} ngày tới khai giảng mà mới {cls['si_so']}/{cls['si_so_toi_thieu']} học viên. Lớp "
                    f"{target['ma_lop']} cùng khoá còn {target['si_so_toi_da'] - target['si_so']} chỗ.",
                    {
                        "lop_hoc_id": cls["id"],
                        "ma_lop": cls["ma_lop"],
                        "lop_dich_id": target["id"],
                        "lop_dich": target["ma_lop"],
                        "so_hoc_vien": cls["si_so"],
                        "ly_do": f"Không đủ sĩ số tối thiểu ({cls['si_so']}/{cls['si_so_toi_thieu']})",
                    },
                    evidence=evidence
                    + [
                        f"Lớp đích {target['ma_lop']}: {target['si_so']}/{target['si_so_toi_da']}, "
                        f"ca {target['ca_hoc']} {target['lich_hoc']}, khai giảng "
                        f"{target['ngay_khai_giang']:%d/%m/%Y}"
                    ],
                    dedupe_key=f"xu_ly_lop_thieu:{cls['id']}",
                )
            else:
                run.submit(
                    "de_xuat_huy_lop",
                    f"Huỷ lớp {cls['ma_lop']} (không đủ sĩ số)",
                    f"Còn {days} ngày tới khai giảng, mới {cls['si_so']}/{cls['si_so_toi_thieu']} học viên và không "
                    "có lớp cùng khoá để gộp. Học viên được hoàn 100% học phí đã đóng (cần kế toán duyệt từng khoản).",
                    {
                        "lop_hoc_id": cls["id"],
                        "ma_lop": cls["ma_lop"],
                        "so_hoc_vien": cls["si_so"],
                        "ly_do": f"Không đủ sĩ số tối thiểu ({cls['si_so']}/{cls['si_so_toi_thieu']})",
                    },
                    evidence=evidence + ["Chính sách: 03_bao_luu_hoan_tien.md › Hoàn học phí (lớp không khai giảng)"],
                    dedupe_key=f"xu_ly_lop_thieu:{cls['id']}",
                )
    conflicts = _conflicts(conn, run, event.get("lop_hoc_id") if event else None)
    return f"{alerts} cảnh báo lớp thiếu; {conflicts} cặp lớp trùng lịch."


def _merge_target(conn, run: AgentRun, cls: dict) -> dict | None:
    for other in training.list_classes(conn, run.actor, course_id=cls["khoa_hoc_id"]):
        if other["id"] == cls["id"] or other["trang_thai"] not in ("sap_khai_giang", "dang_hoc"):
            continue
        if other["trang_thai"] == "dang_hoc" and other["buoi_da_hoc"] >= 3:
            continue
        if other["si_so_toi_da"] - other["si_so"] >= cls["si_so"] and other["si_so"] >= cls["si_so"]:
            return other
    return None


def _conflicts(conn, run: AgentRun, only_class: int | None) -> int:
    found = 0
    classes = [c for c in training.list_classes(conn, run.actor) if c["trang_thai"] in ("sap_khai_giang", "dang_hoc")]
    for c in classes:
        if only_class and c["id"] != only_class:
            continue
        for hit in training.find_conflicts(
            conn,
            c["ngay_khai_giang"],
            c["lich_hoc"],
            c["ca_hoc"],
            c["so_buoi"],
            c["giang_vien_id"],
            c["phong_hoc_id"],
            exclude_class=c["id"],
        ):
            a, b = sorted((c["id"], hit["lop_hoc_id"]))
            p = run.submit(
                "canh_bao_trung_lich",
                f"Trùng {' và '.join(hit['trung'])}: {c['ma_lop']} và {hit['ma_lop']}",
                "Hai lớp cùng ca, có chung ngày học trong tuần và thời gian học giao nhau.",
                {"lop_a": a, "lop_b": b, "trung": hit["trung"]},
                evidence=[f"{c['ma_lop']}: ca {c['ca_hoc']} {c['lich_hoc']}, GV {c['giang_vien']}, phòng {c['phong']}"],
                dedupe_key=f"trung:{a}:{b}",
            )
            found += p is not None
    return found


# =====================================================================
# 4. CHĂM SÓC - sự kiện attendance.marked / grade.recorded + lịch hằng ngày
# =====================================================================
CARE_SYSTEM = (
    "Bạn là chuyên viên chăm sóc học viên của Trung tâm Đào tạo Ánh Dương. Viết email hỏi thăm ngắn (4-5 câu, tiếng "
    "Việt, ân cần, không trách móc, xưng 'Trung tâm', gọi học viên là 'bạn') theo đúng tình trạng được nêu: nếu vắng "
    "học thì hỏi lý do và nhắc có thể học bù miễn phí tối đa 3 buổi ở lớp khác cùng khoá; nếu điểm chưa tốt thì đề "
    "nghị hỗ trợ ôn tập. Mời liên hệ nếu cần. Không chào kết, không ký tên."
)


def care_message(info: dict) -> tuple[str, str, bool]:
    if info["streak"] >= 2:
        reason = f"vắng {info['streak']} buổi liên tiếp"
        fallback = (
            f"Trung tâm nhận thấy bạn đã vắng {info['streak']} buổi gần đây của lớp {info['ma_lop']} và muốn hỏi thăm "
            "xem bạn có gặp khó khăn gì không. Nếu bạn bận đột xuất, bạn có thể đăng ký học bù miễn phí (tối đa 3 buổi) "
            "ở lớp khác cùng khoá. Trung tâm luôn sẵn sàng hỗ trợ để bạn theo kịp chương trình."
        )
    else:
        reason = "kết quả kiểm tra giữa khoá chưa tốt"
        fallback = (
            f"Trung tâm muốn hỏi thăm việc học của bạn ở lớp {info['ma_lop']} sau bài kiểm tra giữa khoá. Nếu có phần "
            "nào bạn thấy khó, giảng viên và trung tâm có thể sắp xếp buổi hỗ trợ thêm hoặc gợi ý tài liệu ôn tập. "
            "Bạn chỉ cần trả lời email này để trung tâm liên hệ."
        )
    text, used = draft_text(
        CARE_SYSTEM, f"Học viên: {info['ho_ten']}\nLớp: {info['ma_lop']}\nTình trạng: {reason}", fallback, 700
    )
    body = f"Chào {info['ho_ten']},\n\n{text}\n\nTrân trọng,\nTrung tâm Đào tạo Ánh Dương\nHotline 1900 0000"
    return f"Trung tâm Ánh Dương hỏi thăm bạn - lớp {info['ma_lop']}", body, used


def run_care(conn, run: AgentRun, event=None) -> str:
    where, params = "lh.trang_thai = 'dang_hoc' AND d.trang_thai_hoc = 'dang_hoc'", []
    if event and event.get("lop_hoc_id"):
        where += " AND lh.id = %s"
        params.append(event["lop_hoc_id"])
    elif event and event.get("don_hang_id"):
        where += " AND d.id = %s"
        params.append(event["don_hang_id"])
    rows = conn.execute(
        f"""SELECT d.id AS don_hang_id, d.hoc_vien_id, hv.ho_ten, lh.id AS lop_hoc_id, lh.ma_lop,
                   gv.username AS giang_vien_username,
                   (SELECT diem FROM diem_so s WHERE s.don_hang_id = d.id AND s.loai = 'giua_khoa') AS giua_khoa
            FROM don_hang d JOIN lop_hoc lh ON lh.id = d.lop_hoc_id JOIN hoc_vien hv ON hv.id = d.hoc_vien_id
            LEFT JOIN giang_vien gv ON gv.id = lh.giang_vien_id WHERE {where}""",
        params,
    ).fetchall()
    flagged = 0
    for r in rows:
        hist = conn.execute(
            """SELECT b.id, dd.trang_thai FROM diem_danh dd JOIN buoi_hoc b ON b.id = dd.buoi_hoc_id
               WHERE dd.don_hang_id = %s ORDER BY b.ngay DESC LIMIT 20""",
            (r["don_hang_id"],),
        ).fetchall()
        statuses = [h["trang_thai"] for h in hist]
        streak = rules.consecutive_absences(statuses)
        low_grade = r["giua_khoa"] is not None and float(r["giua_khoa"]) < rules.PASS_SCORE
        if streak < 2 and not low_grade:
            continue
        rate = rules.attendance_rate(statuses)
        info = {**r, "streak": streak}
        subject, body, used_llm = care_message(info)
        reasons = []
        if streak >= 2:
            reasons.append(f"Vắng {streak} buổi liên tiếp gần nhất")
        if low_grade:
            reasons.append(f"Điểm giữa khoá {float(r['giua_khoa']):g}/100 (< {rules.PASS_SCORE})")
        reasons.append(
            f"Chuyên cần {rate:.0%} trên {len(statuses)} buổi đã điểm danh (yêu cầu 80% để được cấp chứng nhận)"
        )
        key_part = hist[streak - 1]["id"] if streak >= 2 else "diem"
        p = run.submit(
            "hoi_tham_hoc_vien",
            f"Hỏi thăm {r['ho_ten']} - lớp {r['ma_lop']}",
            "; ".join(reasons[:-1]) + ". " + ("Thư do AI soạn." if used_llm else "Thư theo mẫu."),
            {
                "don_hang_id": r["don_hang_id"],
                "hoc_vien_id": r["hoc_vien_id"],
                "ho_ten": r["ho_ten"],
                "lop_hoc_id": r["lop_hoc_id"],
                "ma_lop": r["ma_lop"],
                "so_buoi_vang_lien_tiep": streak,
                "chuyen_can": round(rate, 3),
                "giang_vien_username": r["giang_vien_username"],
                "subject": subject,
                "body": body,
            },
            evidence=reasons,
            dedupe_key=f"hoi_tham:{r['don_hang_id']}:{key_part}",
        )
        flagged += p is not None
    return f"Xét {len(rows)} học viên; {flagged} người cần hỏi thăm."


# =====================================================================
# 5. BÁO CÁO - lịch hằng tuần (thứ Hai) hoặc chạy tay
# =====================================================================
REPORT_SYSTEM = (
    "Bạn là trợ lý phân tích của quản lý trung tâm đào tạo. Dựa trên số liệu (đã tính sẵn), viết 2-3 câu nhận xét "
    "ngắn gọn bằng tiếng Việt: điều đáng chú ý nhất và một việc nên làm tuần tới. CHỈ dùng con số có trong dữ liệu."
)


def run_report(conn, run: AgentRun, event=None) -> str:
    t = today()
    n = reports.weekly_numbers(conn, t - timedelta(days=1))
    a, b = n["tuan_nay"], n["tuan_truoc"]
    flags = reports.anomalies(n)
    pending = conn.execute("SELECT count(*) AS c FROM de_xuat_agent WHERE trang_thai = 'cho_duyet'").fetchone()["c"]
    lines = [
        f"Doanh thu: {vnd(a['doanh_thu'])} (tuần trước {vnd(b['doanh_thu'])})",
        f"Ghi danh mới: {a['ghi_danh_moi']} (tuần trước {b['ghi_danh_moi']})",
        f"Khách tiềm năng mới: {a['khach_moi']} (tuần trước {b['khach_moi']})",
        f"Huỷ ghi danh: {a['huy']} (tuần trước {b['huy']})",
        f"Nợ quá hạn hiện tại: {vnd(n['qua_han']['so_tien'])} ({n['qua_han']['hoc_vien']} học viên)",
        f"Đề xuất của agent đang chờ duyệt: {pending}",
    ]
    data_text = "\n".join(lines) + ("\nBất thường: " + "; ".join(flags) if flags else "")
    comment, used = draft_text(REPORT_SYSTEM, data_text, "", 500)
    body = "\n".join(f"• {x}" for x in lines)
    if flags:
        body += "\n\nĐiểm bất thường:\n" + "\n".join(f"⚠ {f}" for f in flags)
    if comment:
        body += f"\n\nNhận xét (AI): {comment}"
    week = t.isocalendar()
    run.submit(
        "bao_cao_tuan",
        f"Báo cáo tuần {week.week}/{week.year}",
        f"{len(flags)} điểm bất thường so với tuần trước." if flags else "Không có biến động bất thường.",
        {"tieu_de": f"Báo cáo tuần {week.week}/{week.year}", "noi_dung": body, "so_lieu": n},
        evidence=lines + flags,
        dedupe_key=f"bao_cao:{week.year}-{week.week}",
    )
    return f"Báo cáo tuần {week.week}: {len(flags)} điểm bất thường." + (" Có nhận xét AI." if used else "")


# =====================================================================
AGENTS: dict[str, BackgroundAgent] = {
    a.name: a
    for a in [
        BackgroundAgent(
            "cong_no",
            "Công nợ",
            "accountant",
            run_debt,
            (),
            "daily",
            "Quét đợt học phí sắp/quá hạn, nhắc theo bậc, đề xuất tạm dừng khi quá 14 ngày.",
        ),
        BackgroundAgent(
            "tuyen_sinh",
            "Tuyển sinh",
            "consultant",
            run_leads,
            ("lead.created",),
            "daily",
            "Chấm điểm khách, gợi ý lớp, soạn tin tư vấn, nhắc tư vấn viên liên hệ.",
        ),
        BackgroundAgent(
            "giao_vu",
            "Giáo vụ",
            "academic",
            run_academic,
            ("class.schedule_changed", "class.created"),
            "daily",
            "Phát hiện lớp thiếu sĩ số, trùng lịch; đề xuất gộp hoặc huỷ lớp.",
        ),
        BackgroundAgent(
            "cham_soc",
            "Chăm sóc",
            "academic",
            run_care,
            ("attendance.marked", "grade.recorded"),
            "daily",
            "Phát hiện học viên có nguy cơ bỏ học, soạn tin hỏi thăm, báo giảng viên.",
        ),
        BackgroundAgent(
            "bao_cao",
            "Báo cáo",
            "manager",
            run_report,
            (),
            "weekly",
            "Tổng hợp tuần, nêu điểm bất thường, gửi quản lý.",
        ),
    ]
}
EVENT_ROUTES: dict[str, list[str]] = {}
for _a in AGENTS.values():
    for _e in _a.events:
        EVENT_ROUTES.setdefault(_e, []).append(_a.name)
