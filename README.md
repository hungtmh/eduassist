# EduAssist Platform 🎓

**Nền tảng quản lý và vận hành trung tâm đào tạo, tích hợp hệ đa tác tử AI** – theo đề xuất đồ án
[`docs/EduAssist_Platform_Proposal.pdf`](docs/EduAssist_Platform_Proposal.pdf); đề cương đồ án tốt nghiệp:
[`docs/EduAssist_De_Cuong_DATN.pdf`](docs/EduAssist_De_Cuong_DATN.pdf) (sinh bằng `docs/de_cuong.py`).
Hệ thống quản lý trọn vòng đời học viên (tuyển sinh → ghi danh → xếp lớp → điểm danh → thu học phí → chăm sóc),
và **agent AI tham gia vận hành**: tự phát hiện việc cần làm, soạn sẵn, thực hiện trong hạn mức hoặc chờ người duyệt.

> Trung tâm "Ánh Dương", học viên, đơn hàng và chính sách đều là **dữ liệu giả lập**.

`Next.js 15 + Tailwind 4` · `FastAPI` · `PostgreSQL 16 + pgvector` · `Alembic` · `LangGraph / LangChain 1.x` · `Docker` · `GitHub Actions`

## Khác gì so với prototype

Prototype (tag `prototype`) là một chatbot Chainlit. Đồ án biến nó thành nền tảng nghiệp vụ:

| Prototype | Nền tảng (bản này) |
|---|---|
| Giao diện chat Chainlit | Web Next.js đủ phân hệ, Copilot nhúng ở mọi màn hình |
| Tool của agent tự truy vấn / ghi DB | **Tầng Service** chứa toàn bộ luật nghiệp vụ; web và agent đều gọi qua đây |
| 3 vai trò | 6 vai trò: học viên, tư vấn viên, giáo vụ, kế toán, giảng viên, quản lý |
| Agent chỉ chạy khi có người hỏi | **5 agent chạy nền** (công nợ, tuyển sinh, giáo vụ, chăm sóc, báo cáo) + worker, outbox sự kiện |
| Duyệt bằng nút trong chat | **Hộp duyệt** + **mức tự chủ L0/L1/L2/Cấm theo từng loại thao tác** |
| 7 bảng, tạo bằng 1 file SQL | ~25 bảng, máy trạng thái, Alembic migration, audit log |

## Ba khu giao diện

| Khu | Đường dẫn | Ai dùng |
|---|---|---|
| Web công khai | `/`, `/khoa-hoc`, `/lich-khai-giang`, `/gioi-thieu`, `/chinh-sach`, `/dang-ky-tu-van` | Khách tìm khoá học (không đăng nhập, render phía server, có SEO và chatbot tư vấn) |
| Cổng học viên | `/portal` | Học viên (khung riêng, ưu tiên điện thoại) |
| Bàn làm việc | `/hom-nay`, `/dashboard`, `/inbox`, `/leads`, `/lich`... | Tư vấn, giáo vụ, kế toán, giảng viên, quản lý |

Form tư vấn trên web tạo khách tiềm năng nguồn `website` → agent tuyển sinh chấm điểm và soạn tin tư vấn như khách nhập tay.

## Kiến trúc

```
Next.js (web) ──REST + SSE──► FastAPI (JWT, 6 vai trò)
                                 ├─ REST nghiệp vụ ───────────┐
                                 └─ Chat SSE → Supervisor ──┐ │
                                      (advisor/analytics/action)│
Worker ── outbox + lịch ──► 5 agent nền ──────────────────────┤
                                                              ▼
                     Tầng Service (luật, máy trạng thái, phân quyền, audit, outbox)
                       ├─ proposals.submit ─► mức tự chủ: L0 gợi ý · L1 chờ duyệt · L2 tự làm trong hạn mức · Cấm
                       ▼
PostgreSQL: nghiệp vụ · pgvector · checkpoint/store LangGraph · de_xuat_agent · outbox · audit_log
```

## Những quyết định kỹ thuật chính

**1. Luật nghiệp vụ ở một chỗ duy nhất** ([`services/`](src/eduassist/services)). Mọi hàm nhận `actor` và tự
`require()` quyền. Agent là `Actor(is_agent=True)` có vai trò như nhân viên số, nên **không làm được điều nhân viên
cùng vai trò không được làm**. Thêm danh sách **Cấm cố định trong code** (`AGENT_FORBIDDEN`): ghi nhận đã thu tiền,
sửa điểm, xoá dữ liệu, đổi quyền – kể cả quản lý ra lệnh qua chat cũng không làm được.

**2. Luật dạng hàm thuần, test từng luật** ([`rules.py`](src/eduassist/services/rules.py)): trả góp chỉ cho khoá từ
5 triệu; ưu đãi không cộng dồn, voucher cộng tối đa 15%; hoàn phí 100/70/0% theo thời điểm huỷ; bảo lưu 1 lần ≤ 6
tháng; chuyển lớp miễn phí 1 lần; trùng lịch = cùng ca + chung thứ + giao khoảng ngày; chứng nhận cần chuyên cần ≥ 80%
và điểm ≥ 50; máy trạng thái cho khách, ghi danh, lớp, đề xuất.

**3. Hộp duyệt + mức tự chủ theo loại thao tác** ([`proposals.py`](src/eduassist/services/proposals.py)).
Agent chỉ gọi `proposals.submit(...)`. `du_lieu` (người nhận, số tiền) **do code tính**, đúng thứ người duyệt thấy;
lúc thực thi kiểm tra lại (VD: đã đóng tiền trong lúc chờ thì bỏ qua). Người duyệt sửa được trường cho phép hoặc bỏ
bớt mục; thực thi chạy bằng vai trò của bên đề xuất (quản lý duyệt voucher 25% do tư vấn viên ra lệnh → vẫn thất bại
vì hạn mức 15% của tư vấn viên). L2 vượt hạn mức ngày tự chuyển sang chờ duyệt. Chống trùng hai mức: khoá đề xuất và
"mục này đã nằm trong đề xuất nào chưa".

**4. LLM quyết định ý định, code quyết định dữ liệu.** Agent nền lọc bằng SQL, tính bằng code; LLM chỉ viết đoạn
lời văn (thư tư vấn, hỏi thăm, nhận xét báo cáo), có **bản mẫu dự phòng** và **kiểm tra không bịa số**
([`background/base.py`](src/eduassist/background/base.py)).

**5. Outbox trong cùng transaction** + worker `SKIP LOCKED`: thay đổi dữ liệu, audit và sự kiện cùng commit hoặc
cùng huỷ. Mỗi request API là một transaction.

**6. Đồng hồ nghiệp vụ** (`core.today()/now()`): mọi luật dùng ngày nghiệp vụ, nên mô phỏng 30 ngày chỉ là đặt lại
đồng hồ trong một transaction rồi rollback.

Kế thừa nguyên từ prototype: Text-to-SQL 4 lớp an toàn (nay đọc thêm 4 bảng mới), RAG hybrid có kiểm chứng nguồn,
bộ nhớ dài hạn, vòng học lại từ 👍 của nhân viên, Langfuse tuỳ chọn.

## Các agent nền

| Agent | Kích hoạt | Làm gì | Mức mặc định |
|---|---|---|---|
| Công nợ | hằng ngày | Đánh dấu quá hạn; nhắc theo bậc: trước hạn 3 ngày → quá 1 → quá 7 ngày; quá 14 ngày đề xuất tạm dừng | Nhắc lần đầu L2 (≤100/ngày), lần sau L1, tạm dừng L1 |
| Tuyển sinh | khách mới + hằng ngày | Chấm điểm khách (luật minh bạch), gợi ý lớp còn chỗ, soạn tin tư vấn; giao việc khi khách quá 3 ngày chưa liên hệ | Tin tư vấn L1, việc nhắc L2 |
| Giáo vụ | hằng ngày + đổi lịch | Lớp thiếu sĩ số (≤14 ngày: cảnh báo; ≤7 ngày: gộp nếu có lớp cùng khoá, không thì huỷ); trùng GV/phòng | Cảnh báo L0, gộp/huỷ L1 |
| Chăm sóc | điểm danh / nhập điểm | Vắng ≥2 buổi liên tiếp hoặc điểm giữa khoá < 50 → thư hỏi thăm + báo giảng viên | L1 |
| Báo cáo | thứ Hai | Số liệu tuần, điểm bất thường (±30%), nhận xét AI có kiểm chứng số | L2 |

Mức tự chủ đổi được ở trang **Agent & mức tự chủ** (chỉ quản lý); agent không tự đổi được.

## Chạy thử

Cần: Docker, [uv](https://docs.astral.sh/uv/), Node 22, Groq API key miễn phí (https://console.groq.com/keys).

```bash
cp .env.example .env              # điền GROQ_API_KEY, JWT_SECRET
```

**Toàn bộ bằng Docker**
```bash
docker compose --profile app up -d --build
# Web http://localhost:3000 · API http://localhost:8000/docs · Email đã gửi http://localhost:8025
```

**Dev**
```bash
docker compose up -d db mailpit
uv sync --all-groups
uv run eduassist-setup                    # alembic upgrade head, role read-only, dữ liệu kịch bản, vector
uv run uvicorn eduassist.api.main:app --reload --port 8000
uv run eduassist-worker                   # agent nền (hoặc --once / --agent cong_no)
cd web && npm install && npm run dev      # http://localhost:3000  (NEXT_PUBLIC_API_URL nếu API khác cổng 8000)
```

Redis không bắt buộc khi chạy 1 tiến trình (không có `REDIS_URL` thì giới hạn lượt gọi và cache nằm trong RAM). Trên
Windows, chạy API trên máy thì giữ `--reload`: chat async dùng psycopg async, cần SelectorEventLoop (uvicorn chỉ dùng
loop này khi có `--reload` hoặc nhiều worker); chạy trong Docker thì không cần để ý.

**Chịu tải:** test tải, cách mở rộng lên 1.000 req/s và kết quả diễn tập sự cố ở
[`docs/SCALING_PLAN.md`](docs/SCALING_PLAN.md) và [`loadtest/README.md`](loadtest/README.md).

**Nhiều trung tâm dùng chung một hệ thống (multi-tenant):** định hướng, phương án tách dữ liệu bằng Row-Level
Security và lộ trình chuyển đổi ở [`docs/MULTI_TENANT.md`](docs/MULTI_TENANT.md) (chưa làm).

**Production** (HTTPS, sao lưu, không dữ liệu demo): xem [`docs/DEPLOY.md`](docs/DEPLOY.md) và
[`docs/PRODUCTION_CHECKLIST.md`](docs/PRODUCTION_CHECKLIST.md). `DEMO_MODE=false` tắt dữ liệu giả lập và nút demo;
`APP_ENV=production` từ chối chạy nếu còn khoá mặc định.

Tài khoản demo khi `DEMO_MODE=true` (mật khẩu `demo123`): `quanly`, `ketoan`, `tuvan`, `nhanvien`, `giaovu`, `giangvien`, `hocvien`.
Trang đăng nhập có nút điền sẵn từng vai trò.

Kịch bản demo nhanh: đăng nhập `quanly` → **Agent** → *Chạy ngay* agent công nợ → **Hộp duyệt** xem đề xuất tạm dừng
học (căn cứ, số tiền do code tính) → *Duyệt* → **Nhật ký** thấy dòng "duyệt bởi quanly" → mở **Copilot**, gõ
"Cấp voucher 10% cho học viên id 7" → duyệt ngay trên thẻ đề xuất trong chat.

## Kiểm thử & đánh giá

```bash
uv run pytest                          # 233 test: luật thuần, phân quyền, API (không cần DB/LLM)
uv run pytest -m integration           # 92 test với Postgres thật (+ Redis nếu có), mỗi test rollback
uv run eduassist-eval background       # mô phỏng 30 ngày cho agent nền (không gọi LLM, DB không đổi)
uv run eduassist-eval all              # + các bộ eval LLM của prototype
cd web && npm run build                # type-check + build giao diện
```

**Mô phỏng 30 ngày (11/11–10/12/2026)** – mỗi ngày: học viên đóng tiền ngẫu nhiên (~6%/ngày), giảng viên điểm danh
(5 học viên được cài sẵn bỏ học), khách mới đến; worker chạy; người duyệt giả lập duyệt mọi đề xuất. Đáp án mỗi ngày
tính bằng SQL riêng từ dữ liệu, so với đề xuất agent tạo:

| Chỉ số | Kết quả |
|---|---|
| Công nợ – ca cần xử lý / bỏ sót / đúng hạn / đề xuất sai | 226 ca · **0 bỏ sót** · 100% đúng ngày · 100% chính xác |
| Chăm sóc – học viên vắng ≥2 buổi liên tiếp được hỏi thăm | 7/7 |
| Giáo vụ – lớp thiếu sĩ số được cảnh báo / đề xuất | 3/3 |
| Tuyển sinh – khách quá 3 ngày chưa liên hệ được giao việc | 17/17 |
| Email trùng trong 24h · nhắc người đã đóng · lần chạy agent lỗi | **0 · 0 · 0** |

Ghi chú trung thực: đáp án dùng cùng ngưỡng nghiệp vụ với agent (bậc −3/1/7/14 ngày), nên bộ này đo **đường ống**
(lọc, chống trùng, mức tự chủ, thực thi, bỏ qua người đã đóng) chứ không đo "agent có hiểu chính sách không". Lần chạy
đầu đạt 79,6% chính xác vì đáp án chỉ tính ngày *chạm đúng* bậc, quên ngày đầu agent phải bắt kịp các đợt đã quá hạn
từ trước – đã sửa cách tính đáp án. Kiểm tra giao diện bắt được một lỗi thật: đợt đã đóng một nửa vẫn bị nhắc với số
tiền gốc – đã sửa bằng view `dot_con_lai` dùng chung cho nhắc nợ, dashboard và báo cáo (có test hồi quy).

Kết quả eval LLM của prototype (01/11/2026, `gpt-oss-120b`): điều phối 100% (16 câu), RAG 100% (12), Text-to-SQL
86,7% → 93,3% khi có few-shot động (15), bảo mật chặn 7/7. Chưa chạy lại sau khi đổi schema/vai trò.

## Cấu trúc

```
src/eduassist/
  services/    core (Actor, quyền, audit, outbox, đồng hồ), rules (luật thuần), crm, training, enrollment,
               finance, students (+cổng học viên), notifications, proposals (hộp duyệt), actions, reports
  background/  5 agent nền, khung chạy, worker (outbox + lịch)
  agents/      supervisor + advisor/analytics/action (action tạo đề xuất qua tầng Service)
  api/         main (chat SSE, auth), platform (REST nghiệp vụ)
  evals/       eval LLM của prototype + background.py (mô phỏng N ngày)
  seed/        dữ liệu giả lập gốc + platform.py (dữ liệu theo kịch bản)
migrations/    Alembic: 0001 schema prototype · 0002 nền tảng · 0003 view dot_con_lai
web/           Next.js: dashboard, hộp duyệt, tuyển sinh, lớp học, học viên, tài chính, yêu cầu, agent, nhật ký,
               cổng học viên, Copilot
```

Thiết kế giao diện theo bộ skill `jakubkrehel/skills` (layout, typography, colors, UI, writing, accessibility):
token màu OKLCH theo vai trò, tương phản đo bằng công thức (không ước lượng) – ghi trong `web/src/app/globals.css`;
màu biểu đồ qua `validate_palette.js`; `:focus-visible`, dialog native `showModal()`, vùng `role="status"` cho toast,
link bỏ qua tới nội dung, chuyển động chỉ khi không bật giảm chuyển động.

## Giới hạn và phần chưa làm so với đề xuất

- **Chưa có:** kiểm thử tải 100 người dùng, thử nghiệm với 3–5 người dùng thật, mở rộng bộ eval LLM lên ~100 câu,
  chế độ tối, đo "giảm thao tác thủ công". Eval LLM cũ chưa chạy lại sau khi đổi vai trò/schema.
- Tầng Service dùng psycopg + SQL thuần (giữ nhất quán với code agent của prototype); Alembic quản lý migration nhưng
  không dùng ORM SQLAlchemy như đề xuất ghi.
- Seed xếp giảng viên/phòng theo kiểu tham lam nên ngoài cặp trùng lịch cài sẵn còn vài cặp trùng thật – agent giáo vụ
  phát hiện đúng, nhưng dữ liệu nên được làm sạch hơn.
- Cổng thanh toán, Zalo OA: ngoài phạm vi (như đề xuất).
- Kiểm tra giao diện trên trình duyệt ở 1920px và 486px (không tràn ngang); chưa kiểm ở 320px, zoom 200% và bằng
  trình đọc màn hình.
