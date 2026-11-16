"""Sinh đề cương đồ án tốt nghiệp EduAssist (A4, thể thức đề cương thông dụng: Times New Roman 13, lề trái 3 cm).

Chạy: uv run --with reportlab python docs/de_cuong.py  -> docs/EduAssist_De_Cuong_DATN.pdf
Điền thông tin sinh viên ở THONG_TIN rồi chạy lại.
"""

# ruff: noqa: E501  (các dòng dài là nội dung văn bản của tài liệu)

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.doctemplate import BaseDocTemplate
from reportlab.platypus.frames import Frame

# ------------------------------------------------------------------ thông tin trang bìa (sinh viên tự điền)
THONG_TIN = {
    "truong": "TRƯỜNG ĐẠI HỌC ....................................",
    "khoa": "KHOA ....................................",
    "nganh": "....................................",
    "sinh_vien": "....................................",
    "mssv": "....................",
    "lop": "....................",
    "gvhd": "....................................",
    "noi_lam": "...................",
    "thang_nam": "tháng 11 năm 2026",
}
REPO_URL = "https://github.com/hungtmh/eduassist"

FONTS = "C:/Windows/Fonts/"
pdfmetrics.registerFont(TTFont("Times", FONTS + "times.ttf"))
pdfmetrics.registerFont(TTFont("Times-B", FONTS + "timesbd.ttf"))
pdfmetrics.registerFont(TTFont("Times-I", FONTS + "timesi.ttf"))
pdfmetrics.registerFont(TTFont("Times-BI", FONTS + "timesbi.ttf"))
pdfmetrics.registerFontFamily("Times", normal="Times", bold="Times-B", italic="Times-I", boldItalic="Times-BI")

OUT = Path(__file__).with_name("EduAssist_De_Cuong_DATN.pdf")
PAGE_W, PAGE_H = A4
LEFT, RIGHT, TOP, BOTTOM = 3 * cm, 2 * cm, 2.5 * cm, 2.5 * cm
CONTENT_W = PAGE_W - LEFT - RIGHT

INK = colors.black
GRID = colors.HexColor("#555555")
HEAD_BG = colors.HexColor("#e6e6e6")

BODY = ParagraphStyle(
    "body", fontName="Times", fontSize=13, leading=18.5, alignment=TA_JUSTIFY, firstLineIndent=1 * cm, spaceAfter=6
)
PLAIN = ParagraphStyle("plain", parent=BODY, firstLineIndent=0)
H1 = ParagraphStyle("h1", fontName="Times-B", fontSize=13.5, leading=19, spaceBefore=12, spaceAfter=6, textColor=INK)
H2 = ParagraphStyle("h2", fontName="Times-BI", fontSize=13, leading=18, spaceBefore=6, spaceAfter=4, textColor=INK)
BULLET = ParagraphStyle("bullet", parent=PLAIN, leftIndent=0.9 * cm, bulletIndent=0.35 * cm, spaceAfter=3)
CELL = ParagraphStyle("cell", fontName="Times", fontSize=11.5, leading=14.5, spaceAfter=0)
CELL_B = ParagraphStyle("cellb", parent=CELL, fontName="Times-B")
CELL_C = ParagraphStyle("cellc", parent=CELL_B, alignment=TA_CENTER)
CAPTION = ParagraphStyle(
    "cap", fontName="Times-I", fontSize=11.5, leading=14, alignment=TA_CENTER, spaceBefore=3, spaceAfter=8
)
REF = ParagraphStyle(
    "ref", parent=PLAIN, fontSize=12, leading=16, leftIndent=0.9 * cm, firstLineIndent=-0.9 * cm, spaceAfter=4
)
TITLE = ParagraphStyle("title", fontName="Times-B", fontSize=16, leading=22, alignment=TA_CENTER, spaceAfter=10)


def p(text):
    return Paragraph(text, BODY)


def h1(text):
    return Paragraph(text, H1)


def h2(text):
    return Paragraph(text, H2)


def bullets(items, mark="-"):
    return [Paragraph(t, BULLET, bulletText=mark) for t in items]


def table(rows, widths, head=True, caption=None):
    total = sum(widths)
    data = []
    for i, row in enumerate(rows):
        style = CELL_C if head and i == 0 else CELL
        data.append([c if isinstance(c, Flowable) else Paragraph(str(c), style) for c in row])
    t = Table(data, colWidths=[CONTENT_W * w / total for w in widths], repeatRows=1 if head else 0)
    st = [
        ("GRID", (0, 0), (-1, -1), 0.6, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if head:
        st.append(("BACKGROUND", (0, 0), (-1, 0), HEAD_BG))
    t.setStyle(TableStyle(st))
    out = [Spacer(1, 3), t]
    if caption:
        out.append(Paragraph(caption, CAPTION))
    else:
        out.append(Spacer(1, 8))
    return out


# ------------------------------------------------------------------ sơ đồ kiến trúc
class Architecture(Flowable):
    """Sơ đồ khối: người dùng -> web -> API/chat/worker -> tầng Service -> dữ liệu."""

    H = 8.3 * cm

    def wrap(self, *_):
        return CONTENT_W, self.H

    def _box(self, x, y, w, h, title, sub=None, fill="#ffffff"):
        c = self.canv
        c.setFillColor(colors.HexColor(fill))
        c.setStrokeColor(GRID)
        c.setLineWidth(0.8)
        c.roundRect(x, y, w, h, 4, stroke=1, fill=1)
        c.setFillColor(INK)
        c.setFont("Times-B", 10.5)
        ty = y + h / 2 + (3 if sub else -3.5)
        c.drawCentredString(x + w / 2, ty, title)
        if sub:
            c.setFont("Times", 9)
            c.drawCentredString(x + w / 2, ty - 11, sub)

    def _arrow(self, x1, y1, x2, y2):
        c = self.canv
        c.setStrokeColor(GRID)
        c.setLineWidth(0.8)
        c.line(x1, y1, x2, y2)
        c.setFillColor(GRID)
        c.circle(x2, y2, 1.6, stroke=0, fill=1)

    def draw(self):
        w = CONTENT_W
        g = 6
        # hàng 1: người dùng
        u = (w - 2 * g) / 3
        top = self.H - 1.15 * cm
        for i, (t, s) in enumerate(
            [
                ("Khách / học viên", "web công khai, cổng học viên"),
                ("Nhân viên (5 vai trò)", "bàn làm việc, hộp duyệt"),
                ("Quản lý", "dashboard, cấu hình tự chủ"),
            ]
        ):
            self._box(i * (u + g), top, u, 1.0 * cm, t, s, "#f3f4f6")
        # hàng 2: web + Caddy
        y2 = top - 1.65 * cm
        self._box(0, y2, w, 1.0 * cm, "Next.js (giao diện)  ·  Caddy (HTTPS, chia tải, kiểm tra sống)", None, "#eef2ff")
        for i in range(3):
            self._arrow(i * (u + g) + u / 2, top, i * (u + g) + u / 2, y2 + 1.0 * cm)
        # hàng 3: api, api-chat, worker
        y3 = y2 - 1.75 * cm
        b = (w - 2 * g) / 3
        items = [
            ("api", "REST nghiệp vụ, JWT, 6 vai trò"),
            ("api-chat (async)", "Supervisor + 3 agent hội thoại"),
            ("worker", "5 agent nền, outbox, lịch chạy"),
        ]
        for i, (t, s) in enumerate(items):
            self._box(i * (b + g), y3, b, 1.1 * cm, t, s, "#ecfdf5")
        for i in range(2):
            self._arrow(i * (b + g) + b / 2, y2, i * (b + g) + b / 2, y3 + 1.1 * cm)
        # hàng 4: tầng Service
        y4 = y3 - 1.75 * cm
        self._box(
            0,
            y4,
            w,
            1.1 * cm,
            "Tầng Service (dùng chung cho web và agent)",
            "luật nghiệp vụ · máy trạng thái · phân quyền · hộp duyệt (L0/L1/L2/Cấm) · audit · outbox",
            "#fff7ed",
        )
        for i in range(3):
            self._arrow(i * (b + g) + b / 2, y3, i * (b + g) + b / 2, y4 + 1.1 * cm)
        # hàng 5: dữ liệu + ngoài
        y5 = y4 - 1.75 * cm
        d = (w - 2 * g) / 3
        self._box(
            0,
            y5,
            d * 2 + g,
            1.1 * cm,
            "PostgreSQL 16 + pgvector",
            "nghiệp vụ · vector RAG · trạng thái hội thoại · RLS (multi-tenant)",
            "#f5f3ff",
        )
        self._box(2 * (d + g), y5, d, 1.1 * cm, "Redis · LLM (Groq)", "bộ đếm, cache · mô hình ngôn ngữ", "#f3f4f6")
        self._arrow(w / 3, y4, w / 3, y5 + 1.1 * cm)
        self._arrow(2 * (d + g) + d / 2, y4, 2 * (d + g) + d / 2, y5 + 1.1 * cm)


# ------------------------------------------------------------------ trang bìa và chân trang
def cover(c, _doc):
    c.saveState()
    # khung đôi của bìa
    c.setStrokeColor(INK)
    c.setLineWidth(2.2)
    c.rect(2.0 * cm, 1.6 * cm, PAGE_W - 3.6 * cm, PAGE_H - 3.2 * cm)
    c.setLineWidth(0.7)
    c.rect(2.2 * cm, 1.8 * cm, PAGE_W - 4.0 * cm, PAGE_H - 3.6 * cm)
    cx = (2.0 * cm + PAGE_W - 1.6 * cm) / 2
    y = PAGE_H - 3.3 * cm
    c.setFillColor(INK)
    c.setFont("Times", 13)
    c.drawCentredString(cx, y, "BỘ GIÁO DỤC VÀ ĐÀO TẠO")
    c.setFont("Times-B", 13)
    c.drawCentredString(cx, y - 20, THONG_TIN["truong"])
    c.drawCentredString(cx, y - 40, THONG_TIN["khoa"])
    c.drawCentredString(cx, y - 52, "-----------------  o0o  -----------------")

    c.setFont("Times-B", 22)
    c.drawCentredString(cx, y - 7.0 * cm, "ĐỀ CƯƠNG")
    c.drawCentredString(cx, y - 7.0 * cm - 30, "ĐỒ ÁN TỐT NGHIỆP")

    c.setFont("Times-B", 13)
    c.drawCentredString(cx, y - 10.2 * cm, "ĐỀ TÀI:")
    c.setFont("Times-B", 16)
    for i, line in enumerate(
        [
            "XÂY DỰNG NỀN TẢNG QUẢN LÝ VÀ VẬN HÀNH",
            "TRUNG TÂM ĐÀO TẠO TÍCH HỢP HỆ ĐA TÁC TỬ AI,",
            "CÓ KHẢ NĂNG MỞ RỘNG ĐA KHÁCH HÀNG",
            "(MULTI-TENANT)",
        ]
    ):
        c.drawCentredString(cx, y - 11.2 * cm - i * 22, line)
    c.setFont("Times-I", 12)
    c.drawCentredString(
        cx,
        y - 11.2 * cm - 4 * 22 - 4,
        "EduAssist Platform: an agentic multi-agent platform for training-center operations",
    )

    lx = 5.6 * cm
    vy = y - 16.4 * cm
    c.setFont("Times", 13)
    for i, (k, v) in enumerate(
        [
            ("Ngành", THONG_TIN["nganh"]),
            ("Giảng viên hướng dẫn", THONG_TIN["gvhd"]),
            ("Sinh viên thực hiện", THONG_TIN["sinh_vien"]),
            ("Mã số sinh viên", THONG_TIN["mssv"]),
            ("Lớp", THONG_TIN["lop"]),
        ]
    ):
        c.setFont("Times-B", 13)
        c.drawString(lx, vy - i * 21, f"{k}:")
        c.setFont("Times", 13)
        c.drawString(lx + 5.0 * cm, vy - i * 21, v)

    c.setFont("Times-B", 13)
    c.drawCentredString(cx, 2.7 * cm, f"{THONG_TIN['noi_lam']}, {THONG_TIN['thang_nam']}")
    c.restoreState()


def footer(c, doc):
    c.saveState()
    c.setFont("Times", 11)
    c.setFillColor(INK)
    c.drawCentredString(LEFT + CONTENT_W / 2, 1.3 * cm, str(doc.page - 1))
    c.restoreState()


# ------------------------------------------------------------------ nội dung
def build():
    s = [Spacer(1, 1), NextPageTemplate("body"), PageBreak()]

    # ---------- thông tin chung
    s += [Paragraph("ĐỀ CƯƠNG ĐỒ ÁN TỐT NGHIỆP", TITLE)]
    s += table(
        [
            ["Mục", "Nội dung"],
            [
                "<b>Tên đề tài (tiếng Việt)</b>",
                "Xây dựng nền tảng quản lý và vận hành trung tâm đào tạo tích hợp hệ đa tác tử AI, có khả năng mở rộng đa khách hàng (multi-tenant)",
            ],
            [
                "<b>Tên đề tài (tiếng Anh)</b>",
                "EduAssist Platform: an agentic multi-agent platform for training-center operations, designed to scale to multi-tenant SaaS",
            ],
            [
                "<b>Loại đề tài</b>",
                "Ứng dụng: xây dựng sản phẩm phần mềm có thành phần trí tuệ nhân tạo, kèm thực nghiệm đánh giá",
            ],
            [
                "<b>Sinh viên thực hiện</b>",
                f"{THONG_TIN['sinh_vien']} - MSSV: {THONG_TIN['mssv']} - Lớp: {THONG_TIN['lop']}",
            ],
            ["<b>Giảng viên hướng dẫn</b>", THONG_TIN["gvhd"]],
            ["<b>Thời gian thực hiện</b>", "16 tuần (một học kỳ)"],
            ["<b>Mã nguồn</b>", f'<link href="{REPO_URL}" color="blue">{REPO_URL}</link>'],
        ],
        [3, 7],
    )

    # ---------- 1
    s += [
        h1("1. LÝ DO CHỌN ĐỀ TÀI"),
        p(
            "Các trung tâm đào tạo quy mô vừa (ngoại ngữ, tin học, kỹ năng) vận hành bằng nhiều công cụ rời rạc: khách "
            "tiềm năng nằm trong tin nhắn mạng xã hội, danh sách học viên trong bảng tính, công nợ trong sổ kế toán. "
            "Nhân viên mất nhiều thời gian cho việc lặp lại như nhắc học phí, gọi lại khách, trả lời cùng một câu hỏi về "
            "chính sách; các luật như hoàn phí, bảo lưu, cộng dồn ưu đãi do từng người tự nhớ nên dễ xử lý không nhất quán; "
            "báo cáo làm tay cuối tháng khiến quản lý phát hiện vấn đề muộn (lớp thiếu học viên, học viên bỏ học, nợ quá hạn)."
        ),
        p(
            "Phần mềm quản lý trung tâm hiện có lưu trữ tốt nhưng <b>thụ động</b>: người dùng phải tự vào xem, tự phát hiện "
            "vấn đề và tự làm từng thao tác. Ngược lại, các chatbot dùng mô hình ngôn ngữ lớn (LLM) trả lời được câu hỏi "
            "nhưng <b>không nối với nghiệp vụ</b>: không biết công nợ của học viên, không lập được hoá đơn hay gửi nhắc nhở. "
            "Các nghiên cứu gần đây về agent dựa trên LLM cho thấy mô hình có thể suy luận và gọi công cụ để hành động "
            "[1], [2], mở ra khả năng để AI <b>tham gia vận hành</b> chứ không chỉ trả lời. Tuy nhiên khi agent chạm vào "
            "tiền, dữ liệu cá nhân và email gửi khách hàng thật thì câu hỏi then chốt là <b>kiểm soát</b>: agent được tự "
            "làm gì, việc nào phải có người duyệt, và làm sao chứng minh nó không vượt quyền [5], [6], [7]."
        ),
        p(
            "Bên cạnh đó, một trung tâm đơn lẻ không đủ lớn để tự vận hành hạ tầng phần mềm. Mô hình phù hợp là phần mềm "
            "dạng dịch vụ (SaaS), nơi <b>nhiều trung tâm dùng chung một hệ thống</b> (multi-tenant) mà dữ liệu vẫn cách ly "
            "tuyệt đối [15]. Điều này đặt ra yêu cầu kỹ thuật về khả năng chịu tải, tính sẵn sàng và cách ly dữ liệu, đặc "
            "biệt khó khi trong hệ thống có agent tự sinh câu truy vấn SQL."
        ),
        p(
            "Vì vậy, đề tài chọn xây dựng một nền tảng nghiệp vụ hoàn chỉnh cho trung tâm đào tạo, trong đó các AI agent "
            "tham gia vận hành dưới sự kiểm soát của con người, đồng thời thiết kế kiến trúc để mở rộng theo tải và theo "
            "số lượng khách hàng."
        ),
    ]

    # ---------- 2
    s += [
        h1("2. TỔNG QUAN TÌNH HÌNH NGHIÊN CỨU"),
        h2("2.1. Agent dựa trên mô hình ngôn ngữ lớn"),
        p(
            "ReAct [1] kết hợp chuỗi suy luận với hành động gọi công cụ, là nền của phần lớn agent hiện nay. Toolformer [2] "
            "cho thấy LLM học được khi nào cần gọi công cụ bên ngoài. Với bài toán nhiều lĩnh vực, các khung đa tác tử như "
            "AutoGen [9] hay LangGraph [17] chia việc cho nhiều agent chuyên trách, có một agent điều phối (supervisor). "
            "Đề tài dùng kiến trúc supervisor với ba agent chuyên trách: tư vấn, phân tích dữ liệu, thao tác nghiệp vụ."
        ),
        h2("2.2. Truy xuất tăng cường (RAG) và Text-to-SQL"),
        p(
            "RAG [3] bổ sung tri thức bên ngoài vào câu trả lời để giảm bịa thông tin; khảo sát [10] tổng hợp các biến thể "
            "trong đó có tìm kiếm lai (vector kết hợp từ khoá). Đề tài gộp hai bảng xếp hạng bằng Reciprocal Rank Fusion [11] "
            "và yêu cầu trích nguồn. Với câu hỏi số liệu, Text-to-SQL được đánh giá trên các bộ Spider [4] và BIRD [12]; "
            "khi đưa vào hệ thống thật, rủi ro chính là câu SQL nguy hiểm hoặc truy cập dữ liệu ngoài quyền, nên cần nhiều "
            "lớp bảo vệ ở cả ứng dụng và cơ sở dữ liệu."
        ),
        h2("2.3. An toàn và mức tự chủ của agent"),
        p(
            'Mô hình mức tự động hoá của Parasuraman, Sheridan và Wickens [5] phân biệt các mức từ "máy chỉ gợi ý" đến '
            '"máy tự làm rồi báo". Các nghiên cứu về tấn công chèn chỉ dẫn gián tiếp [6] và danh mục rủi ro OWASP cho ứng '
            "dụng LLM [7] cho thấy không thể dựa vào prompt để giới hạn quyền của agent; ngược lại, con người duyệt quá nhiều đề xuất đúng dễ duyệt theo quán tính [8], nên số việc phải duyệt cần được giữ ở mức hợp lý. Đề tài áp dụng hướng: quyền đặt "
            "trong code và cơ sở dữ liệu, mức tự chủ cấu hình theo từng loại thao tác (L0 gợi ý, L1 chờ duyệt, L2 tự làm "
            "trong hạn mức, Cấm)."
        ),
        h2("2.4. Kiến trúc mở rộng và đa khách hàng"),
        p(
            "Các mẫu thiết kế cho hệ thống chịu lỗi như giới hạn thời gian, ngắt mạch (circuit breaker), từ chối sớm khi quá "
            "tải [14] và outbox giao dịch [13] giúp hệ thống không treo khi một thành phần chậm. Định luật Little [16] dùng "
            "để tính sức chứa từ tải và thời gian xử lý; các nguyên lý về bản sao, phân vùng và giao dịch của hệ thống dữ liệu lớn được tổng hợp trong [19]. Với SaaS, hướng dẫn kiến trúc của AWS [15] phân ba mô hình tách dữ "
            "liệu: silo (cơ sở dữ liệu riêng), bridge (schema riêng) và pool (dùng chung bảng); PostgreSQL hỗ trợ cách ly ở "
            "mức dòng bằng Row-Level Security [18]. Khi phục vụ nhiều tổ chức, hệ thống còn phải đáp ứng quy định về bảo vệ dữ liệu cá nhân [20]."
        ),
        h2("2.5. Khoảng trống"),
        p(
            "Các công trình trên thường đánh giá agent tách khỏi hệ thống nghiệp vụ (trên bộ dữ liệu chuẩn), còn phần mềm "
            "quản lý thì chưa có agent chủ động. Đề tài lấp khoảng trống này bằng một hệ thống mà agent và giao diện web "
            "<b>dùng chung một tầng luật nghiệp vụ</b>, có cơ chế kiểm soát kiểm chứng được, và kiến trúc sẵn sàng phục vụ "
            "nhiều trung tâm."
        ),
    ]

    # ---------- 3
    s += [
        h1("3. MỤC TIÊU ĐỀ TÀI"),
        h2("3.1. Mục tiêu tổng quát"),
        p(
            "Xây dựng nền tảng web quản lý trọn vòng đời học viên của trung tâm đào tạo (tuyển sinh, ghi danh, xếp lớp, "
            "điểm danh, thu học phí, chăm sóc), có các AI agent tham gia vận hành an toàn dưới sự kiểm soát của con người, "
            "và có kiến trúc mở rộng được theo tải và theo số lượng trung tâm."
        ),
        h2("3.2. Mục tiêu cụ thể"),
        *bullets(
            [
                "Xây dựng ứng dụng web hoàn chỉnh với ba khu giao diện (web công khai, cổng học viên, bàn làm việc nhân viên), 6 vai trò người dùng và luật nghiệp vụ cài trong phần mềm.",
                "Xây dựng tầng agentic: trợ lý hội thoại đa tác tử (tư vấn bằng RAG, phân tích bằng Text-to-SQL, thao tác có duyệt) và 5 agent chạy nền (công nợ, tuyển sinh, giáo vụ, chăm sóc, báo cáo).",
                "Xây dựng cơ chế kiểm soát: phân quyền cho agent như nhân viên số, mức tự chủ theo loại thao tác, hộp duyệt, danh sách thao tác cấm cố định, nhật ký kiểm toán.",
                "Thiết kế và kiểm chứng khả năng chịu tải: hệ thống không treo khi quá tải, tự hồi phục sau sự cố, mở rộng bằng cách thêm máy; mục tiêu thiết kế 1.000 request/giây.",
                "Đề xuất kiến trúc đa khách hàng (multi-tenant) cách ly dữ liệu bằng Row-Level Security, kèm lộ trình chuyển đổi và bộ kiểm thử cách ly.",
                "Đánh giá định lượng: độ chính xác của agent, độ an toàn, hiệu năng, và mức giảm thao tác thủ công.",
            ]
        ),
    ]

    # ---------- 4
    s += [
        h1("4. ĐỐI TƯỢNG VÀ PHẠM VI NGHIÊN CỨU"),
        h2("4.1. Đối tượng nghiên cứu"),
        *bullets(
            [
                "Quy trình nghiệp vụ của trung tâm đào tạo quy mô vừa: tuyển sinh, ghi danh, học vụ, tài chính, chăm sóc học viên.",
                "Kiến trúc agent dựa trên LLM: điều phối đa tác tử, RAG, Text-to-SQL, người duyệt trong vòng lặp (human-in-the-loop).",
                "Kỹ thuật hệ thống phân tán cho ứng dụng web: kiểm soát quá tải, bộ nhớ đệm, cân bằng tải, cách ly dữ liệu đa khách hàng.",
            ]
        ),
        h2("4.2. Phạm vi"),
    ]
    s += table(
        [
            ["Trong phạm vi", "Ngoài phạm vi"],
            [
                "- Web cho học viên, 5 vai trò nhân viên và khách vãng lai<br/>"
                "- Luật nghiệp vụ, máy trạng thái cho ghi danh, hoá đơn, trả góp, bảo lưu, hoàn phí<br/>"
                "- Trợ lý hội thoại, 5 agent chạy nền, hộp duyệt<br/>"
                "- Gửi email thật qua SMTP<br/>"
                "- Kiểm thử tự động, bộ đánh giá agent, kiểm thử tải, diễn tập sự cố<br/>"
                "- Thiết kế multi-tenant và lộ trình chuyển đổi",
                "- Cổng thanh toán thật (chỉ giả lập)<br/>"
                "- Ứng dụng di động riêng (web hiển thị tốt trên điện thoại)<br/>"
                "- Lớp học trực tuyến, quản lý bài giảng (LMS), tính lương, kế toán thuế<br/>"
                "- Tích hợp Zalo OA thật (thiết kế sẵn điểm nối)<br/>"
                "- Vận hành thương mại SaaS: thu phí thuê bao, tự đăng ký trung tâm<br/>"
                "- Dữ liệu khách hàng thật: toàn bộ dữ liệu là giả lập",
            ],
        ],
        [5, 5],
    )
    s += [
        p(
            "Quy mô thiết kế: một trung tâm 2.000 đến 10.000 học viên, 1 đến 3 cơ sở; trang nghiệp vụ phản hồi dưới 1 giây "
            "(p95). Dữ liệu thử nghiệm được sinh giả lập ở hai cỡ: dữ liệu demo (421 học viên) và dữ liệu cỡ thật "
            "(10.104 học viên, 50.058 đơn hàng, 1,3 triệu lượt điểm danh)."
        ),
    ]

    # ---------- 5
    s += [
        h1("5. PHƯƠNG PHÁP NGHIÊN CỨU"),
        *bullets(
            [
                "<b>Nghiên cứu tài liệu:</b> tổng hợp công trình về agent LLM, RAG, Text-to-SQL, an toàn LLM và kiến trúc SaaS (mục 2).",
                "<b>Phân tích nghiệp vụ:</b> mô hình hoá quy trình của trung tâm thành luật dạng hàm thuần và máy trạng thái cho từng đối tượng (ghi danh, hoá đơn, yêu cầu, đề xuất của agent).",
                "<b>Phát triển lặp theo giai đoạn:</b> mỗi giai đoạn kết thúc bằng một kết quả chạy được và kiểm chứng được (mục 9).",
                "<b>Thực nghiệm định lượng:</b> bộ đánh giá agent có đáp án, mô phỏng 30 ngày vận hành, kiểm thử tải bằng k6 trên dữ liệu cỡ thật, diễn tập sự cố (tắt tiến trình, tắt Redis, khoá bảng, LLM lỗi).",
                "<b>So sánh trước / sau:</b> mỗi tối ưu (truy vấn, cache, kiểm soát quá tải) được đo trước và sau, và kiểm tra kết quả trả về không đổi.",
            ]
        ),
        h2("Công nghệ sử dụng"),
    ]
    s += table(
        [
            ["Tầng", "Công nghệ"],
            ["Giao diện", "Next.js 15, React, Tailwind CSS 4, TypeScript"],
            ["Backend", "Python 3.12, FastAPI, Uvicorn; JWT; SSE cho chat trả lời dần"],
            ["Agent", "LangGraph / LangChain 1.x; LLM qua Groq (gpt-oss-120b); embedding chạy cục bộ bằng FastEmbed"],
            ["Dữ liệu", "PostgreSQL 16, pgvector, Alembic migration; Redis (bộ đếm, cache, giới hạn dùng chung)"],
            ["Triển khai", "Docker Compose, Caddy (HTTPS, cân bằng tải), PgBouncer (tuỳ chọn), GitHub Actions"],
            ["Kiểm thử", "pytest, k6, bộ đánh giá agent tự xây dựng, endpoint /metrics theo chuẩn Prometheus"],
        ],
        [2.2, 7.8],
    )

    # ---------- 6
    s += [
        h1("6. NỘI DUNG THỰC HIỆN"),
        h2("6.1. Kiến trúc tổng thể"),
        KeepTogether([Architecture(), Paragraph("Hình 1. Kiến trúc tổng thể của EduAssist Platform", CAPTION)]),
        p(
            "Quyết định trung tâm của kiến trúc là <b>luật nghiệp vụ nằm ở một chỗ duy nhất</b> (tầng Service). Giao diện "
            "web, trợ lý hội thoại và agent chạy nền đều gọi qua tầng này; agent được coi là một nhân viên số có vai trò, "
            "nên không làm được điều mà nhân viên cùng vai trò không được làm. Các thành phần chạy code (api, api-chat, "
            "worker, web) không giữ trạng thái riêng, nên có thể chạy thêm bản để chịu tải."
        ),
        h2("6.2. Các hạng mục"),
    ]
    s += table(
        [
            ["Hạng mục", "Nội dung chính"],
            [
                "<b>Nghiệp vụ</b>",
                "Tuyển sinh (khách tiềm năng, lịch hẹn, học thử), đào tạo (khoá, lớp, lịch, phòng, điểm danh, học bù, chuyển lớp), tài chính (hoá đơn, trả góp, voucher, hoàn phí), yêu cầu của học viên (bảo lưu, hoàn phí), tài khoản và phân quyền 6 vai trò, nhật ký kiểm toán.",
            ],
            [
                "<b>Trợ lý hội thoại</b>",
                "Supervisor điều phối 3 agent: tư vấn khoá học (RAG lai có trích nguồn), phân tích số liệu (Text-to-SQL qua user chỉ đọc, kiểm tra cú pháp chỉ cho SELECT, giới hạn thời gian và số dòng, che email / số điện thoại), thao tác nghiệp vụ (tạo đề xuất, dừng chờ người dùng xác nhận). Mỗi vai trò có một đồ thị agent riêng chỉ chứa công cụ được phép.",
            ],
            [
                "<b>Agent chạy nền</b>",
                "Công nợ (nhắc nợ theo bậc), tuyển sinh (chấm điểm, soạn tin tư vấn), giáo vụ (lớp thiếu sĩ số, trùng lịch), chăm sóc (học viên vắng liên tiếp), báo cáo tuần. Chạy theo lịch và theo sự kiện (outbox), có khoá chống chạy trùng.",
            ],
            [
                "<b>Kiểm soát</b>",
                "Hộp duyệt, mức tự chủ L0/L1/L2/Cấm theo loại thao tác, hạn mức theo ngày, chống trùng, danh sách thao tác cấm cố định trong code (ghi nhận thu tiền, sửa điểm, xoá dữ liệu, đổi quyền).",
            ],
            [
                "<b>Chịu tải và sự cố</b>",
                "Kiểm soát cửa vào (từ chối sớm bằng 503), giới hạn thời gian ở mọi tầng, Redis cho giới hạn và cache dùng chung, chat bất đồng bộ tách dịch vụ riêng, giới hạn số lượt gọi LLM toàn hệ thống, cân bằng tải nhiều máy, số liệu vận hành.",
            ],
            [
                "<b>Đa khách hàng</b>",
                "Thiết kế mô hình pool: cột tenant_id ở mọi bảng, Row-Level Security bắt buộc ở cơ sở dữ liệu (áp dụng cả cho SQL do agent sinh), xác định trung tâm theo tên miền con, hạn mức theo trung tâm, lộ trình 6 bước.",
            ],
        ],
        [2.4, 7.6],
    )

    # ---------- 7
    s += [
        h1("7. ĐỊNH HƯỚNG MỞ RỘNG"),
        h2("7.1. Mở rộng theo tải"),
        p(
            "Python chỉ dùng được một nhân CPU cho mỗi tiến trình, nên hệ thống mở rộng bằng nhiều tiến trình trên nhiều "
            "máy; điều kiện là các thành phần không giữ trạng thái riêng. Đã đo trên máy 2 vCPU (dữ liệu cỡ thật):"
        ),
    ]
    s += table(
        [
            ["Phép đo", "Kết quả"],
            ["Tải đều 250 request/giây, 60 giây", "0% lỗi, p95 140 ms, p99 255 ms"],
            [
                "Tăng dần tới 1.000 request/giây",
                "Phần vượt sức bị từ chối nhanh bằng 503, không treo; số request thành công gấp 38 lần bản ban đầu (1.220 lên 46.210)",
            ],
            ["Tối ưu truy vấn danh sách hoá đơn", "223 ms xuống 17 ms (kết quả trả về giống hệt)"],
            ["Tắt một tiến trình API / tắt Redis 30 giây", "0 request lỗi"],
            ["Khoá cả bảng học viên 20 giây", "Không treo; trả 503 trong lúc khoá, hồi phục khoảng 3 giây sau"],
        ],
        [4.2, 5.8],
        caption="Bảng 1. Kết quả đo tải và diễn tập sự cố (14/11/2026)",
    )
    s += [
        p(
            "Từ chi phí đo được (khoảng 4 ms CPU mỗi request), cấu hình cho 1.000 request/giây được ước lượng khoảng ba máy "
            "API 4 vCPU, một máy cơ sở dữ liệu và Redis. Con số này là ngoại suy, sẽ được kiểm chứng trên môi trường "
            "staging nhiều máy nếu có hạ tầng."
        ),
        h2("7.2. Mở rộng lên nhiều trung tâm (multi-tenant)"),
        p(
            "Đề tài so sánh ba mô hình silo, bridge và pool [15] và chọn <b>pool kết hợp Row-Level Security</b>: mọi bảng "
            "có cột tenant_id, cơ sở dữ liệu tự lọc dòng theo trung tâm của phiên làm việc (đặt bằng set_config trong từng "
            "giao dịch). Lý do chính: agent Text-to-SQL tự sinh câu truy vấn, nên việc cách ly phải do cơ sở dữ liệu ép buộc "
            "chứ không thể dựa vào việc LLM tự thêm điều kiện lọc. Mặc định là đóng: phiên chưa xác định trung tâm thì không "
            "thấy dòng nào."
        ),
    ]
    s += table(
        [
            ["Bước", "Nội dung", "Kiểm chứng"],
            ["1", "Bảng trung_tam; mọi thao tác mang tenant_id", "Toàn bộ kiểm thử hiện có vẫn qua"],
            [
                "2",
                "Thêm cột tenant_id, đổi ràng buộc UNIQUE, index, khoá ngoại theo trung tâm (không khoá bảng)",
                "Kết quả mọi endpoint không đổi",
            ],
            [
                "3",
                "Đặt trung tâm cho mỗi request, câu SQL của agent, worker, khoá Redis, hội thoại",
                "Cảnh báo khi truy vấn chạy thiếu trung tâm",
            ],
            [
                "4",
                "Bật Row-Level Security với trung tâm thứ hai",
                "Kiểm thử cách ly toàn bộ endpoint và câu hỏi tấn công cho agent",
            ],
            ["5", "Tên miền con cho từng trung tâm", "Tạo trung tâm mới bằng một lệnh"],
            [
                "6",
                "Hạn mức theo trung tâm (request, lượt LLM)",
                "Một trung tâm tải gấp 10 lần, trung tâm khác vẫn đạt p95",
            ],
        ],
        [0.8, 5.4, 3.8],
        caption="Bảng 2. Lộ trình chuyển đổi sang multi-tenant",
    )

    # ---------- 8
    s += [
        h1("8. PHƯƠNG PHÁP ĐÁNH GIÁ"),
    ]
    s += table(
        [
            ["Nhóm", "Chỉ số", "Cách đo", "Mục tiêu"],
            ["Nghiệp vụ", "Luật cài đúng", "Kiểm thử tự động cho từng luật, từng hướng chuyển trạng thái", "100% qua"],
            [
                "Agent hội thoại",
                "Điều phối, RAG, Text-to-SQL",
                "Bộ câu hỏi có đáp án, mở rộng lên khoảng 100 câu",
                "Điều phối, RAG từ 95%; SQL từ 90%",
            ],
            [
                "Agent chạy nền",
                "Đề xuất đúng, không bỏ sót",
                "Mô phỏng 30 ngày với kịch bản biết trước đáp án",
                "Đúng từ 90%; 0 ca quá hạn bị bỏ sót",
            ],
            [
                "An toàn",
                "Thao tác trái phép",
                "Kịch bản tấn công: vượt quyền, chèn chỉ dẫn, SQL nguy hiểm",
                "0 thao tác trái phép",
            ],
            [
                "Cách ly dữ liệu",
                "Lộ dữ liệu giữa trung tâm",
                "Kiểm thử cách ly mọi endpoint; câu hỏi cố ý vượt rào cho agent",
                "0 dòng của trung tâm khác",
            ],
            [
                "Hiệu năng",
                "Thời gian phản hồi, sức chịu tải",
                "k6 trên dữ liệu cỡ thật; diễn tập sự cố",
                "p95 dưới 1 giây; không treo khi quá tải",
            ],
            [
                "Hiệu quả",
                "Giảm thao tác thủ công",
                "Đếm số bước, thời gian cho 5 nghiệp vụ mẫu có / không có agent",
                "Báo cáo mức giảm đo được",
            ],
            [
                "Con người",
                "Đề xuất được duyệt không sửa",
                "Thử nghiệm với 3 đến 5 người đóng vai nhân viên",
                "Báo cáo số liệu và nhận xét",
            ],
        ],
        [1.7, 2.3, 3.8, 2.2],
        caption="Bảng 3. Chỉ số và phương pháp đánh giá",
    )
    s += [
        h2("Kết quả đã có"),
        *bullets(
            [
                "Mô phỏng 30 ngày cho agent nền: 226 ca công nợ, 0 bỏ sót, 100% đúng ngày; chăm sóc 7/7; giáo vụ 3/3; tuyển sinh 17/17; 0 email trùng, 0 nhắc nhầm người đã đóng.",
                "Đánh giá agent hội thoại (bản prototype, 01/11/2026): điều phối 100% (16 câu), RAG 100% (12 câu), Text-to-SQL 86,7% lên 93,3% khi có ví dụ mẫu động (15 câu), chặn 7/7 kịch bản tấn công. Bộ câu hỏi còn nhỏ và cần chạy lại trên schema mới.",
                "Khoảng 325 kiểm thử tự động (luật, phân quyền, API, tích hợp với PostgreSQL thật).",
            ]
        ),
    ]

    # ---------- 9
    s += [
        h1("9. KẾ HOẠCH THỰC HIỆN"),
    ]
    s += table(
        [
            ["Tuần", "Nội dung", "Kết quả kiểm chứng được", "Trạng thái"],
            [
                "1 - 3",
                "Thiết kế schema, migration, tầng Service đào tạo và ghi danh, khung web, đăng nhập",
                "Ghi danh một học viên từ web, có kiểm tra sĩ số",
                "Đã xong",
            ],
            [
                "4 - 7",
                "Tài chính, học vụ, tuyển sinh, cổng học viên, web công khai",
                "Trọn vòng đời: khách mới, ghi danh, thanh toán, học, hoàn thành",
                "Đã xong",
            ],
            [
                "8 - 9",
                "Trợ lý hội thoại nhúng trong web, hộp duyệt, nhật ký kiểm toán",
                "Ra lệnh trong chat tạo đề xuất; duyệt xong thì thực hiện",
                "Đã xong",
            ],
            ["10 - 12", "Worker, outbox, 5 agent nền, mức tự chủ", "Mô phỏng 30 ngày đạt chỉ số ở mục 8", "Đã xong"],
            ["13", "Kiểm thử tải, diễn tập sự cố, kiến trúc chịu tải", "Bảng 1", "Đã xong"],
            [
                "14",
                "Thiết kế multi-tenant; mở rộng bộ đánh giá agent lên khoảng 100 câu và chạy lại",
                "Tài liệu thiết kế; bảng kết quả đánh giá mới",
                "Đang làm",
            ],
            [
                "15",
                "Thử nghiệm với người dùng; đo giảm thao tác thủ công; kiểm thử bảo mật",
                "Số liệu và nhận xét của 3 đến 5 người",
                "Chưa làm",
            ],
            [
                "16",
                "Hoàn thiện báo cáo, tài liệu triển khai, video demo",
                "Báo cáo, bản chạy được bằng một lệnh",
                "Chưa làm",
            ],
        ],
        [1.1, 4.1, 3.5, 1.3],
        caption="Bảng 4. Kế hoạch 16 tuần và tiến độ (cập nhật tháng 11/2026)",
    )
    s += [
        p(
            "Ưu tiên khi thiếu thời gian: giữ nguyên kết quả đánh giá agent và thử nghiệm người dùng; phần multi-tenant "
            "dừng ở mức thiết kế và lộ trình (không triển khai) mà không ảnh hưởng mục tiêu chính."
        ),
    ]

    # ---------- 10
    s += [
        h1("10. KẾT QUẢ DỰ KIẾN"),
        *bullets(
            [
                "Sản phẩm phần mềm chạy được bằng một lệnh (Docker Compose), gồm web, API, trợ lý hội thoại, worker và dữ liệu giả lập; mã nguồn công khai kèm tài liệu triển khai production.",
                "Bộ đánh giá có thể chạy lại: kiểm thử tự động, bộ câu hỏi cho agent, mô phỏng 30 ngày, kịch bản kiểm thử tải và diễn tập sự cố.",
                "Tài liệu thiết kế kiến trúc chịu tải và kiến trúc multi-tenant, có số đo minh chứng.",
                "Báo cáo đồ án và video demo các luồng nghiệp vụ chính.",
            ]
        ),
        h2("Đóng góp của đề tài"),
        *bullets(
            [
                "Một cách tổ chức để agent LLM thực hiện nghiệp vụ thật: agent đi qua cùng tầng luật với con người, quyền nằm trong code và cơ sở dữ liệu, mức tự chủ cấu hình theo loại thao tác.",
                "Số liệu thực nghiệm về hành vi của hệ thống agentic khi quá tải và khi thành phần bên ngoài (LLM, Redis, cơ sở dữ liệu) gặp sự cố.",
                "Phân tích cách ly dữ liệu đa khách hàng khi trong hệ thống có agent tự sinh SQL.",
            ]
        ),
    ]

    # ---------- 11
    s += [
        h1("11. DỰ KIẾN BỐ CỤC BÁO CÁO"),
    ]
    s += table(
        [
            ["Chương", "Nội dung"],
            ["Mở đầu", "Lý do chọn đề tài, mục tiêu, đối tượng, phạm vi, phương pháp"],
            [
                "Chương 1",
                "Tổng quan: nghiệp vụ trung tâm đào tạo; agent LLM, RAG, Text-to-SQL; an toàn và mức tự chủ; kiến trúc SaaS",
            ],
            [
                "Chương 2",
                "Phân tích yêu cầu và thiết kế: tác nhân, chức năng, luật nghiệp vụ, máy trạng thái, mô hình dữ liệu",
            ],
            ["Chương 3", "Thiết kế tầng agentic: supervisor và agent hội thoại, agent nền, hộp duyệt, cơ chế an toàn"],
            ["Chương 4", "Kiến trúc hệ thống: triển khai, chịu tải, chịu lỗi, định hướng multi-tenant"],
            [
                "Chương 5",
                "Cài đặt và thực nghiệm: kết quả đánh giá agent, mô phỏng, kiểm thử tải, diễn tập sự cố, thử nghiệm người dùng",
            ],
            ["Kết luận", "Kết quả đạt được, hạn chế, hướng phát triển"],
        ],
        [1.6, 8.4],
    )

    # ---------- 12
    s += [
        h1("12. RỦI RO VÀ CÁCH GIẢM THIỂU"),
    ]
    s += table(
        [
            ["Rủi ro", "Giảm thiểu"],
            [
                "LLM trả lời sai hoặc bị chèn chỉ dẫn, thực hiện thao tác ngoài ý muốn",
                "Quyền trong code và cơ sở dữ liệu; thao tác quan trọng chờ duyệt; danh sách cấm cố định; bộ kịch bản tấn công",
            ],
            [
                "Nhà cung cấp LLM giới hạn hạn mức hoặc lỗi",
                "Thử lại chỉ với lỗi tạm thời; giới hạn thời gian 45 giây mỗi câu; agent nền có bản mẫu do code soạn; trang nghiệp vụ không phụ thuộc LLM",
            ],
            [
                "Lộ dữ liệu giữa các trung tâm khi multi-tenant",
                "Row-Level Security bắt buộc, mặc định đóng; kiểm thử cách ly toàn bộ endpoint",
            ],
            [
                "Thiếu hạ tầng nhiều máy để đo 1.000 request/giây",
                "Đo trên một máy, tính sức chứa từ chi phí mỗi request; ghi rõ phần ngoại suy",
            ],
            [
                "Dữ liệu giả lập không phản ánh đủ thực tế",
                "Sinh dữ liệu cỡ thật theo phân bố nghiệp vụ; thử nghiệm với người đóng vai nhân viên",
            ],
        ],
        [4, 6],
    )

    # ---------- tài liệu tham khảo
    refs = [
        'S. Yao, J. Zhao, D. Yu, N. Du, I. Shafran, K. Narasimhan, Y. Cao, "ReAct: Synergizing Reasoning and Acting in Language Models," in <i>Proc. ICLR</i>, 2023.',
        'T. Schick et al., "Toolformer: Language Models Can Teach Themselves to Use Tools," in <i>Proc. NeurIPS</i>, 2023.',
        'P. Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," in <i>Proc. NeurIPS</i>, 2020.',
        'T. Yu et al., "Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task," in <i>Proc. EMNLP</i>, 2018.',
        'R. Parasuraman, T. B. Sheridan, C. D. Wickens, "A model for types and levels of human interaction with automation," <i>IEEE Trans. Systems, Man, and Cybernetics - Part A</i>, vol. 30, no. 3, pp. 286-297, 2000.',
        'K. Greshake et al., "Not What You\'ve Signed Up For: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection," in <i>Proc. ACM AISec</i>, 2023.',
        "OWASP Foundation, <i>OWASP Top 10 for Large Language Model Applications</i>, 2025.",
        'R. Parasuraman, D. H. Manzey, "Complacency and Bias in Human Use of Automation: An Attentional Integration," <i>Human Factors</i>, vol. 52, no. 3, pp. 381-410, 2010.',
        'Q. Wu et al., "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation," arXiv:2308.08155, 2023.',
        'Y. Gao et al., "Retrieval-Augmented Generation for Large Language Models: A Survey," arXiv:2312.10997, 2023.',
        'G. V. Cormack, C. L. A. Clarke, S. Büttcher, "Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods," in <i>Proc. ACM SIGIR</i>, 2009.',
        'J. Li et al., "Can LLM Already Serve as A Database Interface? A BIg Bench for Large-Scale Database Grounded Text-to-SQLs," in <i>Proc. NeurIPS</i>, 2023.',
        "C. Richardson, <i>Microservices Patterns</i>. Manning, 2018 (mẫu Transactional Outbox).",
        "M. T. Nygard, <i>Release It! Design and Deploy Production-Ready Software</i>, 2nd ed. Pragmatic Bookshelf, 2018.",
        "Amazon Web Services, <i>SaaS Lens - AWS Well-Architected Framework</i> (mô hình silo, bridge, pool).",
        'J. D. C. Little, "A Proof for the Queuing Formula: L = λW," <i>Operations Research</i>, vol. 9, no. 3, pp. 383-387, 1961.',
        "LangChain, <i>LangGraph Documentation</i>, https://langchain-ai.github.io/langgraph/.",
        'PostgreSQL Global Development Group, <i>PostgreSQL 16 Documentation</i>, mục 5.8 "Row Security Policies".',
        "M. Kleppmann, <i>Designing Data-Intensive Applications</i>. O'Reilly, 2017.",
        "Chính phủ nước CHXHCN Việt Nam, <i>Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân</i>, 2023.",
    ]
    s += [CondPageBreak(6 * cm), h1("TÀI LIỆU THAM KHẢO")]
    s += [Paragraph(f"[{i}]&nbsp;&nbsp;{r}", REF) for i, r in enumerate(refs, 1)]

    # ---------- xác nhận
    sign = Table(
        [
            [
                Paragraph("<b>XÁC NHẬN CỦA<br/>GIẢNG VIÊN HƯỚNG DẪN</b>", CELL_C),
                Paragraph(
                    f"<i>{THONG_TIN['noi_lam']}, ngày ..... {THONG_TIN['thang_nam']}</i><br/><b>SINH VIÊN THỰC HIỆN</b>",
                    ParagraphStyle("sc", parent=CELL, alignment=TA_CENTER),
                ),
            ],
            [
                Paragraph(
                    "<i>(Ký và ghi rõ họ tên)</i>",
                    ParagraphStyle("si", parent=CELL, alignment=TA_CENTER, fontName="Times-I"),
                ),
                Paragraph(
                    "<i>(Ký và ghi rõ họ tên)</i>",
                    ParagraphStyle("si2", parent=CELL, alignment=TA_CENTER, fontName="Times-I"),
                ),
            ],
            ["", ""],
        ],
        colWidths=[CONTENT_W / 2] * 2,
        rowHeights=[None, None, 2.6 * cm],
    )
    sign.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    s += [CondPageBreak(7 * cm), Spacer(1, 14), sign]

    # đề mục không nằm cô đơn cuối trang
    story = []
    for f in s:
        if isinstance(f, Paragraph) and f.style in (H1, H2):
            story.append(CondPageBreak(5.5 * cm if f.style is H1 else 3 * cm))
        story.append(f)

    doc = BaseDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=LEFT,
        rightMargin=RIGHT,
        topMargin=TOP,
        bottomMargin=BOTTOM,
        title="Đề cương đồ án tốt nghiệp - EduAssist Platform",
        author=THONG_TIN["sinh_vien"].strip(". ") or "EduAssist",
        subject="Nền tảng quản lý trung tâm đào tạo tích hợp hệ đa tác tử AI",
    )
    frame = Frame(
        LEFT,
        BOTTOM,
        CONTENT_W,
        PAGE_H - TOP - BOTTOM,
        id="f",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc.addPageTemplates(
        [
            PageTemplate(id="cover", frames=[frame], onPage=cover),
            PageTemplate(id="body", frames=[frame], onPage=footer),
        ]
    )
    doc.build(story)
    print(f"Đã tạo {OUT}")


if __name__ == "__main__":
    build()
