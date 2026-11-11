"""Sinh file đề xuất đồ án EduAssist Platform (A4 dọc).

Chạy: uv run --with reportlab python docs/proposal.py  -> docs/EduAssist_Platform_Proposal.pdf
"""

# ruff: noqa: E501  (các dòng dài là nội dung văn bản của tài liệu)

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

FONTS = "C:/Windows/Fonts/"
pdfmetrics.registerFont(TTFont("Arial", FONTS + "arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", FONTS + "arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", FONTS + "ariali.ttf"))
pdfmetrics.registerFont(TTFont("Arial-BoldItalic", FONTS + "arialbi.ttf"))
pdfmetrics.registerFontFamily(
    "Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic", boldItalic="Arial-BoldItalic"
)

OUT = Path(__file__).with_name("EduAssist_Platform_Proposal.pdf")
PAGE_W, PAGE_H = A4
MARGIN = 2 * cm
CONTENT_W = PAGE_W - 2 * MARGIN

INK = colors.HexColor("#1f2937")
MUTED = colors.HexColor("#6b7280")
NAVY = colors.HexColor("#1e3a5f")
LINE = colors.HexColor("#d1d5db")
HEAD_BG = colors.HexColor("#1e3a5f")
ROW_ALT = colors.HexColor("#f8fafc")
NOTE_BG = colors.HexColor("#eff6ff")
NOTE_BORDER = colors.HexColor("#3b82f6")
GREEN = (colors.HexColor("#f0fdf4"), colors.HexColor("#16a34a"))
BLUE = (colors.HexColor("#eef2ff"), colors.HexColor("#6366f1"))
CYAN = (colors.HexColor("#ecfeff"), colors.HexColor("#0891b2"))
ORANGE = (colors.HexColor("#fff7ed"), colors.HexColor("#ea580c"))
PURPLE = (colors.HexColor("#f5f3ff"), colors.HexColor("#7c3aed"))
GREY = (colors.HexColor("#f1f5f9"), colors.HexColor("#64748b"))

BODY = ParagraphStyle("body", fontName="Arial", fontSize=10, leading=14.5, textColor=INK, spaceAfter=6)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8.5, leading=11.5, textColor=MUTED, spaceAfter=4)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.8, leading=12, spaceAfter=0)
CELL_HEAD = ParagraphStyle("cellhead", parent=CELL, fontName="Arial-Bold", textColor=colors.white)
H1 = ParagraphStyle("h1", fontName="Arial-Bold", fontSize=15, leading=19, textColor=NAVY, spaceBefore=14, spaceAfter=8)
H2 = ParagraphStyle("h2", fontName="Arial-Bold", fontSize=11.5, leading=15, textColor=INK, spaceBefore=10, spaceAfter=5)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=14, bulletIndent=3, spaceAfter=3)
NOTE = ParagraphStyle("note", parent=BODY, fontSize=9.5, leading=13.5, spaceAfter=0)


def p(text):
    return Paragraph(text, BODY)


def h1(text):
    return Paragraph(text, H1)


def h2(text):
    return Paragraph(text, H2)


def bullets(items):
    return [Paragraph(t, BULLET, bulletText="•") for t in items]


def table(rows, widths, head=True):
    """rows: list các list chuỗi. widths: tỉ lệ cột (tự quy về bề rộng trang)."""
    total = sum(widths)
    col_w = [CONTENT_W * w / total for w in widths]
    data = []
    for i, row in enumerate(rows):
        style = CELL_HEAD if head and i == 0 else CELL
        data.append([Paragraph(str(c), style) for c in row])
    t = Table(data, colWidths=col_w, repeatRows=1 if head else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if head:
        style.append(("BACKGROUND", (0, 0), (-1, 0), HEAD_BG))
        style += [("BACKGROUND", (0, i), (-1, i), ROW_ALT) for i in range(2, len(rows), 2)]
    else:
        style.append(("BACKGROUND", (0, 0), (0, -1), ROW_ALT))
    t.setStyle(TableStyle(style))
    return t


def note(text):
    t = Table([[Paragraph(text, NOTE)]], colWidths=[CONTENT_W])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NOTE_BG),
                ("LINEBEFORE", (0, 0), (0, -1), 3, NOTE_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def gap(h=6):
    return Spacer(1, h)


# ---------------------------------------------------------------- hình vẽ
class Diagram(Flowable):
    def __init__(self, height, draw_fn):
        super().__init__()
        self.width, self.height, self.draw_fn = CONTENT_W, height, draw_fn

    def wrap(self, *_):
        return self.width, self.height

    def draw(self):
        self.draw_fn(self.canv, self.width, self.height)


def _box(c, x, top, w, h, title, sub=None, palette=GREY, total_h=0, size=8.5):
    """x, top tính từ góc TRÊN-trái của hình."""
    bg, border = palette
    y = total_h - top - h
    c.setFillColor(bg)
    c.setStrokeColor(border)
    c.setLineWidth(0.9)
    c.roundRect(x, y, w, h, 5, stroke=1, fill=1)
    c.setFillColor(INK)
    lines = title.split("\n")
    subs = sub.split("\n") if sub else []
    block = len(lines) * (size + 2) + len(subs) * 9
    cy = y + h / 2 + block / 2 - size
    c.setFont("Arial-Bold", size)
    for ln in lines:
        c.drawCentredString(x + w / 2, cy, ln)
        cy -= size + 2
    c.setFont("Arial", 7)
    c.setFillColor(MUTED)
    for ln in subs:
        c.drawCentredString(x + w / 2, cy, ln)
        cy -= 9


def _band(c, top, h, label, palette, total_w, total_h):
    bg, border = palette
    c.setFillColor(colors.white)
    c.setStrokeColor(border)
    c.setLineWidth(0.8)
    c.setDash(3, 2)
    c.roundRect(0, total_h - top - h, total_w, h, 6, stroke=1, fill=0)
    c.setDash()
    c.setFont("Arial-Bold", 7.5)
    c.setFillColor(border)
    c.drawString(6, total_h - top - 10, label)


def _arrow(c, x1, y1, x2, y2, total_h, label=None):
    """Toạ độ y tính từ mép trên."""
    c.setStrokeColor(colors.HexColor("#475569"))
    c.setFillColor(colors.HexColor("#475569"))
    c.setLineWidth(0.9)
    ya, yb = total_h - y1, total_h - y2
    c.line(x1, ya, x2, yb)
    import math

    ang = math.atan2(yb - ya, x2 - x1)
    s = 4.5
    pth = c.beginPath()
    pth.moveTo(x2, yb)
    pth.lineTo(x2 - s * math.cos(ang - 0.45), yb - s * math.sin(ang - 0.45))
    pth.lineTo(x2 - s * math.cos(ang + 0.45), yb - s * math.sin(ang + 0.45))
    pth.close()
    c.drawPath(pth, stroke=0, fill=1)
    if label:
        c.setFont("Arial-Italic", 6.8)
        c.setFillColor(MUTED)
        c.drawCentredString((x1 + x2) / 2, (ya + yb) / 2 + 3, label)


def draw_architecture(c, w, h):
    pad, gapx = 8, 6

    def row(top, bh, items, palette):
        n = len(items)
        bw = (w - 2 * pad - (n - 1) * gapx) / n
        for i, (title, sub) in enumerate(items):
            _box(c, pad + i * (bw + gapx), top, bw, bh, title, sub, palette, h)

    _band(c, 0, 58, "GIAO DIỆN WEB (Next.js)", BLUE, w, h)
    row(
        16,
        36,
        [
            ("Cổng học viên", "lịch học · công nợ · yêu cầu"),
            ("Bàn làm việc nhân viên", "tuyển sinh · học vụ · thu phí"),
            ("Dashboard quản lý", "báo cáo · cấu hình"),
            ("Hộp duyệt + Copilot", "duyệt đề xuất · chat"),
        ],
        BLUE,
    )

    _band(c, 70, 58, "API (FastAPI)", CYAN, w, h)
    row(
        86,
        36,
        [
            ("REST nghiệp vụ", "CRUD + hành động"),
            ("Chat SSE", "stream token / bước / duyệt"),
            ("Xác thực + RBAC", "JWT · vai trò · hạn mức"),
            ("Webhook", "thanh toán · email"),
        ],
        CYAN,
    )

    _band(c, 140, 84, "LÕI ỨNG DỤNG", GREEN, w, h)
    third = (w - 2 * pad - 2 * 46) / 3
    x1, x2, x3 = pad, pad + third + 46, pad + 2 * (third + 46)
    _box(
        c,
        x1,
        158,
        third,
        58,
        "Tầng Service",
        "luật nghiệp vụ · máy trạng thái\nkiểm tra quyền · ghi audit",
        ORANGE,
        h,
        9.5,
    )
    _box(
        c,
        x2,
        158,
        third,
        58,
        "Agent Runtime (LangGraph)",
        "Supervisor + agent chuyên trách\ntool = hàm của tầng Service",
        GREEN,
        h,
        8.3,
    )
    _box(c, x3, 158, third, 58, "Worker", "lịch chạy hằng ngày\nxử lý sự kiện từ outbox", GREEN, h, 9.5)
    _arrow(c, x2, 187, x1 + third, 187, h, "gọi tool")
    _arrow(c, x3, 187, x2 + third, 187, h, "kích hoạt")

    _band(c, 236, 58, "POSTGRESQL 16 + pgvector (một cơ sở dữ liệu)", ORANGE, w, h)
    row(
        252,
        36,
        [
            ("Dữ liệu nghiệp vụ", "học viên · lớp · hoá đơn..."),
            ("Kho tri thức", "vector + full-text"),
            ("Trạng thái agent", "checkpoint · bộ nhớ"),
            ("Vận hành", "outbox · hàng đợi · audit"),
        ],
        ORANGE,
    )

    _band(c, 306, 52, "DỊCH VỤ BÊN NGOÀI", PURPLE, w, h)
    row(
        322,
        30,
        [
            ("LLM", "đổi nhà cung cấp bằng cấu hình"),
            ("SMTP", "gửi email"),
            ("Cổng thanh toán", "sandbox / giả lập"),
            ("Langfuse", "theo dõi agent"),
        ],
        PURPLE,
    )

    for top in (58, 128, 224, 294):
        _arrow(c, w / 2, top, w / 2, top + 12, h)


def draw_agent_loop(c, w, h):
    bw, bh = 82, 44
    xs = [0, 100, 200, 300]
    mid = 48
    items = [
        ("Kích hoạt", "sự kiện · lịch chạy\n· câu chat", GREY),
        ("Agent", "đọc dữ liệu\nlập luận, chọn tool", GREEN),
        ("Đề xuất", "tham số do LLM chọn\nsố liệu do code tính", GREEN),
        ("Chính sách\ntự chủ", None, ORANGE),
    ]
    for x, (t, s, pal) in zip(xs, items, strict=True):
        _box(c, x, mid - bh / 2, bw, bh, t, s, pal, h)
    for a, b in zip(xs, xs[1:], strict=False):
        _arrow(c, a + bw, mid, b, mid, h)

    bx, bw2 = 396, 70
    _box(c, bx, 4, bw2, 36, "Tự thực thi", "trong hạn mức (L2)", GREEN, h)
    _box(c, bx, 56, bw2, 36, "Hộp duyệt", "người quyết định (L1)", BLUE, h)
    _arrow(c, xs[3] + bw, mid - 8, bx, 22, h)
    _arrow(c, xs[3] + bw, mid + 8, bx, 74, h)

    y2 = 122
    _box(
        c, 284, y2, 182, 34, "Tầng Service kiểm tra luật rồi mới ghi", "cùng luật với nhân viên cùng vai trò", ORANGE, h
    )
    _box(c, 84, y2, 182, 34, "Cơ sở dữ liệu + Audit log", "ai / agent nào · làm gì · vì sao · ai duyệt", ORANGE, h)
    _arrow(c, bx + bw2 / 2, 92, bx + bw2 / 2, y2, h)  # Hộp duyệt -> Service
    c.setStrokeColor(colors.HexColor("#475569"))
    c.setLineWidth(0.9)
    c.line(bx + bw2, h - 22, w - 4, h - 22)  # Tự thực thi -> vòng ra mép phải -> Service
    c.line(w - 4, h - 22, w - 4, h - (y2 + 17))
    _arrow(c, w - 4, y2 + 17, 466, y2 + 17, h)
    _arrow(c, 284, y2 + 17, 266, y2 + 17, h)
    c.setFont("Arial-Italic", 7.2)
    c.setFillColor(MUTED)
    c.drawString(0, h - y2 - 14, "Duyệt / từ chối / sửa")
    c.drawString(0, h - y2 - 24, "→ dữ liệu đánh giá")


# ---------------------------------------------------------------- trang
def footer(c, doc):
    c.saveState()
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(MARGIN, 1.4 * cm, PAGE_W - MARGIN, 1.4 * cm)
    c.setFont("Arial", 8)
    c.setFillColor(MUTED)
    c.drawString(MARGIN, 1.0 * cm, "EduAssist Platform · Đề xuất đồ án tốt nghiệp")
    c.drawRightString(PAGE_W - MARGIN, 1.0 * cm, f"Trang {doc.page}")
    c.restoreState()


def cover(c, doc):
    c.saveState()
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 9.2 * cm, PAGE_W, 9.2 * cm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Arial-Bold", 11)
    c.drawString(MARGIN, PAGE_H - 3.2 * cm, "ĐỀ XUẤT ĐỒ ÁN TỐT NGHIỆP")
    c.setFont("Arial-Bold", 34)
    c.drawString(MARGIN, PAGE_H - 5.2 * cm, "EduAssist Platform")
    c.setFont("Arial", 14)
    c.drawString(MARGIN, PAGE_H - 6.4 * cm, "Nền tảng quản lý và vận hành trung tâm đào tạo,")
    c.drawString(MARGIN, PAGE_H - 7.1 * cm, "tích hợp hệ đa tác tử AI (Agentic AI)")
    c.setFont("Arial", 9)
    c.setFillColor(MUTED)
    c.drawString(MARGIN, 1.0 * cm, "Phiên bản 1.0 · Tháng 11/2026")
    c.restoreState()


def build():
    s = []

    # ---------------- bìa
    s += [Spacer(1, 8.6 * cm)]
    s += [
        table(
            [
                ["Sinh viên thực hiện", "(điền họ tên, MSSV)"],
                ["Giảng viên hướng dẫn", "(điền họ tên)"],
                ["Loại đề tài", "Xây dựng sản phẩm phần mềm ứng dụng AI"],
                ["Thời gian dự kiến", "16 tuần (một học kỳ)"],
            ],
            [3, 7],
            head=False,
        ),
        gap(14),
        h2("Tài liệu này trả lời"),
        *bullets(
            [
                "<b>Đề tài</b> là gì và <b>giải quyết bài toán</b> nào (mục 1, 2).",
                "<b>Phạm vi</b>: ai sử dụng, quy mô bao nhiêu, làm gì và không làm gì (mục 3).",
                "<b>Input / Output</b> của hệ thống (mục 4).",
                "Chức năng, luật nghiệp vụ và <b>tầng agentic</b> vận hành hệ thống (mục 5, 6).",
                "Kiến trúc, dữ liệu, kế hoạch 16 tuần, cách đánh giá và rủi ro (mục 7 đến 12).",
            ]
        ),
        gap(10),
        note(
            "<b>Điểm xuất phát:</b> đồ án phát triển tiếp từ prototype EduAssist đã chạy được: một chatbot đa tác tử "
            "(tư vấn bằng RAG, phân tích dữ liệu bằng Text-to-SQL, thao tác có người duyệt). Bản prototype dừng ở "
            "mức chatbot. Đồ án này biến nó thành một nền tảng nghiệp vụ hoàn chỉnh, trong đó agent tham gia vận hành."
        ),
        PageBreak(),
    ]

    # ---------------- 1
    s += [
        h1("1. Tóm tắt đề tài"),
        p(
            "<b>EduAssist Platform</b> là một hệ thống web quản lý toàn bộ vòng đời học viên của một trung tâm đào tạo: "
            "tuyển sinh, ghi danh, xếp lớp, điểm danh, thu học phí và chăm sóc. Điểm khác biệt là các <b>AI agent "
            "tham gia vận hành</b>: chúng theo dõi dữ liệu, tự phát hiện việc cần làm, soạn sẵn và thực hiện nghiệp vụ, "
            "dưới sự kiểm soát của con người."
        ),
        table(
            [
                ["Câu hỏi", "Trả lời ngắn"],
                [
                    "<b>Đề tài</b>",
                    "Xây dựng nền tảng quản lý và vận hành trung tâm đào tạo, tích hợp hệ đa tác tử AI có khả năng "
                    "thực hiện nghiệp vụ.",
                ],
                [
                    "<b>Giải quyết bài toán gì</b>",
                    "Trung tâm quy mô vừa đang vận hành bằng Excel, Zalo và sức người. Việc lặp lại (nhắc nợ, theo "
                    "đuổi khách, trả lời câu hỏi, làm báo cáo) chiếm phần lớn thời gian. Luật nghiệp vụ áp dụng không "
                    "nhất quán. Hệ thống gom dữ liệu về một nơi, cài luật vào phần mềm, và giao việc lặp lại cho agent.",
                ],
                [
                    "<b>Input</b>",
                    "Thao tác nghiệp vụ trên web; câu hỏi và yêu cầu bằng tiếng Việt tự nhiên; sự kiện hệ thống "
                    "(khách mới, hoá đơn quá hạn, học viên vắng); tài liệu chính sách; quyết định duyệt của con người.",
                ],
                [
                    "<b>Output</b>",
                    "Dữ liệu nghiệp vụ nhất quán; câu trả lời có trích nguồn; báo cáo số liệu; đề xuất hành động chờ "
                    "duyệt; hành động đã thực hiện (email, hoá đơn, voucher) kèm nhật ký đầy đủ.",
                ],
                [
                    "<b>Scope</b>",
                    "Một trung tâm, 1 đến 3 cơ sở, khoảng 2.000 đến 5.000 học viên, 20 đến 50 nhân viên. Sáu nhóm "
                    "người dùng: học viên, tư vấn viên, giáo vụ, kế toán, giảng viên, quản lý.",
                ],
            ],
            [2.6, 7.4],
        ),
    ]

    # ---------------- 2
    s += [
        h1("2. Bối cảnh và bài toán"),
        h2("2.1. Hiện trạng ở trung tâm đào tạo quy mô vừa"),
        table(
            [
                ["Vấn đề", "Biểu hiện", "Hậu quả"],
                [
                    "Dữ liệu rời rạc",
                    "Khách tiềm năng nằm trong Zalo, học viên trong Excel, công nợ trong sổ kế toán.",
                    "Không ai thấy bức tranh đầy đủ về một học viên. Dữ liệu lệch nhau giữa các bộ phận.",
                ],
                [
                    "Việc lặp lại tốn người",
                    "Nhắc học phí, nhắc lịch, gọi lại khách cũ, trả lời cùng một câu hỏi về chính sách.",
                    "Nhân viên bận việc vặt, bỏ sót khách và bỏ sót công nợ.",
                ],
                [
                    "Luật nằm trong đầu người",
                    "Hoàn phí, bảo lưu, cộng dồn ưu đãi do từng nhân viên tự nhớ và tự tính.",
                    "Cùng một tình huống, mỗi người xử lý một kiểu. Dễ sai và khó kiểm tra lại.",
                ],
                [
                    "Quyết định chậm",
                    "Báo cáo làm tay vào cuối tháng. Lớp thiếu học viên chỉ được phát hiện sát ngày khai giảng.",
                    "Quản lý phản ứng muộn với doanh thu giảm, lớp rỗng, học viên bỏ học.",
                ],
            ],
            [2.2, 4, 3.8],
        ),
        h2("2.2. Giải pháp hiện có và khoảng trống"),
        *bullets(
            [
                "<b>Phần mềm quản lý trung tâm</b> lưu trữ tốt nhưng <b>thụ động</b>: người dùng phải tự vào xem, "
                "tự phát hiện vấn đề và tự làm từng thao tác.",
                "<b>Chatbot AI</b> trả lời được câu hỏi nhưng <b>không nối với nghiệp vụ</b>: không biết công nợ của "
                "học viên, không tạo được hoá đơn, không gửi được nhắc nhở.",
                "<b>Khoảng trống:</b> một hệ thống vừa là nơi ghi nhận nghiệp vụ với luật chặt chẽ, vừa có agent chủ động "
                "làm việc trên chính dữ liệu đó, với cơ chế kiểm soát rõ ràng.",
            ]
        ),
        h2("2.3. Câu hỏi đồ án cần trả lời"),
        *bullets(
            [
                "Thiết kế thế nào để agent thực hiện được nghiệp vụ thật (tiền, email, dữ liệu học viên) mà vẫn an toàn?",
                "Loại thao tác nào nên để agent tự làm, loại nào bắt buộc phải có người duyệt?",
                "Đo hiệu quả của agent bằng chỉ số nào, và đạt được bao nhiêu trên dữ liệu thử nghiệm?",
            ]
        ),
    ]

    # ---------------- 3
    s += [
        h1("3. Mục tiêu và phạm vi"),
        h2("3.1. Mục tiêu"),
        *bullets(
            [
                "Xây dựng một ứng dụng web hoàn chỉnh (giao diện, backend, cơ sở dữ liệu) phủ các nghiệp vụ cốt lõi "
                "của trung tâm, với luật nghiệp vụ được cài trong phần mềm.",
                "Xây dựng tầng agentic gồm trợ lý hội thoại và các agent chạy nền, dùng chung luật nghiệp vụ với "
                "giao diện web.",
                "Xây dựng cơ chế kiểm soát: phân quyền cho agent, mức tự chủ theo loại thao tác, hộp duyệt, nhật ký.",
                "Đánh giá định lượng: độ chính xác của agent, độ an toàn, và mức giảm thao tác thủ công.",
            ]
        ),
        h2("3.2. Người sử dụng"),
        table(
            [
                ["Vai trò", "Dùng hệ thống để", "Agent hỗ trợ"],
                [
                    "Học viên / phụ huynh",
                    "Xem lịch học, công nợ, kết quả; gửi yêu cầu bảo lưu, hoàn phí; hỏi chính sách.",
                    "Trả lời có trích nguồn; tư vấn khoá học theo nhu cầu.",
                ],
                [
                    "Tư vấn viên",
                    "Quản lý khách tiềm năng, lịch hẹn, học thử, ghi danh.",
                    "Chấm điểm khách, soạn tin tư vấn, nhắc việc cần theo đuổi.",
                ],
                [
                    "Giáo vụ",
                    "Mở lớp, xếp lịch, xếp phòng, điểm danh, học bù, chuyển lớp.",
                    "Cảnh báo lớp thiếu sĩ số, trùng lịch; đề xuất xếp học bù.",
                ],
                [
                    "Kế toán",
                    "Lập hoá đơn, ghi nhận thanh toán, theo dõi công nợ, hoàn phí.",
                    "Nhắc nợ theo bậc; đối soát thanh toán; đề xuất xử lý quá hạn.",
                ],
                [
                    "Giảng viên",
                    "Xem lịch dạy, điểm danh, nhập điểm, nhận xét học viên.",
                    "Tóm tắt tình hình lớp; phát hiện học viên có nguy cơ bỏ học.",
                ],
                [
                    "Quản lý",
                    "Xem dashboard, duyệt đề xuất, cấu hình chính sách và mức tự chủ.",
                    "Báo cáo tự động; hỏi số liệu bằng ngôn ngữ tự nhiên.",
                ],
            ],
            [2.2, 4.4, 3.4],
        ),
        h2("3.3. Quy mô thiết kế"),
        p(
            "Các con số dưới đây là <b>mục tiêu thiết kế</b>, sẽ được kiểm chứng bằng dữ liệu giả lập và kiểm thử tải ở giai đoạn cuối."
        ),
        table(
            [
                ["Hạng mục", "Mục tiêu"],
                ["Tổ chức", "1 trung tâm, 1 đến 3 cơ sở. Chưa hỗ trợ nhiều trung tâm dùng chung (multi-tenant)."],
                ["Dữ liệu", "2.000 đến 5.000 học viên, 50 đến 200 lớp mỗi năm, vài chục nghìn giao dịch thanh toán."],
                ["Người dùng đồng thời", "Khoảng 100 người dùng web, 10 đến 20 phiên chat cùng lúc."],
                [
                    "Thời gian phản hồi",
                    "Trang nghiệp vụ dưới 1 giây. Câu trả lời của agent bắt đầu hiện chữ trong vài giây.",
                ],
                ["Triển khai", "Docker Compose trên một máy chủ. Một cơ sở dữ liệu PostgreSQL."],
            ],
            [2.6, 7.4],
        ),
        h2("3.4. Trong và ngoài phạm vi"),
        table(
            [
                ["Trong phạm vi", "Ngoài phạm vi"],
                [
                    "• Web cho học viên và nhân viên, đủ 8 phân hệ ở mục 5<br/>"
                    "• Luật nghiệp vụ và máy trạng thái cho ghi danh, hoá đơn, bảo lưu, hoàn phí<br/>"
                    "• Trợ lý hội thoại, 5 agent chạy nền, hộp duyệt<br/>"
                    "• Gửi email thật qua SMTP<br/>"
                    "• Bộ đánh giá agent và kiểm thử tự động",
                    "• Cổng thanh toán thật (chỉ làm sandbox / giả lập)<br/>"
                    "• Ứng dụng di động (web hiển thị tốt trên điện thoại)<br/>"
                    "• Lớp học trực tuyến, quản lý nội dung bài giảng (LMS)<br/>"
                    "• Tính lương, kế toán thuế<br/>"
                    "• Tích hợp Zalo OA thật (thiết kế sẵn điểm nối, chưa cài)<br/>"
                    "• Dữ liệu khách hàng thật: toàn bộ dữ liệu là giả lập",
                ],
            ],
            [5, 5],
        ),
    ]

    # ---------------- 4
    s += [
        h1("4. Input và Output"),
        table(
            [
                ["Input", "Ví dụ", "Output tương ứng"],
                [
                    "<b>Thao tác trên web</b>",
                    "Tư vấn viên ghi danh học viên vào lớp IELTS, chọn trả góp.",
                    "Bản ghi ghi danh đã qua kiểm tra luật (còn chỗ, đủ điều kiện trả góp); hoá đơn và 2 đợt thanh toán "
                    "được sinh tự động.",
                ],
                [
                    "<b>Ngôn ngữ tự nhiên</b>",
                    '"Doanh thu tháng 10 theo từng khoá?" hoặc "Nghỉ giữa chừng có được hoàn tiền không?"',
                    "Bảng số liệu kèm câu SQL đã chạy; câu trả lời chính sách kèm nguồn tài liệu đã kiểm chứng.",
                ],
                [
                    "<b>Sự kiện và lịch chạy</b>",
                    "Hoá đơn quá hạn 3 ngày; khách mới để lại số điện thoại; học viên vắng 2 buổi liên tiếp.",
                    "Đề xuất hành động trong hộp duyệt (danh sách nhắc nợ, tin nhắn hỏi thăm), hoặc hành động tự thực "
                    "hiện nếu nằm trong hạn mức.",
                ],
                [
                    "<b>Tài liệu chính sách</b>",
                    "File Markdown / PDF về học phí, hoàn phí, bảo lưu, nội quy.",
                    "Kho tri thức để agent tra cứu; danh sách câu hỏi mà tài liệu chưa trả lời được.",
                ],
                [
                    "<b>Quyết định của con người</b>",
                    "Quản lý bấm Duyệt, Từ chối hoặc Sửa một đề xuất của agent.",
                    "Hành động được thực thi và ghi nhật ký; quyết định trở thành dữ liệu để đánh giá agent.",
                ],
            ],
            [2.3, 3.5, 4.2],
        ),
    ]

    # ---------------- 5
    s += [
        h1("5. Chức năng và luật nghiệp vụ"),
        p(
            "Hệ thống gồm 8 phân hệ. Cột bên phải là ví dụ về luật được <b>kiểm tra trong code</b>, không phụ thuộc "
            "vào trí nhớ của nhân viên hay lời dặn trong prompt. Các ngưỡng cụ thể lấy từ bộ chính sách giả lập "
            "của trung tâm và cấu hình được."
        ),
        table(
            [
                ["Phân hệ", "Chức năng chính", "Ví dụ luật nghiệp vụ"],
                [
                    "<b>1. Tuyển sinh (CRM)</b>",
                    "Khách tiềm năng, nguồn khách, lịch hẹn, học thử, chuyển thành học viên.",
                    "Khách chuyển trạng thái theo đúng trình tự; mỗi khách có một người phụ trách; quá 3 ngày chưa liên hệ thì cảnh báo.",
                ],
                [
                    "<b>2. Đào tạo</b>",
                    "Khoá học, lớp, lịch, phòng, giảng viên, kiểm tra đầu vào.",
                    "Không xếp trùng phòng hoặc trùng giảng viên; lớp chỉ mở khi đạt sĩ số tối thiểu.",
                ],
                [
                    "<b>3. Ghi danh và học vụ</b>",
                    "Ghi danh, chuyển lớp, bảo lưu, điểm danh, học bù, điểm, chứng nhận.",
                    "Không ghi danh quá sĩ số tối đa; bảo lưu có thời hạn; chứng nhận yêu cầu đủ tỉ lệ chuyên cần.",
                ],
                [
                    "<b>4. Tài chính</b>",
                    "Hoá đơn, trả góp, ghi nhận thanh toán, công nợ, hoàn phí, ưu đãi và voucher.",
                    "Trả góp 2 đợt chỉ cho khoá từ 5 triệu; mức hoàn phí theo thời điểm huỷ; voucher có hạn mức theo vai trò.",
                ],
                [
                    "<b>5. Cổng học viên</b>",
                    "Lịch học, công nợ, thanh toán, gửi yêu cầu, hỏi đáp.",
                    "Học viên chỉ thấy dữ liệu của chính mình (lọc theo định danh trong phiên đăng nhập).",
                ],
                [
                    "<b>6. Thông báo</b>",
                    "Email và thông báo trong ứng dụng, mẫu nội dung, lịch sử gửi.",
                    "Không gửi trùng cùng một nội dung trong 24 giờ; giới hạn số người nhận mỗi đợt.",
                ],
                [
                    "<b>7. Báo cáo</b>",
                    "Doanh thu, công nợ, tỉ lệ chuyển đổi, tỉ lệ lấp đầy lớp, chuyên cần.",
                    "Số liệu tính từ một nguồn duy nhất; agent chỉ được đọc qua tài khoản chỉ đọc.",
                ],
                [
                    "<b>8. Quản trị</b>",
                    "Người dùng, vai trò, cấu hình chính sách, mức tự chủ của agent, nhật ký.",
                    "Mọi thay đổi dữ liệu nhạy cảm đều ghi nhật ký: ai, lúc nào, giá trị trước và sau.",
                ],
            ],
            [2.4, 3.6, 4],
        ),
        h2("Vòng đời các đối tượng chính (máy trạng thái)"),
        table(
            [
                ["Đối tượng", "Các trạng thái và hướng chuyển"],
                ["Khách tiềm năng", "Mới → Đã liên hệ → Hẹn học thử → Đã ghi danh, hoặc → Không tiếp tục"],
                [
                    "Ghi danh",
                    "Chờ thanh toán → Đang học → Hoàn thành; từ Đang học có thể → Bảo lưu → Đang học, hoặc → Đã huỷ",
                ],
                ["Hoá đơn", "Chưa thanh toán → Thanh toán một phần → Đã thanh toán; có thể → Quá hạn, → Đã hoàn"],
                ["Đề xuất của agent", "Chờ duyệt → Đã duyệt → Đã thực hiện, hoặc → Từ chối, → Hết hạn"],
            ],
            [2.4, 7.6],
        ),
        gap(6),
        note(
            "<b>Nguyên tắc cốt lõi:</b> luật nghiệp vụ nằm ở <b>một chỗ duy nhất</b> là tầng Service. Giao diện web và "
            "agent đều gọi qua tầng này. Vì vậy agent không thể làm điều mà một nhân viên cùng vai trò không được làm, "
            "kể cả khi LLM bị dẫn dắt sai."
        ),
    ]

    # ---------------- 6
    s += [
        h1("6. Tầng agentic: agent tham gia vận hành"),
        h2("6.1. Bốn nguyên tắc thiết kế"),
        *bullets(
            [
                '<b>Agent là "nhân viên số" có vai trò và hạn mức.</b> Tool của agent chính là các hàm của tầng Service, '
                "nên agent chịu cùng luật và cùng phân quyền với con người.",
                "<b>LLM quyết định ý định, code quyết định dữ liệu.</b> LLM chỉ chọn việc cần làm và vài tham số ngắn. "
                "Danh sách người nhận, số tiền, nội dung theo mẫu đều do code lấy từ cơ sở dữ liệu. Bài học này đến từ "
                "prototype: khi để LLM tự chép danh sách 153 người nợ, kết quả vừa thiếu vừa chậm.",
                "<b>Thao tác có tác động phải có người duyệt</b>, trừ khi loại thao tác đó đã được quản lý cho phép tự "
                "động trong một hạn mức cụ thể.",
                "<b>Mọi việc agent làm đều để lại dấu vết và đo được</b>: nhật ký, lý do, người duyệt, kết quả.",
            ]
        ),
        KeepTogether([h2("6.2. Vòng xử lý của một agent"), Diagram(160, draw_agent_loop)]),
        gap(4),
        h2("6.3. Ba cách agent tham gia"),
        table(
            [
                ["Cách", "Mô tả", "Trạng thái"],
                [
                    "<b>Copilot hội thoại</b>",
                    "Khung chat có trong mọi màn hình. Người dùng hỏi số liệu, hỏi chính sách, "
                    'hoặc ra lệnh bằng tiếng Việt ("gửi nhắc nợ cho lớp này").',
                    "Đã có ở prototype, sẽ nhúng vào web",
                ],
                [
                    "<b>Agent chạy nền</b>",
                    "Tự chạy theo lịch hoặc khi có sự kiện, không cần ai hỏi. Kết quả là các đề xuất "
                    "hoặc hành động trong hạn mức.",
                    "Xây mới",
                ],
                [
                    "<b>Hộp duyệt</b>",
                    "Một màn hình gom mọi đề xuất của agent. Người có quyền xem căn cứ, sửa, duyệt hoặc "
                    "từ chối, từng việc hoặc cả loạt.",
                    "Mở rộng từ cơ chế duyệt đã có",
                ],
            ],
            [2.3, 5.3, 2.4],
        ),
        h2("6.4. Danh mục agent"),
        table(
            [
                ["Agent", "Kích hoạt", "Việc agent làm", "Mức tự chủ mặc định"],
                [
                    "<b>Tư vấn</b>",
                    "Câu hỏi của học viên",
                    "Trả lời chính sách có trích nguồn, gợi ý khoá học và lớp sắp mở.",
                    "Tự trả lời (chỉ đọc)",
                ],
                [
                    "<b>Phân tích</b>",
                    "Câu hỏi của nhân viên",
                    "Viết và chạy SQL chỉ đọc, trả bảng số liệu kèm câu SQL.",
                    "Tự trả lời (chỉ đọc)",
                ],
                [
                    "<b>Tuyển sinh</b>",
                    "Khách mới; khách chưa được liên hệ",
                    "Chấm điểm khách, đề xuất lớp phù hợp, soạn tin tư vấn, tạo việc nhắc cho tư vấn viên.",
                    "Chờ duyệt tin nhắn; tự tạo việc nhắc",
                ],
                [
                    "<b>Công nợ</b>",
                    "Lịch hằng ngày",
                    "Quét hoá đơn sắp và quá hạn; nhắc theo bậc: trước hạn 3 ngày, quá 1 ngày, quá 7 ngày; quá 14 ngày thì đề xuất tạm dừng.",
                    "Nhắc lần đầu tự động; từ lần 2 chờ duyệt",
                ],
                [
                    "<b>Giáo vụ</b>",
                    "Lịch hằng ngày; thay đổi lịch",
                    "Phát hiện lớp thiếu sĩ số trước khai giảng, trùng lịch; đề xuất gộp lớp, dời lịch, xếp học bù.",
                    "Chờ duyệt",
                ],
                [
                    "<b>Chăm sóc</b>",
                    "Điểm danh; điểm kiểm tra",
                    "Phát hiện học viên có nguy cơ bỏ học (vắng liên tiếp, điểm giảm), soạn tin hỏi thăm, báo giảng viên.",
                    "Chờ duyệt",
                ],
                [
                    "<b>Báo cáo</b>",
                    "Lịch hằng tuần",
                    "Tổng hợp doanh thu, công nợ, tuyển sinh; nêu điểm bất thường so với tuần trước.",
                    "Tự gửi cho quản lý",
                ],
                [
                    "<b>Vận hành</b>",
                    "Lệnh trong chat",
                    "Thực hiện thao tác theo yêu cầu: gửi email, cấp voucher, nhắc nợ hàng loạt.",
                    "Chờ duyệt",
                ],
            ],
            [1.5, 2, 4.5, 2],
        ),
        h2("6.5. Mức tự chủ"),
        p(
            "Quản lý cấu hình mức tự chủ cho <b>từng loại thao tác</b>, không phải cho cả agent. Mặc định là mức thận trọng."
        ),
        table(
            [
                ["Mức", "Ý nghĩa", "Ví dụ thao tác"],
                [
                    "<b>L0 · Gợi ý</b>",
                    "Agent chỉ báo cáo và cảnh báo, không tạo hành động.",
                    "Cảnh báo lớp thiếu sĩ số; báo cáo tuần.",
                ],
                [
                    "<b>L1 · Chờ duyệt</b>",
                    "Agent soạn sẵn hành động với đủ căn cứ; người có quyền quyết định.",
                    "Cấp voucher, hoàn phí, tạm dừng học viên, gửi email hàng loạt.",
                ],
                [
                    "<b>L2 · Tự động trong hạn mức</b>",
                    "Agent tự làm nếu nằm trong hạn mức; ghi nhật ký; người xem lại sau.",
                    "Nhắc lịch học; nhắc học phí lần đầu, tối đa N email mỗi ngày.",
                ],
                [
                    "<b>Cấm</b>",
                    "Agent không bao giờ được làm, kể cả khi được yêu cầu.",
                    "Sửa điểm, xoá dữ liệu, đổi quyền người dùng, ghi nhận đã thu tiền.",
                ],
            ],
            [2.4, 4, 3.6],
        ),
        h2("6.6. Cơ chế an toàn"),
        table(
            [
                ["Rủi ro", "Cách kiểm soát", "Nguồn gốc"],
                [
                    "Agent làm vượt quyền",
                    "Tool gọi qua tầng Service, kiểm tra vai trò và hạn mức trong code.",
                    "Mở rộng",
                ],
                [
                    "Người duyệt bị thông tin sai",
                    "Nội dung hộp duyệt do code tính từ dữ liệu sẽ được dùng, không lấy từ lời mô tả của LLM.",
                    "Đã có",
                ],
                [
                    "Làm lặp một việc",
                    "Khoá chống trùng cho mỗi hành động; quy tắc không gửi lại trong 24 giờ.",
                    "Đã có, mở rộng",
                ],
                [
                    "SQL do LLM viết gây hại",
                    "Kiểm tra cú pháp, danh sách bảng cho phép, tài khoản chỉ đọc, giới hạn thời gian.",
                    "Đã có",
                ],
                [
                    "Bịa thông tin hoặc bịa nguồn",
                    "Chỉ trả lời từ tài liệu tìm được; nguồn được đối chiếu với kho trước khi hiển thị.",
                    "Đã có",
                ],
                [
                    "Chỉ dẫn độc hại giấu trong dữ liệu",
                    "Dữ liệu đưa cho LLM được đánh dấu là dữ liệu; agent con không thấy toàn bộ hội thoại.",
                    "Đã có",
                ],
                ["Không biết agent đã làm gì", "Nhật ký đầy đủ và theo dõi từng bước chạy của agent.", "Mở rộng"],
            ],
            [2.6, 5.6, 1.8],
        ),
    ]

    # ---------------- 7
    s += [
        KeepTogether([h1("7. Kiến trúc hệ thống"), Diagram(362, draw_architecture)]),
        gap(8),
        h2("7.1. Các quyết định kiến trúc chính"),
        *bullets(
            [
                "<b>Một khối ứng dụng chia module</b> (modular monolith), không dùng microservice. Phù hợp với quy mô một "
                "trung tâm và thời gian một học kỳ, dễ triển khai và dễ kiểm thử.",
                "<b>Tầng Service dùng chung.</b> API cho web và tool của agent đều gọi cùng các hàm nghiệp vụ. Đây là điều "
                "làm cho agent an toàn theo thiết kế.",
                "<b>Một cơ sở dữ liệu PostgreSQL</b> cho dữ liệu nghiệp vụ, kho tri thức (pgvector), trạng thái agent, "
                "hàng đợi sự kiện và nhật ký. Ít thành phần phải vận hành, và mọi thứ nằm trong cùng một giao dịch.",
                "<b>Sự kiện qua bảng outbox.</b> Khi nghiệp vụ thay đổi (hoá đơn quá hạn, khách mới), một dòng sự kiện "
                "được ghi trong cùng giao dịch. Worker đọc bảng này để kích hoạt agent, nên không mất sự kiện.",
                "<b>Dừng và chạy tiếp bền vững.</b> Agent chờ duyệt không giữ tài nguyên: trạng thái nằm trong cơ sở dữ "
                "liệu, người dùng có thể duyệt sau vài giờ.",
            ]
        ),
        h2("7.2. Công nghệ"),
        table(
            [
                ["Tầng", "Công nghệ", "Ghi chú"],
                [
                    "Giao diện",
                    "Next.js (React, TypeScript), Tailwind CSS",
                    "Xây mới, thay cho giao diện chat Chainlit hiện tại",
                ],
                ["API", "FastAPI, JWT, SSE", "Đã có phần chat; thêm REST cho nghiệp vụ"],
                ["Nghiệp vụ", "Python, SQLAlchemy 2, Alembic (quản lý thay đổi schema)", "Xây mới"],
                [
                    "Agent",
                    "LangChain 1.x, LangGraph (checkpoint, interrupt, store)",
                    "Đã có, mở rộng thêm agent chạy nền",
                ],
                ["Dữ liệu", "PostgreSQL 16, pgvector, full-text search", "Đã có, mở rộng schema"],
                ["Worker", "Tiến trình Python đọc outbox và chạy theo lịch", "Xây mới"],
                ["LLM", "Qua một lớp trừu tượng; prototype dùng Groq (gpt-oss-120b)", "Đổi nhà cung cấp bằng cấu hình"],
                ["Embedding", "FastEmbed chạy tại chỗ, không gửi dữ liệu ra ngoài", "Đã có"],
                ["Vận hành", "Docker Compose, GitHub Actions, Langfuse, pytest", "Đã có, mở rộng"],
            ],
            [1.8, 4.6, 3.6],
        ),
    ]

    # ---------------- 8
    s += [
        h1("8. Mô hình dữ liệu"),
        table(
            [
                ["Nhóm", "Bảng chính", "Trạng thái"],
                ["Tuyển sinh", "khach_tiem_nang, nguon_khach, lich_hen, hoc_thu, viec_can_lam", "Mới"],
                [
                    "Đào tạo",
                    "khoa_hoc, lop_hoc, buoi_hoc, phong_hoc, giang_vien, co_so",
                    "Có khoa_hoc, lop_hoc; còn lại mới",
                ],
                [
                    "Học vụ",
                    "hoc_vien, ghi_danh, diem_danh, hoc_bu, bao_luu, diem_so, chung_nhan",
                    "Có hoc_vien; còn lại mới",
                ],
                [
                    "Tài chính",
                    "hoa_don, dot_thanh_toan, thanh_toan, hoan_phi, voucher, chuong_trinh_uu_dai",
                    "Có don_hang, thanh_toan, voucher; tách và mở rộng",
                ],
                ["Thông báo", "mau_thong_bao, thong_bao, email_log", "Có email_log; còn lại mới"],
                ["Agent", "de_xuat_agent, chinh_sach_tu_chu, lan_chay_agent, outbox_su_kien", "Mới"],
                ["Tri thức và học lại", "policy_chunks, sql_examples, knowledge_gap, query_log, feedback", "Đã có"],
                [
                    "Hệ thống",
                    "app_user, vai_tro, quyen, audit_log, checkpoints, store",
                    "Có app_user, checkpoints, store; còn lại mới",
                ],
            ],
            [2.2, 5.3, 2.5],
        ),
        gap(4),
        p(
            "Bảng trung tâm của tầng agentic là <b>de_xuat_agent</b>. Mỗi dòng lưu: agent nào đề xuất, loại hành động, "
            "tham số, căn cứ (dữ liệu dẫn tới đề xuất), trạng thái, người duyệt, thời điểm và kết quả thực hiện. "
            "Bảng này vừa phục vụ hộp duyệt, vừa là nguồn dữ liệu để đánh giá agent."
        ),
    ]

    # ---------------- 9
    s += [
        h1("9. Kế thừa từ prototype"),
        p(
            "Prototype EduAssist đã chạy được và có bộ đánh giá. Đây là nền để đồ án tập trung vào phần mới thay vì làm lại từ đầu."
        ),
        table(
            [
                ["Đã có và đã kiểm chứng", "Sẽ xây trong đồ án"],
                [
                    "Supervisor điều phối 3 agent (tư vấn, phân tích, vận hành)",
                    "5 agent chạy nền: tuyển sinh, công nợ, giáo vụ, chăm sóc, báo cáo",
                ],
                [
                    "Duyệt thao tác bằng interrupt, trạng thái lưu trong PostgreSQL",
                    "Hộp duyệt và cấu hình mức tự chủ theo loại thao tác",
                ],
                [
                    "Tool của agent tự truy vấn cơ sở dữ liệu",
                    "Tầng Service với luật nghiệp vụ và máy trạng thái; tool gọi qua tầng này",
                ],
                [
                    "7 bảng nghiệp vụ, tạo bằng một file SQL",
                    "Schema nghiệp vụ đầy đủ, có công cụ quản lý thay đổi schema",
                ],
                ["Giao diện chat (Chainlit)", "Toàn bộ giao diện web nghiệp vụ (Next.js), có nhúng Copilot"],
                ["Agent chỉ chạy khi có người hỏi", "Worker, outbox sự kiện, lịch chạy"],
                ["Phân quyền 3 vai trò, che thông tin cá nhân với học viên", "Phân quyền 6 vai trò, nhật ký kiểm toán"],
                [
                    "RAG tìm kiếm lai có kiểm chứng nguồn; Text-to-SQL 4 lớp an toàn; bộ nhớ dài hạn; vòng học lại từ đánh giá của người dùng",
                    "Giữ nguyên, dùng lại",
                ],
                [
                    "82 kiểm thử tự động, 4 bộ đánh giá agent, CI, Docker Compose",
                    "Bộ đánh giá cho agent chạy nền; kiểm thử tải",
                ],
            ],
            [5, 5],
        ),
        h2("Kết quả đánh giá của prototype (01/11/2026, model gpt-oss-120b)"),
        table(
            [
                ["Bộ đánh giá", "Số câu", "Kết quả"],
                ["Điều phối đúng agent", "16", "100%"],
                ["RAG: đúng thông tin / trích nguồn đúng / biết từ chối", "12", "100% / 100% / 100%"],
                ["Text-to-SQL, không có ví dụ mẫu", "15", "86,7% đúng; trung bình 1,13 lần chạy mỗi câu"],
                ["Text-to-SQL, có ví dụ mẫu động", "15", "93,3% đúng; trung bình 1,00 lần chạy mỗi câu"],
                ["Bảo mật (7 kịch bản tấn công)", "7", "Chặn 7 / 7"],
            ],
            [5.2, 1.3, 3.5],
        ),
        Paragraph(
            "Ghi chú: bộ câu hỏi còn nhỏ. Lần chạy RAG đầu tiên chỉ đạt 67% do lỗi nhận diện nguồn và đã được sửa. "
            "Một câu SQL sai ở cả hai cấu hình. Đồ án sẽ mở rộng bộ đánh giá ở mục 11.",
            SMALL,
        ),
    ]

    # ---------------- 10
    s += [
        h1("10. Kế hoạch thực hiện (16 tuần)"),
        table(
            [
                ["Giai đoạn", "Tuần", "Nội dung", "Kết quả kiểm chứng được"],
                [
                    "<b>1. Nền tảng</b>",
                    "1 đến 3",
                    "Thiết kế schema đầy đủ, công cụ quản lý schema, tầng Service cho đào tạo và ghi danh, khung web và đăng nhập.",
                    "Ghi danh một học viên từ web, có kiểm tra sĩ số; kiểm thử cho các luật.",
                ],
                [
                    "<b>2. Nghiệp vụ lõi</b>",
                    "4 đến 7",
                    "Tài chính (hoá đơn, trả góp, hoàn phí, voucher), học vụ (điểm danh, bảo lưu, chuyển lớp), tuyển sinh, cổng học viên.",
                    "Chạy trọn một vòng đời: khách mới → ghi danh → thanh toán → học → hoàn thành.",
                ],
                [
                    "<b>3. Agent trong web</b>",
                    "8 đến 9",
                    "Nhúng Copilot vào web; chuyển tool của agent sang gọi tầng Service; hộp duyệt; nhật ký kiểm toán.",
                    "Ra lệnh trong chat tạo đề xuất trong hộp duyệt; duyệt xong thì thực hiện và có nhật ký.",
                ],
                [
                    "<b>4. Agent chạy nền</b>",
                    "10 đến 12",
                    "Outbox và worker; agent công nợ, tuyển sinh, giáo vụ, chăm sóc, báo cáo; cấu hình mức tự chủ.",
                    "Chạy mô phỏng 30 ngày trên dữ liệu giả lập, agent sinh đề xuất đúng theo kịch bản.",
                ],
                [
                    "<b>5. Đánh giá</b>",
                    "13 đến 14",
                    "Mở rộng bộ đánh giá, kiểm thử tải, kiểm thử bảo mật, thử nghiệm với người dùng.",
                    "Bảng kết quả theo các chỉ số ở mục 11.",
                ],
                [
                    "<b>6. Hoàn thiện</b>",
                    "15 đến 16",
                    "Sửa lỗi, viết báo cáo, tài liệu triển khai, chuẩn bị demo.",
                    "Bản chạy được bằng một lệnh; báo cáo và video demo.",
                ],
            ],
            [1.9, 1.2, 4, 2.9],
        ),
        gap(4),
        p(
            "Thứ tự ưu tiên khi thiếu thời gian: giữ trọn giai đoạn 1 đến 3 và <b>hai agent chạy nền là công nợ và "
            "tuyển sinh</b>. Ba agent còn lại có thể giảm xuống mức gợi ý (L0)."
        ),
    ]

    # ---------------- 11
    s += [
        h1("11. Phương pháp đánh giá"),
        table(
            [
                ["Nhóm", "Chỉ số", "Cách đo", "Mục tiêu"],
                [
                    "Nghiệp vụ",
                    "Luật nghiệp vụ được cài đúng",
                    "Kiểm thử tự động cho từng luật và từng hướng chuyển trạng thái",
                    "100% kiểm thử qua",
                ],
                [
                    "Agent hội thoại",
                    "Điều phối, RAG, Text-to-SQL",
                    "Mở rộng bộ câu hỏi hiện có lên khoảng 100 câu",
                    "Điều phối và RAG từ 95%; SQL từ 90%",
                ],
                [
                    "Agent chạy nền",
                    "Tỉ lệ đề xuất đúng",
                    "Mô phỏng 30 ngày với kịch bản đã biết đáp án; so đề xuất với đáp án",
                    "Đúng từ 90%; không bỏ sót ca quá hạn",
                ],
                [
                    "An toàn",
                    "Thao tác trái phép",
                    "Bộ kịch bản tấn công: vượt quyền, chèn chỉ dẫn, SQL nguy hiểm, làm lặp",
                    "0 thao tác trái phép được thực hiện",
                ],
                [
                    "Hiệu quả",
                    "Giảm thao tác thủ công",
                    "Đếm số bước và thời gian cho 5 nghiệp vụ mẫu, có và không có agent",
                    "Báo cáo mức giảm đo được",
                ],
                [
                    "Con người",
                    "Tỉ lệ đề xuất được duyệt không sửa",
                    "Thử nghiệm với 3 đến 5 người đóng vai nhân viên",
                    "Báo cáo số liệu và nhận xét",
                ],
                [
                    "Hiệu năng",
                    "Thời gian phản hồi",
                    "Kiểm thử tải với 100 người dùng giả lập",
                    "Trang nghiệp vụ dưới 1 giây (p95)",
                ],
            ],
            [1.6, 2.4, 3.9, 2.1],
        ),
        Paragraph(
            "Các mục tiêu là ngưỡng đặt ra để phấn đấu. Kết quả thật, kể cả phần không đạt, sẽ được báo cáo đầy đủ.",
            SMALL,
        ),
    ]

    # ---------------- 12
    s += [
        h1("12. Rủi ro và cách giảm thiểu"),
        table(
            [
                ["Rủi ro", "Ảnh hưởng", "Giảm thiểu"],
                [
                    "Phạm vi quá rộng cho một học kỳ",
                    "Không kịp hoàn thành",
                    "Làm theo lát cắt dọc: mỗi giai đoạn có một luồng chạy được từ đầu đến cuối. Có thứ tự ưu tiên rõ (mục 10).",
                ],
                [
                    "LLM trả kết quả không ổn định",
                    "Agent sai hoặc khó đánh giá",
                    "Để code quyết định dữ liệu; đầu ra có cấu trúc; chạy bộ đánh giá sau mỗi thay đổi prompt.",
                ],
                [
                    "Giới hạn tốc độ và chi phí LLM",
                    "Agent chạy nền chậm, demo gián đoạn",
                    "Agent chạy nền xử lý theo lô, lọc bằng SQL trước, chỉ gọi LLM cho phần cần lập luận; có model dự phòng.",
                ],
                [
                    "Agent gây hậu quả thật",
                    "Gửi nhầm email, sai tiền",
                    "Mặc định chờ duyệt; hạn mức; chống lặp; môi trường thử dùng hộp thư giả.",
                ],
                [
                    "Dữ liệu giả lập thiếu thực tế",
                    "Kết quả đánh giá kém thuyết phục",
                    "Sinh dữ liệu theo kịch bản có chủ đích (lớp thiếu người, nợ quá hạn, học viên vắng) và công bố cách sinh.",
                ],
                [
                    "Xây giao diện tốn thời gian",
                    "Chậm phần agent",
                    "Dùng thư viện thành phần có sẵn; ưu tiên màn hình phục vụ luồng chính.",
                ],
            ],
            [2.6, 2.3, 5.1],
        ),
    ]

    # ---------------- 13
    s += [
        KeepTogether(
            [
                h1("13. Sản phẩm bàn giao"),
                *bullets(
                    [
                        "<b>Mã nguồn</b> đầy đủ (web, API, tầng Service, agent, worker), chạy được bằng Docker Compose.",
                        "<b>Cơ sở dữ liệu</b> với schema nghiệp vụ, script sinh dữ liệu giả lập theo kịch bản.",
                        "<b>Bộ kiểm thử và bộ đánh giá agent</b>, kèm kết quả chạy.",
                        "<b>Báo cáo đồ án</b>: phân tích, thiết kế, cài đặt, đánh giá, hạn chế.",
                        "<b>Tài liệu</b>: hướng dẫn triển khai, hướng dẫn sử dụng theo vai trò, tài liệu kiến trúc.",
                        "<b>Demo</b>: kịch bản và video chạy trọn vòng đời học viên có agent tham gia.",
                    ]
                ),
                gap(8),
                note(
                    "<b>Đóng góp chính của đồ án:</b> một mô hình tích hợp agent vào phần mềm nghiệp vụ, trong đó agent dùng "
                    "chung luật với con người, có mức tự chủ cấu hình được theo từng loại thao tác, và mọi hành động đều "
                    "qua kiểm soát và đo được. Mô hình này áp dụng được cho các phần mềm quản lý khác ngoài lĩnh vực đào tạo."
                ),
            ]
        )
    ]

    # Tiêu đề không được nằm trơ trọi cuối trang: còn ít chỗ thì sang trang mới trước khi in tiêu đề
    story = []
    for f in s:
        if isinstance(f, Paragraph) and f.style in (H1, H2):
            story.append(CondPageBreak(120 if f.style is H1 else 95))
        story.append(f)
    s = story

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=1.8 * cm,
        bottomMargin=2 * cm,
        title="EduAssist Platform - Đề xuất đồ án tốt nghiệp",
        author="EduAssist",
    )
    doc.build(s, onFirstPage=cover, onLaterPages=footer)
    print(f"OK -> {OUT} ({doc.page} trang)")


if __name__ == "__main__":
    build()
