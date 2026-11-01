"""Vẽ tài liệu kiến trúc EduAssist ra PDF (A3 ngang, 3 trang).

Chạy: python architecture.py  -> EduAssist_Architecture.pdf
"""

import math
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

FONTS = "C:/Windows/Fonts/"
pdfmetrics.registerFont(TTFont("Arial", FONTS + "arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", FONTS + "arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", FONTS + "ariali.ttf"))
pdfmetrics.registerFont(TTFont("Mono", FONTS + "consola.ttf"))

W, H = landscape(A3)
OUT = Path(__file__).with_name("EduAssist_Architecture.pdf")

INK = colors.HexColor("#1f2937")
MUTED = colors.HexColor("#6b7280")
NAVY = colors.HexColor("#1e3a5f")
ARROW = colors.HexColor("#475569")

# (nền, viền) cho từng lớp
C_CLIENT = (colors.HexColor("#eef2ff"), colors.HexColor("#6366f1"))
C_API = (colors.HexColor("#ecfeff"), colors.HexColor("#0891b2"))
C_AGENT = (colors.HexColor("#f0fdf4"), colors.HexColor("#16a34a"))
C_DATA = (colors.HexColor("#fff7ed"), colors.HexColor("#ea580c"))
C_EXT = (colors.HexColor("#f5f3ff"), colors.HexColor("#7c3aed"))
C_OPS = (colors.HexColor("#f1f5f9"), colors.HexColor("#64748b"))
C_WARN = (colors.HexColor("#fef2f2"), colors.HexColor("#dc2626"))
WHITE = colors.white


def Y(y):
    """Toạ độ tính từ MÉP TRÊN trang (dễ nghĩ hơn gốc dưới-trái của reportlab)."""
    return H - y


def fit(text, font, size, max_w):
    while size > 5 and pdfmetrics.stringWidth(text, font, size) > max_w:
        size -= 0.25
    return size


def text(c, x, y, s, font="Arial", size=10, color=INK, align="left"):
    c.setFont(font, size)
    c.setFillColor(color)
    if align == "center":
        c.drawCentredString(x, Y(y), s)
    elif align == "right":
        c.drawRightString(x, Y(y), s)
    else:
        c.drawString(x, Y(y), s)


def band(c, x, y, w, h, label, palette):
    bg, border = palette
    c.setFillColor(bg)
    c.setStrokeColor(border)
    c.setLineWidth(1)
    c.setDash(4, 3)
    c.roundRect(x, Y(y + h), w, h, 10, stroke=1, fill=1)
    c.setDash()
    text(c, x + 12, y + 16, label, "Arial-Bold", 9.5, border)


def box(
    c,
    x,
    y,
    w,
    h,
    title,
    lines=(),
    palette=C_AGENT,
    dashed=False,
    title_size=11,
    line_size=8.6,
    fill=WHITE,
    center=False,
    mono_prefix=None,
):
    bg, border = palette
    c.setFillColor(fill)
    c.setStrokeColor(border)
    c.setLineWidth(1.4)
    if dashed:
        c.setDash(5, 3)
    c.roundRect(x, Y(y + h), w, h, 7, stroke=1, fill=1)
    c.setDash()
    # dải màu trên đầu box
    c.setFillColor(border)
    c.roundRect(x, Y(y + 5), w, 5, 2.5, stroke=0, fill=1)
    ty = y + 21
    ts = fit(title, "Arial-Bold", title_size, w - 14)
    text(c, x + w / 2 if center else x + 8, ty, title, "Arial-Bold", ts, NAVY, "center" if center else "left")
    ly = ty + 4
    for ln in lines:
        font = "Arial"
        color = INK
        if ln.startswith("`"):
            ln, font = ln.strip("`"), "Mono"
        elif ln.startswith("~"):
            ln, font, color = ln[1:], "Arial-Italic", MUTED
        size = fit(ln, font, line_size, w - 16)
        ly += size + 4
        text(c, x + w / 2 if center else x + 9, ly, ln, font, size, color, "center" if center else "left")


def arrow(c, pts, label=None, color=ARROW, dashed=False, width=1.3, both=False, label_at=0.5, label_dx=0, label_dy=0):
    """pts: list các điểm (x, y) theo toạ độ-từ-trên. Vẽ polyline + mũi tên ở cuối."""
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(width)
    if dashed:
        c.setDash(5, 3)
    p = c.beginPath()
    p.moveTo(pts[0][0], Y(pts[0][1]))
    for x, y in pts[1:]:
        p.lineTo(x, Y(y))
    c.drawPath(p, stroke=1, fill=0)
    c.setDash()

    def head(a, b):
        (x1, y1), (x2, y2) = a, b
        ang = math.atan2(Y(y2) - Y(y1), x2 - x1)
        L, s = 8, 0.42
        hp = c.beginPath()
        hp.moveTo(x2, Y(y2))
        hp.lineTo(x2 - L * math.cos(ang - s), Y(y2) - L * math.sin(ang - s))
        hp.lineTo(x2 - L * math.cos(ang + s), Y(y2) - L * math.sin(ang + s))
        hp.close()
        c.drawPath(hp, stroke=0, fill=1)

    head(pts[-2], pts[-1])
    if both:
        head(pts[1], pts[0])
    if label:
        # đặt nhãn trên đoạn dài nhất
        segs = list(zip(pts, pts[1:], strict=False))
        (x1, y1), (x2, y2) = max(segs, key=lambda s: math.dist(*s))
        mx, my = x1 + (x2 - x1) * label_at + label_dx, y1 + (y2 - y1) * label_at + label_dy
        size = 7.8
        tw = pdfmetrics.stringWidth(label, "Arial-Italic", size)
        c.setFillColor(WHITE)
        c.rect(mx - tw / 2 - 3, Y(my + 3.5), tw + 6, size + 4, stroke=0, fill=1)
        text(c, mx, my + 1.5, label, "Arial-Italic", size, color, "center")


def header(c, title, subtitle, page):
    c.setFillColor(NAVY)
    c.rect(0, Y(52), W, 52, stroke=0, fill=1)
    text(c, 30, 33, title, "Arial-Bold", 20, WHITE)
    text(c, W - 30, 33, subtitle, "Arial", 10.5, colors.HexColor("#cbd5e1"), "right")
    text(c, W - 30, H - 12, f"EduAssist · Tài liệu kiến trúc · Trang {page}/3", "Arial", 8, MUTED, "right")


def legend(c, x, y, items):
    for i, (label, pal) in enumerate(items):
        xx = x + i * 125
        c.setFillColor(pal[0])
        c.setStrokeColor(pal[1])
        c.roundRect(xx, Y(y + 9), 14, 10, 2, stroke=1, fill=1)
        text(c, xx + 19, y + 7.5, label, "Arial", 8.5, INK)


# =====================================================================
# TRANG 1 - KIẾN TRÚC TỔNG THỂ
# =====================================================================
def page_overview(c):
    header(
        c,
        "EduAssist – Kiến trúc hệ thống",
        "Trợ lý AI multi-agent cho trung tâm đào tạo · LangGraph · FastAPI · PostgreSQL",
        1,
    )

    MX, MW = 30, 840  # cột chính
    SX, SW = 895, 265  # cột dịch vụ ngoài
    EX = SX + 15  # mép trái các box dịch vụ ngoài

    # ---- Lớp 1: kênh người dùng
    band(c, MX, 70, MW, 110, "1. KÊNH NGƯỜI DÙNG", C_CLIENT)
    box(
        c,
        50,
        90,
        175,
        68,
        "Học viên / Phụ huynh",
        ["Hỏi khoá học, học phí, lịch,", "chính sách bảo lưu, hoàn tiền", "~role = student"],
        C_CLIENT,
        line_size=8.2,
    )
    box(
        c,
        240,
        90,
        175,
        68,
        "Nhân viên / Quản lý",
        ["Hỏi số liệu kinh doanh,", "giao việc hành chính", "~role = staff | manager"],
        C_CLIENT,
        line_size=8.2,
    )
    box(
        c,
        470,
        90,
        210,
        68,
        "Chainlit UI (web chat)",
        ["Stream chữ + hiện từng bước agent", "Nút Duyệt / Từ chối (HITL)", "Like / Dislike → feedback"],
        C_CLIENT,
        line_size=8.2,
    )
    box(
        c,
        700,
        90,
        155,
        68,
        "Zalo OA / Messenger",
        ["Kênh mở rộng (giai đoạn sau)", "Webhook → cùng API", "~chỉ cho agent tư vấn"],
        C_CLIENT,
        dashed=True,
        line_size=8.2,
    )
    arrow(c, [(137, 158), (137, 168), (520, 168), (520, 158)])
    c.setStrokeColor(ARROW)
    c.setLineWidth(1.3)
    c.line(327, Y(158), 327, Y(168))

    # ---- Lớp 2: API
    band(c, MX, 190, MW, 100, "2. API GATEWAY", C_API)
    box(
        c,
        50,
        210,
        300,
        70,
        "FastAPI",
        [
            "`POST /chat         → SSE stream",
            "`POST /chat/resume  → duyệt / từ chối",
            "`GET  /conversations/{id}/... · /health",
        ],
        C_API,
    )
    box(
        c,
        365,
        210,
        235,
        70,
        "Xác thực & phân quyền",
        ["JWT → user_id + role", "Role quyết định agent/tool được dùng", "~(kiểm soát trong code, không trong prompt)"],
        C_API,
    )
    box(
        c,
        615,
        210,
        240,
        70,
        "Bảo vệ API",
        ["Rate limit theo user", "Validate input (Pydantic)", "Lỗi → báo lịch sự, không lộ traceback"],
        C_API,
    )
    arrow(c, [(640, 158), (640, 184), (200, 184), (200, 210)], "HTTPS + SSE", both=True, label_at=0.3)
    arrow(c, [(777, 158), (777, 210)], "webhook", dashed=True)

    # ---- Lớp 3: agent
    band(c, MX, 302, MW, 278, "3. LỚP AGENT  (LangGraph)", C_AGENT)
    box(
        c,
        270,
        322,
        360,
        80,
        "Supervisor  (1 graph cho mỗi vai trò)",
        [
            "Agent con được bọc thành tool: ask_advisor / ask_analytics / ask_action",
            "Graph của học viên KHÔNG chứa tool analytics / action",
            "Bộ nhớ dài hạn (Store) · nguồn trích dẫn được kiểm chứng",
            "Giới hạn số lần gọi tool · checkpoint sau mỗi bước",
        ],
        C_AGENT,
    )
    arrow(c, [(200, 280), (200, 296), (450, 296), (450, 322)], "graph.astream(state, thread_id)", label_at=0.55)

    ay, ah, aw = 430, 110, 262
    box(
        c,
        45,
        ay,
        aw,
        ah,
        "Advisor agent – RAG",
        [
            "`search_policies  (hybrid: vector + full-text)",
            "`find_courses · my_enrollments (của chính mình)",
            "Trích nguồn tới từng mục tài liệu",
            "Không tìm thấy → nói rõ, ghi knowledge_gap",
            "~Quyền: student, staff, manager",
        ],
        C_AGENT,
    )
    box(
        c,
        319,
        ay,
        aw,
        ah,
        "Analytics agent – Text-to-SQL",
        [
            "Few-shot động: 3 ví dụ SQL gần nhất",
            "`run_sql → sqlglot: 1 SELECT, allowlist",
            "  → role agent_ro, LIMIT, timeout",
            "Lỗi / bị chặn → tự sửa (tối đa 4 lần chạy)",
            "~Quyền: staff, manager",
        ],
        C_AGENT,
    )
    box(
        c,
        593,
        ay,
        aw,
        ah,
        "Action agent – Human-in-the-loop",
        [
            "`send_email(recipients, subject, body)",
            "`create_voucher(hoc_vien_id, phan_tram)",
            "interrupt() → chờ duyệt · resume /chat/resume",
            "Chỉ gửi tới email học viên có thật · voucher ≤15/30%",
            "~Quyền: staff, manager",
        ],
        C_AGENT,
    )
    arrow(c, [(330, 402), (176, ay)], both=True)
    arrow(c, [(450, 402), (450, ay)], both=True)
    arrow(c, [(570, 402), (724, ay)], both=True)

    # middleware
    c.setFillColor(colors.HexColor("#dcfce7"))
    c.setStrokeColor(C_AGENT[1])
    c.roundRect(45, Y(570), 810, 22, 5, stroke=1, fill=1)
    # chừa khe ở x=230 và x=430 cho 2 mũi tên xuống lớp dữ liệu
    text(c, 55, 563, "Middleware:", "Arial-Bold", 8.6, NAVY)
    for x, seg, max_w in [
        (113, "ModelRetry + ModelFallback", 108),
        (240, "ToolCallLimit  ·  PII masking (học viên)", 182),
        (440, "Dynamic prompt (vai trò + bộ nhớ)  ·  Human-in-the-loop  ·  stream sự kiện tiến trình", 405),
    ]:
        text(c, x, 563, seg, "Arial", fit(seg, "Arial", 8.4, max_w), INK)

    # ---- Lớp 4: dữ liệu
    band(c, MX, 592, MW, 138, "4. DỮ LIỆU  (PostgreSQL 16)", C_DATA)
    dy, dh = 614, 78
    box(
        c,
        45,
        dy,
        195,
        dh,
        "pgvector",
        ["`policy_chunks (RAG)", "`sql_examples (few-shot)", "Embedding: FastEmbed local"],
        C_DATA,
    )
    box(
        c,
        250,
        dy,
        195,
        dh,
        "Nghiệp vụ + log",
        [
            "`hoc_vien, khoa_hoc, lop_hoc, don_hang,",
            "`thanh_toan, voucher (giả lập)",
            "`query_log, feedback, knowledge_gap",
        ],
        C_DATA,
    )
    box(
        c,
        455,
        dy,
        195,
        dh,
        "Checkpointer",
        ["State theo thread_id", "Resume HITL qua nhiều request", "Server restart không mất chat"],
        C_DATA,
    )
    box(
        c,
        660,
        dy,
        195,
        dh,
        "Store (bộ nhớ dài hạn)",
        ["Hồ sơ & sở thích theo user", "VD: con lớp 8, học buổi tối", "Namespace theo user_id"],
        C_DATA,
    )
    text(c, 45, 714, "DB roles:", "Arial-Bold", 8.6, NAVY)
    text(
        c,
        95,
        714,
        "app_rw  (API, ghi dữ liệu)   ·   agent_ro  (CHỈ SELECT trên allowlist bảng – dùng cho Analytics agent)   ·   "
        "Một database cho cả 4 vai trò → 1 dịch vụ để chạy & deploy",
        "Arial",
        8.6,
        INK,
    )

    arrow(c, [(230, ay + ah), (230, dy)])
    text(c, 236, 604, "truy vấn vector", "Arial-Italic", 7.8, ARROW)
    arrow(c, [(430, ay + ah), (430, dy)])
    text(c, 436, 604, "SELECT (agent_ro)", "Arial-Italic", 7.8, ARROW)
    arrow(
        c, [(630, 390), (868, 390), (868, 600), (552, 600), (552, dy)], "checkpoint mỗi bước", label_at=0.5, dashed=True
    )
    arrow(c, [(760, 600), (760, dy)], dashed=True)
    text(c, 766, 609, "Store", "Arial-Italic", 7.8, ARROW)

    # ---- Lớp 5: vận hành
    band(c, MX, 742, MW, 64, "5. VẬN HÀNH", C_OPS)
    for i, (t, l) in enumerate(
        [
            ("Docker Compose", "api · ui · postgres (1 lệnh chạy hết)"),
            ("GitHub Actions CI", "ruff · pytest · integration test Postgres"),
            ("Deploy", "Render / Railway / Fly.io + Postgres managed"),
            ("Cấu hình", "pydantic-settings · secrets qua .env"),
        ]
    ):
        x = 45 + i * 205
        text(c, x, 774, t, "Arial-Bold", 9.2, NAVY)
        text(c, x, 789, l, "Arial", 8.3, INK)

    # ---- Cột dịch vụ ngoài
    band(c, SX, 190, SW, 540, "DỊCH VỤ BÊN NGOÀI", C_EXT)
    box(
        c,
        EX,
        212,
        SW - 30,
        74,
        "Embedding",
        ["FastEmbed (chạy local, miễn phí)", "multilingual-MiniLM – hiểu tiếng Việt", "~Không gửi dữ liệu ra ngoài"],
        C_EXT,
    )
    box(
        c,
        EX,
        318,
        SW - 30,
        92,
        "LLM provider",
        [
            "Chính: Groq (gpt-oss-120b)",
            "Dự phòng: model thứ 2 (fallback)",
            "Structured output: json_schema",
            "~Đổi provider = sửa .env",
        ],
        C_EXT,
    )
    box(
        c,
        EX,
        428,
        SW - 30,
        74,
        "Email / SMTP",
        ["Dev: Mailpit (bắt email giả)", "Prod: SMTP / SendGrid", "~Chỉ chạy sau khi được duyệt"],
        C_EXT,
    )
    box(
        c,
        EX,
        514,
        SW - 30,
        104,
        "Langfuse (observability)",
        [
            "Trace từng bước: LLM, tool, latency",
            "Token & chi phí theo user/agent",
            "Gắn feedback Like/Dislike vào trace",
            "Dataset + kết quả eval",
            "~Có thể tự host → dữ liệu học viên",
            "~không rời hạ tầng công ty",
        ],
        C_EXT,
    )
    box(
        c,
        EX,
        630,
        SW - 30,
        88,
        "Bảo mật dữ liệu cá nhân",
        [
            "Che email/SĐT trước khi ghi log",
            "Nội dung RAG = dữ liệu, không phải lệnh",
            "Không dùng eval() trong tool",
            "Secrets không commit lên git",
        ],
        C_WARN,
    )
    arrow(c, [(630, 350), (EX, 350)], "gọi LLM", label_at=0.78)
    arrow(c, [(855, 470), (EX, 470)])
    text(c, 882, 463, "gửi", "Arial-Italic", 7.8, ARROW, "center")
    arrow(c, [(855, 559), (EX, 559)], dashed=True)
    text(c, 882, 552, "trace", "Arial-Italic", 7.8, ARROW, "center")

    legend(
        c,
        30,
        820,
        [
            ("Kênh người dùng", C_CLIENT),
            ("API", C_API),
            ("Agent", C_AGENT),
            ("Dữ liệu", C_DATA),
            ("Dịch vụ ngoài", C_EXT),
            ("Bảo mật", C_WARN),
        ],
    )


# =====================================================================
# TRANG 2 - LUỒNG XỬ LÝ
# =====================================================================
def node(c, cx, cy, w, h, label, pal=C_AGENT, sub=None, round_=True):
    bg, border = pal
    c.setFillColor(bg)
    c.setStrokeColor(border)
    c.setLineWidth(1.4)
    c.roundRect(cx - w / 2, Y(cy + h / 2), w, h, h / 2 if round_ else 6, stroke=1, fill=1)
    text(c, cx, cy + (0 if sub else 3.5), label, "Arial-Bold", fit(label, "Arial-Bold", 10, w - 10), NAVY, "center")
    if sub:
        text(c, cx, cy + 13, sub, "Arial", fit(sub, "Arial", 8, w - 10), MUTED, "center")


def page_flows(c):
    header(
        c,
        "Luồng xử lý & các lớp an toàn",
        "Graph của Supervisor · Human-in-the-loop qua 2 request · Pipeline Text-to-SQL",
        2,
    )

    # ---- A. Graph
    band(c, 30, 70, 510, 500, "A. SUPERVISOR = create_agent, AGENT CON = TOOL", C_AGENT)
    gx = 230
    node(c, gx, 110, 90, 28, "START", C_OPS)
    node(c, gx, 172, 240, 44, "model (supervisor)", sub="dynamic prompt: vai trò + bộ nhớ dài hạn (Store)")
    node(c, gx, 262, 240, 44, "tools", sub="ToolNode – CHỈ có tool của vai trò này")
    arrow(c, [(gx, 124), (gx, 150)])
    arrow(c, [(gx - 20, 194), (gx - 20, 240)], "có tool_calls", label_at=0.5, label_dx=-38)
    arrow(c, [(gx + 20, 240), (gx + 20, 194)], "kết quả", label_at=0.5, label_dx=30, color=C_AGENT[1])
    subs = [
        ("ask_advisor", "→ Advisor agent", 103),
        ("ask_analytics", "→ Analytics agent", 228),
        ("ask_action", "→ Action agent", 353),
        ("remember_fact", "→ Store", 473),
    ]
    for tool_name, sub, cx in subs:
        node(c, cx, 352, 110, 42, tool_name, sub=sub, round_=False)
        arrow(c, [(gx + (cx - gx) * 0.5, 284), (cx, 331)])
    node(c, 353, 437, 190, 42, "interrupt()", C_WARN, sub="dừng CẢ graph cha, chờ người duyệt")
    arrow(c, [(353, 373), (353, 416)])
    node(c, gx, 510, 90, 28, "END", C_OPS)
    arrow(c, [(110, 172), (38, 172), (38, 510), (185, 510)], "không gọi tool nữa", label_at=0.62)
    text(
        c,
        75,
        540,
        "Học viên: [ask_advisor, remember_user_fact]  ·  Nhân viên / quản lý: cả 4 tool.",
        "Arial-Bold",
        8.5,
        NAVY,
    )
    text(
        c,
        75,
        554,
        "Agent con chạy BÊN TRONG tool; interrupt của nó vẫn dừng cả graph cha và resume đúng chỗ.",
        "Arial-Italic",
        8.5,
        MUTED,
    )

    # ---- B. Sequence HITL
    band(c, 555, 70, 605, 500, "B. HUMAN-IN-THE-LOOP QUA 2 HTTP REQUEST", C_WARN)
    lanes = [
        ("Nhân viên (Chainlit)", 635, C_CLIENT),
        ("FastAPI", 785, C_API),
        ("LangGraph", 935, C_AGENT),
        ("Postgres", 1085, C_DATA),
    ]
    for name, x, pal in lanes:
        node(c, x, 108, 130, 28, name, pal, round_=False)
        c.setStrokeColor(colors.HexColor("#cbd5e1"))
        c.setDash(3, 3)
        c.line(x, Y(122), x, Y(552))
        c.setDash()
    L = {n: x for n, x, _ in lanes}
    steps = [
        (150, "Nhân viên (Chainlit)", "FastAPI", "1  POST /chat  “Gửi email nhắc nợ học phí”"),
        (182, "FastAPI", "LangGraph", "2  astream(input, thread_id)"),
        (214, "LangGraph", "Postgres", "3  supervisor → analytics → action"),
        (246, "LangGraph", "Postgres", "4  send_email → interrupt(): LƯU state"),
        (278, "FastAPI", "Nhân viên (Chainlit)", "5  SSE: event interrupt (12 người nhận)"),
        (364, "Nhân viên (Chainlit)", "FastAPI", "6  POST /chat/resume {decision: approve}"),
        (396, "FastAPI", "LangGraph", "7  Command(resume=decisions)"),
        (428, "Postgres", "LangGraph", "8  nạp lại state từ checkpoint"),
        (460, "LangGraph", "LangGraph", "9  chạy send_email (chỉ lúc này)"),
        (492, "LangGraph", "FastAPI", "10  kết quả cuối"),
        (524, "FastAPI", "Nhân viên (Chainlit)", "11  SSE: “Đã gửi 12 email”"),
    ]
    for y, a, b, label in steps:
        if a == b:
            x = L[a]
            arrow(c, [(x, y - 8), (x + 40, y - 8), (x + 40, y + 4), (x + 4, y + 4)], color=C_WARN[1])
            text(c, x + 48, y + 1, label, "Arial", 8.3, INK)
            continue
        arrow(c, [(L[a], y), (L[b], y)])
        mid = (L[a] + L[b]) / 2
        tw = pdfmetrics.stringWidth(label, "Arial", 8.3)
        c.setFillColor(WHITE)
        c.rect(mid - tw / 2 - 3, Y(y - 3), tw + 6, 11, stroke=0, fill=1)
        text(c, mid, y - 5, label, "Arial", 8.3, INK, "center")
    c.setFillColor(C_WARN[0])
    c.setStrokeColor(C_WARN[1])
    c.roundRect(570, Y(345), 575, 40, 6, stroke=1, fill=1)
    text(
        c,
        857,
        321,
        "Request 1 kết thúc ở đây. Người duyệt có thể bấm sau vài phút, vài giờ,",
        "Arial-Bold",
        8.8,
        C_WARN[1],
        "center",
    )
    text(
        c,
        857,
        335,
        "kể cả khi server đã khởi động lại – vì state nằm trong Postgres, không nằm trong RAM.",
        "Arial",
        8.6,
        INK,
        "center",
    )

    # ---- C. Text-to-SQL pipeline
    band(c, 30, 584, 1130, 238, "C. PIPELINE TEXT-TO-SQL – 4 LỚP AN TOÀN (không trông vào prompt)", C_DATA)
    steps = [
        ("Câu hỏi", ["“Khoá nào bán chạy", "nhất quý 3?”"], C_CLIENT),
        ("Lấy ví dụ", ["3 cặp (câu hỏi, SQL)", "gần nhất từ pgvector", "~đã được nhân viên xác nhận"], C_DATA),
        ("LLM sinh SQL", ["Schema + ví dụ", "trong prompt"], C_EXT),
        ("(1) Kiểm tra cú pháp", ["sqlglot parse", "CHỈ SELECT", "bảng thuộc allowlist"], C_WARN),
        ("(2) Ép giới hạn", ["Tự thêm LIMIT 200", "statement_timeout 5s"], C_WARN),
        (
            "(3) Chạy read-only",
            ["Kết nối role agent_ro", "DB từ chối mọi lệnh ghi", "~kể cả khi (1) bị vượt qua"],
            C_WARN,
        ),
        ("Trả lời", ["Bảng + nhận xét", "kèm câu SQL đã chạy"], C_AGENT),
    ]
    bw, gap, y0 = 140, 21, 640
    for i, (t, ls, pal) in enumerate(steps):
        x = 45 + i * (bw + gap)
        box(c, x, y0, bw, 92, t, ls, pal, title_size=10.5, line_size=8.6)
        if i:
            arrow(c, [(x - gap, y0 + 46), (x, y0 + 46)])
    # vòng tự sửa
    x_llm = 45 + 2 * (bw + gap) + bw / 2
    x_val = 45 + 3 * (bw + gap) + bw / 2
    x_run = 45 + 5 * (bw + gap) + bw / 2
    arrow(c, [(x_val, y0 + 92), (x_val, y0 + 118), (x_llm, y0 + 118), (x_llm, y0 + 92)], color=C_WARN[1])
    arrow(
        c,
        [(x_run, y0 + 92), (x_run, y0 + 132), (x_llm - 20, y0 + 132), (x_llm - 20, y0 + 92)],
        "(4) lỗi → gửi thông báo lỗi cho LLM tự sửa (tối đa 4 lần chạy), quá giới hạn → báo không trả lời được",
        color=C_WARN[1],
        label_at=0.5,
    )
    text(
        c,
        45,
        806,
        "Vì sao nhiều lớp? Prompt “chỉ được SELECT” có thể bị vượt qua bằng prompt injection. "
        "Lớp (3) là chốt chặn cuối ở chính database.",
        "Arial-Italic",
        8.8,
        MUTED,
    )


# =====================================================================
# TRANG 3 - HỌC LIÊN TỤC, ĐÁNH GIÁ, LỘ TRÌNH
# =====================================================================
def page_learning(c):
    header(c, "Vòng học liên tục, đánh giá & lộ trình", "Data flywheel · Eval có số liệu · Công nghệ · 7 giai đoạn", 3)

    # ---- A. Flywheel
    band(c, 30, 70, 560, 480, "A. DATA FLYWHEEL – HỌC Ở LỚP BAO QUANH MODEL (không fine-tune)", C_AGENT)
    cx, cy, rx, ry = 310, 315, 190, 165
    items = [
        ("1. Người dùng dùng agent", ["Chat qua Chainlit / Zalo"], C_CLIENT),
        ("2. Thu tín hiệu", ["Like/Dislike · duyệt/từ chối", "nhân viên sửa câu trả lời"], C_CLIENT),
        ("3. Lưu vào Langfuse", ["Feedback gắn với trace", "đầy đủ từng bước"], C_EXT),
        ("4. Nhân viên xác nhận", ["Chỉ ví dụ do STAFF duyệt", "~chống dữ liệu bẩn / đầu độc"], C_WARN),
        ("5. Cập nhật tri thức", ["sql_examples (few-shot)", "báo lỗ hổng tài liệu RAG"], C_DATA),
        ("6. Eval trước / sau", ["Điểm tăng → áp dụng", "Điểm giảm → rollback"], C_AGENT),
    ]
    pos = []
    for i in range(len(items)):
        a = -math.pi / 2 + i * 2 * math.pi / len(items)
        pos.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    bw, bh = 168, 66
    for i, (px, py) in enumerate(pos):
        nx, ny = pos[(i + 1) % len(pos)]
        d = math.dist((px, py), (nx, ny))
        ux, uy = (nx - px) / d, (ny - py) / d
        # khoảng từ tâm box tới mép box theo hướng mũi tên (+5 cho thoáng)
        t = min(bw / 2 / abs(ux) if ux else 1e9, bh / 2 / abs(uy) if uy else 1e9) + 5
        sx, sy = px + ux * t, py + uy * t
        ex, ey = nx - ux * t, ny - uy * t
        arrow(c, [(sx, sy), (ex, ey)], color=C_AGENT[1], width=1.8)
    for (t, ls, pal), (px, py) in zip(items, pos, strict=False):
        box(c, px - bw / 2, py - bh / 2, bw, bh, t, ls, pal, title_size=10, line_size=8.4)
    text(c, cx, cy - 6, "Agent tốt hơn", "Arial-Bold", 13, C_AGENT[1], "center")
    text(c, cx, cy + 10, "sau mỗi vòng", "Arial", 10, C_AGENT[1], "center")
    text(
        c,
        45,
        532,
        "Bộ nhớ dài hạn (Store) học theo TỪNG người dùng; kho ví dụ + tài liệu học cho TOÀN hệ thống.",
        "Arial-Italic",
        8.6,
        MUTED,
    )

    # ---- B. Eval
    band(c, 605, 70, 555, 228, "B. ĐÁNH GIÁ (EVAL) – CON SỐ ĐƯA VÀO README & CV", C_EXT)
    data = [
        ["Thành phần", "Chỉ số", "Cách đo"],
        ["Supervisor", "Routing accuracy", "% câu hỏi đi đúng agent (bộ ~30 câu có nhãn)"],
        ["Analytics", "Execution accuracy", "Chạy SQL agent & SQL đáp án → so sánh kết quả"],
        ["Advisor", "Correctness · Faithfulness", "LLM-as-judge: đúng ý? có bám tài liệu?"],
        ["Advisor", "Citation rate", "% câu trả lời có trích nguồn hợp lệ"],
        ["Toàn hệ thống", "Latency p95 · chi phí/câu", "Lấy từ Langfuse traces"],
    ]
    t = Table(data, colWidths=[95, 150, 280])
    t.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Arial", 8.8),
                ("FONT", (0, 0), (-1, 0), "Arial-Bold", 9),
                ("BACKGROUND", (0, 0), (-1, 0), C_EXT[1]),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, C_EXT[0]]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c4b5fd")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    _, th = t.wrapOn(c, 525, 300)
    t.drawOn(c, 620, Y(96 + th))
    text(
        c,
        620,
        96 + th + 22,
        "CI chạy eval subset mỗi lần push · eval đầy đủ trước mỗi lần đổi prompt/model.",
        "Arial-Italic",
        8.6,
        MUTED,
    )

    # ---- C. Tech stack
    band(c, 605, 312, 555, 238, "C. CÔNG NGHỆ", C_OPS)
    stack = [
        ["Lớp", "Công nghệ"],
        ["Agent", "LangChain 1.x · LangGraph (StateGraph, interrupt, Store)"],
        ["LLM", "Groq (gpt-oss-120b) + fallback · FastEmbed (local)"],
        ["API", "FastAPI · SSE · Pydantic · JWT"],
        ["UI", "Chainlit (giai đoạn sau: Next.js + Vercel AI SDK)"],
        ["Dữ liệu", "PostgreSQL 16 · pgvector · langgraph-checkpoint-postgres"],
        ["An toàn", "sqlglot · role read-only · PIIMiddleware"],
        ["Quan sát", "Langfuse (cloud khi dev, tự host được)"],
        ["Chất lượng", "uv · Ruff · pytest + fake LLM · GitHub Actions"],
        ["Triển khai", "Docker Compose · Render / Railway / Fly.io"],
    ]
    t = Table(stack, colWidths=[95, 430])
    t.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Arial", 8.8),
                ("FONT", (0, 0), (-1, 0), "Arial-Bold", 9),
                ("FONT", (0, 1), (0, -1), "Arial-Bold", 8.8),
                ("BACKGROUND", (0, 0), (-1, 0), C_OPS[1]),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, C_OPS[0]]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 3.6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.6),
            ]
        )
    )
    _, th = t.wrapOn(c, 525, 300)
    t.drawOn(c, 620, Y(338 + th))

    # ---- D. Roadmap
    band(c, 30, 564, 1130, 232, "D. LỘ TRÌNH 7 GIAI ĐOẠN", C_CLIENT)
    phases = [
        ("1. Nền móng", ["Sườn dự án (uv)", "Docker + Postgres", "Sinh dữ liệu giả", "CI: lint + test"]),
        ("2. Analytics", ["Text-to-SQL", "4 lớp an toàn", "Bộ eval đầu tiên", "~phần khó nhất → làm trước"]),
        ("3. Advisor", ["RAG trên pgvector", "Trích nguồn", "Eval faithfulness"]),
        ("4. Action + Supervisor", ["HITL + interrupt", "Phân quyền theo role", "Checkpointer Postgres"]),
        ("5. API + UI", ["FastAPI SSE", "Chainlit: steps,", "nút duyệt, feedback"]),
        ("6. Hoàn thiện", ["Langfuse tracing", "Deploy", "README + GIF demo"]),
        ("7. Học liên tục", ["Kho ví dụ SQL", "Store theo user", "Eval trước / sau"]),
    ]
    gap, y0 = 18, 596
    bw = (1100 - 6 * gap) / 7
    for i, (t_, ls) in enumerate(phases):
        x = 45 + i * (bw + gap)
        box(c, x, y0, bw, 118, t_, ls, C_CLIENT if i < 6 else C_AGENT, title_size=10.5, line_size=8.8)
        if i:
            arrow(c, [(x - gap, y0 + 59), (x, y0 + 59)], width=1.6)
    text(c, 45, 742, "Mỗi giai đoạn = 1 hoặc vài commit có nghĩa, chạy được độc lập.", "Arial-Bold", 9, NAVY)
    text(
        c,
        45,
        758,
        "Ngoài phạm vi (nói rõ khi phỏng vấn): dữ liệu là giả lập · chưa có khách hàng thật · "
        "kênh Zalo/Messenger & đồng bộ Google Sheets là bước mở rộng.",
        "Arial",
        8.8,
        INK,
    )
    text(
        c,
        45,
        774,
        "Mục tiêu: làm đúng CÁCH LÀM của production (an toàn, chịu lỗi, test, đo lường, triển khai) – "
        "không phải chịu tải production.",
        "Arial",
        8.8,
        INK,
    )


c = canvas.Canvas(str(OUT), pagesize=(W, H))
c.setTitle("EduAssist – Tài liệu kiến trúc")
c.setAuthor("EduAssist")
for draw in (page_overview, page_flows, page_learning):
    draw(c)
    c.showPage()
c.save()
print("Đã tạo", OUT)
