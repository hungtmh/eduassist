# EduAssist – Những gì còn thiếu để lên production

> Rà soát ngày 12/11/2026 trên nhánh `platform`, dựa trên đọc code (API, web, Docker, CI, schema).
> Chưa chạy hệ thống để kiểm tra từng mục; mục nào ghi "kiểm tra lại" là tôi chưa xác nhận chắc.

## Tiến độ

**Đợt 1 đã làm (12/11/2026).** Kiểm tra: 265 test (264 qua, 1 bỏ qua do thiếu dữ liệu; thêm 63 test mới), mô phỏng 30 ngày vẫn 100%, `npm run build`
qua, chạy thử trên trình duyệt các luồng tạo tài khoản, bắt đổi mật khẩu, khoá tài khoản, kích hoạt học viên qua email.

| Mục | Trạng thái | Ở đâu |
|---|---|---|
| 2.1 Tài khoản demo | ✅ `DEMO_MODE=false`: không seed, ẩn nút demo, khoá tài khoản demo còn `demo123`, tạo quản lý đầu tiên | `scripts/setup.py`, `login/page.tsx` |
| 2.2 Khoá mặc định | ✅ `APP_ENV=production` từ chối khởi động nếu còn khoá mặc định / yếu | `config.py` |
| 2.3 Dò mật khẩu | ✅ Giới hạn theo IP + khoá tạm 15 phút sau 5 lần sai | `services/accounts.py`, `api/ratelimit.py` |
| 2.4 Đổi / quên mật khẩu | ✅ Đổi, quên (link email 30 phút, dùng một lần), bắt đổi lần đầu, quy tắc độ mạnh | `/doi-mat-khau`, `/quen-mat-khau`, `/dat-mat-khau` |
| 2.6 Thu hồi phiên | ✅ Đọc tài khoản từ DB mỗi request, `token_version`; "Đăng xuất mọi thiết bị" | `api/auth.py` |
| 2.8 Header bảo mật | ✅ CSP (web), HSTS và các header khác (Caddy) | `next.config.ts`, `deploy/Caddyfile` |
| 2.11 `/docs` công khai | ✅ Tắt ở production | `api/main.py` |
| 3.1 Quản lý người dùng | ✅ Trang **Người dùng** | `(app)/users` |
| 3.2 Tài khoản học viên | ✅ Nút *Cấp tài khoản* trong hồ sơ học viên, email chỉ chứa link kích hoạt | `student-account.tsx` |
| 3.3, 3.4 Khoá học, cơ sở, phòng, giảng viên | ✅ Trang **Danh mục đào tạo**; khoá ngừng bán không mở lớp mới | `(app)/catalog` |
| 4.4a SMTP thật | ✅ STARTTLS / SSL + đăng nhập (cần bạn có tài khoản email) | `notifications.py` |
| 4.5a Phân trang | ✅ `limit/offset` + `X-Total-Count`, nút "Tải thêm" ở 7 trang | `core.paginate`, `use-paged.ts` |
| 6.1 HTTPS | ✅ Caddy tự xin chứng chỉ (cần tên miền) | `docker-compose.prod.yml` |
| 6.2 Sao lưu | ✅ Hằng ngày, đã thử khôi phục được. ⚠️ Chép ra ngoài máy chủ: bạn tự cấu hình | `deploy/backup.sh`, `deploy/restore.sh` |
| 6.3 Cổng DB | ✅ Không mở ở production | `docker-compose.prod.yml` |
| 6.6 Theo dõi lỗi | ✅ Sentry tuỳ chọn cho API + worker (web chưa có) | `observability.py` |
| 6.8 Múi giờ | ✅ `Asia/Ho_Chi_Minh` cho container và PostgreSQL (cả compose dev) | `Dockerfile`, compose |
| 6.12 Image web | ✅ `output: "standalone"` | `web/Dockerfile` |
| 8.1 Dữ liệu gửi LLM | ✅ Che email/SĐT trong kết quả SQL; agent gửi email theo id, không thấy địa chỉ; agent nền không gửi tên. ⚠️ Nội dung người dùng tự gõ vào chat vẫn đi tới LLM | `security/pii.py` |

**Đợt 2 đã làm (12/11/2026).** Kiểm tra: 287 test (286 qua, 1 bỏ qua; thêm 22 test mới), build production qua. Chạy thử trên
trình duyệt: trang chủ, chi tiết khoá học, gửi form tư vấn → khách mới nguồn website → agent tuyển sinh tự chấm điểm;
chatbot khách vãng lai gọi LLM thật, trả lời đúng học phí và lớp còn chỗ; trang Hôm nay và Thời khoá biểu của giảng viên;
học viên mở trang nhân viên bị đưa về cổng học viên.

| Mục | Trạng thái | Ở đâu |
|---|---|---|
| 1.1 Trang chủ | ✅ Hero, danh mục, khoá sắp khai giảng, cam kết (lấy đúng từ tài liệu chính sách), lớp còn chỗ, form tư vấn | `(public)/page.tsx` |
| 1.2 Danh mục khoá học | ✅ Lọc theo lĩnh vực, trình độ | `(public)/khoa-hoc` |
| 1.3 Chi tiết khoá học | ✅ Đối tượng, kết quả, lộ trình, lớp sắp mở còn bao nhiêu chỗ, giảng viên, trả góp, khoá liên quan | `(public)/khoa-hoc/[slug]` |
| 1.4 Form tư vấn | ✅ Bẫy bot, giới hạn theo IP, chống trùng số điện thoại, lưu thời điểm đồng ý, báo người phụ trách, kích hoạt agent tuyển sinh | `services/public.py` |
| 1.5 Lịch khai giảng | ✅ Theo tháng, lọc lĩnh vực và ca | `(public)/lich-khai-giang` |
| 1.6 Chatbot khách vãng lai | ✅ Chỉ tra chính sách và khoá học, không lưu hội thoại, giới hạn theo IP và tổng số lượt | `public_chat.py` |
| 1.7 Trang chính sách | ✅ Đọc thẳng từ `data/policies` (cùng nguồn với RAG) | `(public)/chinh-sach` |
| 1.8 Giới thiệu, giảng viên, cơ sở, liên hệ | ✅ Giảng viên có thể tắt "hiện công khai" | `(public)/gioi-thieu` |
| 1.9 Quyền riêng tư, điều khoản | ⚠️ Có bản mẫu, **cần người có chuyên môn pháp lý rà soát** | `(public)/quyen-rieng-tu`, `dieu-khoan` |
| 1.10 SEO | ✅ Metadata từng trang, canonical, Open Graph, `sitemap.xml`, `robots.txt`, JSON-LD `Course`; trang nội bộ `noindex` | `sitemap.ts`, `robots.ts` |
| Tách 3 khu | ✅ `(public)` web công khai · `(portal)` cổng học viên có khung riêng · `(app)` bàn làm việc nhân viên | `app/` |
| 3.10 Trang chủ theo vai trò | ✅ **Việc hôm nay** cho giảng viên, tư vấn, kế toán, giáo vụ | `(app)/hom-nay` |
| 4.2a Thời khoá biểu dạng lịch | ✅ Tuần × ca, lọc giảng viên và phòng, đánh dấu buổi chưa điểm danh; giảng viên chỉ xem lịch mình | `(app)/lich` |
| Nội dung trang khoá học | ✅ Quản lý sửa đường dẫn, mô tả ngắn, lộ trình, tiểu sử giảng viên ở trang Danh mục | `(app)/catalog` |

Còn lại của Đợt 2: ảnh thật cho khoá học và giảng viên (bìa hiện là hình vẽ theo danh mục; cần chỗ lưu file, mục 4.5f),
blog / câu hỏi thường gặp (1.11), đăng ký và thanh toán online (1.12).

**Test tải và chống sập (14/11/2026).** Test tải bằng k6 (`loadtest/`) cho thấy API **treo cứng ở khoảng 100 req/s**
do hai lỗi deadlock (pool kết nối và thread pool). Đã sửa cả hai, thêm kiểm soát cửa vào (vượt sức thì trả 503 nhanh,
tự hồi phục), hạn chờ kết nối và hạn thời gian SQL, index cho 23 khoá ngoại, trả JSON bằng orjson. Cùng bài test tăng
dần tới 1.000 req/s: từ 1.220 lên 42.037 request thành công; máy 2 vCPU chịu khoảng 300 req/s. Kế hoạch đạt
1.000 req/s: [`SCALING_PLAN.md`](SCALING_PLAN.md).

**Làm theo kế hoạch mở rộng (14/11/2026), phần code của giai đoạn 1–5.** Redis cho giới hạn lượt gọi, cache tài
khoản và số lượt chat LLM toàn hệ thống (Redis chết thì tự dùng RAM); khoá chống chạy trùng agent giữa nhiều worker;
chat chuyển sang async, có dịch vụ riêng, tối đa 45 giây mỗi câu, đóng trình duyệt thì huỷ lời gọi LLM; nút "Chạy ca
ngay" đi qua hàng đợi của worker; PgBouncer (tuỳ chọn), Caddy chia tải nhiều bản, `/metrics`; web tự thử lại khi
gặp 503. Test với dữ liệu cỡ thật (50.000 đơn, 1,3 triệu lượt điểm danh) tìm ra và sửa 3 endpoint chậm (migration
`0007`); máy 2 vCPU chịu 250 req/s trong mục tiêu độ trễ. Đã diễn tập: giết tiến trình API, tắt Redis, khoá bảng,
Groq lỗi. Còn lại phần cần máy thật: nhiều máy API, bản sao DB, sao lưu WAL, CDN, Prometheus/Grafana, chạy 1.000 req/s
trên staging. Tổng 233 test đơn vị + 92 test với database (thêm 39 test cho phần chống sập và mở rộng).

Hướng dẫn triển khai: [`DEPLOY.md`](DEPLOY.md). Việc còn lại là Đợt 3 và các mục chưa đánh dấu bên dưới.

---

Mức ưu tiên:

- **P0** – chặn lên production: không làm thì không nên cho người thật dùng.
- **P1** – cần có để trung tâm dùng được hằng ngày.
- **P2** – nên có, làm sau khi đã chạy thật.

---

## 0. Trả lời nhanh ba câu hỏi

### Có nên tách mỗi vai trò thành một trang web riêng không?

**Không tách 6 web. Tách thành 3 khu.**

| Khu | Ai dùng | Đặc điểm | Gợi ý địa chỉ |
|---|---|---|---|
| **Web công khai** | Người ngoài, khách tìm khoá học | Không đăng nhập, render phía server, cần SEO, đẹp | `anhduong.vn` |
| **Cổng học viên** | Học viên (sau này thêm phụ huynh) | Đăng nhập, ưu tiên điện thoại, giao diện đơn giản | `anhduong.vn/hoc` hoặc `hoc.anhduong.vn` |
| **Bàn làm việc nhân viên** | Tư vấn, giáo vụ, kế toán, giảng viên, quản lý | Đăng nhập, nhiều bảng số liệu, có Copilot và Hộp duyệt | `app.anhduong.vn` |

Lý do giữ 5 vai trò nhân viên chung một web: họ dùng chung dữ liệu (một học viên vừa là việc của tư vấn, vừa của kế toán), và `shell.tsx` đã lọc menu theo quyền. Tách ra chỉ làm nhân đôi code.

Lý do tách học viên ra: hiện học viên đăng nhập vào cùng khung với nhân viên (sidebar, Copilot, ngày tháng kiểu bàn làm việc), trong khi họ chỉ có một trang `/portal`. Đây là đối tượng khác hẳn.

Cách làm ít tốn công nhất: giữ một dự án Next.js, chia ba route group `(public)`, `(portal)`, `(app)`, mỗi nhóm một layout riêng.

### Có thiếu trang giới thiệu khoá học cho người ngoài không?

**Có, và đây là lỗ hổng lớn nhất về mặt sản phẩm.** Hiện `/` chỉ chuyển hướng sang `/login`. Người ngoài không xem được gì.

Hệ quả cụ thể: bảng `khach_tiem_nang` có nguồn `website`, agent tuyển sinh chạy khi có khách mới, nhưng **không có form công khai nào để khách tự để lại thông tin**. Khách chỉ vào hệ thống khi tư vấn viên gõ tay. Xem mục 1.

### Thứ gì đang chặn production?

Bảo mật tài khoản (mục 2), quản trị người dùng và danh mục (mục 3), hạ tầng triển khai (mục 6), và việc gửi dữ liệu cá nhân học viên sang LLM nước ngoài (mục 8).

---

## 1. Web công khai (chưa có gì) – P0/P1

| # | Trang / tính năng | Ghi chú | Mức |
|---|---|---|---|
| 1.1 | **Trang chủ** | Giới thiệu trung tâm, khoá nổi bật, lớp sắp khai giảng, số liệu, đánh giá học viên, nút "Đăng ký tư vấn" | P0 |
| 1.2 | **Danh mục khoá học** | Lọc theo danh mục, trình độ, học phí, hình thức. Dữ liệu đã có ở `khoa_hoc` nhưng `GET /courses` đang bắt đăng nhập | P0 |
| 1.3 | **Trang chi tiết khoá học** | Mô tả, lộ trình, học phí, ưu đãi, **các lớp sắp khai giảng còn chỗ**, giảng viên | P0 |
| 1.4 | **Form đăng ký tư vấn / học thử** | Tạo `khach_tiem_nang` nguồn `website` → kích hoạt agent tuyển sinh. Cần chống spam (captcha, giới hạn theo IP) | P0 |
| 1.5 | **Lịch khai giảng** | Bảng tất cả lớp sắp mở, theo cơ sở và ca học | P1 |
| 1.6 | **Chatbot tư vấn cho khách vãng lai** | Agent advisor (RAG chính sách) đã có nhưng bắt đăng nhập. Mở bản ẩn danh: chỉ RAG, không Text-to-SQL, giới hạn theo IP, cuối hội thoại mời để lại số điện thoại | P1 |
| 1.7 | **Trang chính sách** | Học phí, hoàn phí, bảo lưu, quy chế. Nội dung đã có ở `data/policies/*.md`, chỉ cần hiển thị | P1 |
| 1.8 | Giới thiệu, đội ngũ giảng viên, cơ sở (bản đồ), liên hệ | Bảng `co_so`, `giang_vien` đã có | P1 |
| 1.9 | Điều khoản sử dụng, chính sách quyền riêng tư | Bắt buộc khi thu thập số điện thoại, email (mục 8) | P0 |
| 1.10 | **SEO** | Metadata từng trang, Open Graph, `sitemap.xml`, `robots.txt`, dữ liệu có cấu trúc `Course`. Hiện chưa có file nào | P1 |
| 1.11 | Tin tức / blog, câu hỏi thường gặp | Phục vụ SEO | P2 |
| 1.12 | Đăng ký và thanh toán online | Phụ thuộc cổng thanh toán (mục 4.1) | P2 |

**Cần thêm ở dữ liệu:** `khoa_hoc` chỉ có `mo_ta` dạng chữ. Trang giới thiệu "hoành tráng" cần thêm ảnh bìa, slug, mô tả ngắn, lộ trình chi tiết, đối tượng phù hợp, kết quả đầu ra, cờ hiển thị công khai. `giang_vien` cần ảnh và tiểu sử.

**Cần thêm ở API:** một nhóm endpoint `/public/*` không cần đăng nhập, chỉ trả trường được phép công khai, có cache và giới hạn tần suất.

---

## 2. Tài khoản và bảo mật – P0

| # | Vấn đề | Hiện trạng trong code | Việc cần làm |
|---|---|---|---|
| 2.1 | **Tài khoản demo** | Trang đăng nhập có 6 nút điền sẵn, mật khẩu `demo123`; `eduassist-setup` tự seed dữ liệu giả khi DB trống | Tắt nút demo và seed bằng biến môi trường; production chỉ tạo một tài khoản quản lý ban đầu |
| 2.2 | **Khoá bí mật mặc định** | `JWT_SECRET=dev-only-change-me`, mật khẩu DB `app_rw_dev_pw` là giá trị mặc định trong `config.py` và `docker-compose.yml` | Từ chối khởi động nếu còn giá trị mặc định khi chạy production |
| 2.3 | **Không chống dò mật khẩu** | `/auth/login` không có giới hạn tần suất (limiter chỉ gắn vào `/chat`) | Giới hạn theo IP và theo tên đăng nhập, khoá tạm sau N lần sai |
| 2.4 | **Không đổi / quên mật khẩu** | Không có endpoint nào | Đổi mật khẩu, quên mật khẩu qua email, bắt đổi ở lần đăng nhập đầu, quy tắc độ mạnh |
| 2.5 | **Token lưu ở `localStorage`** | `web/src/lib/api.ts` | Chuyển sang cookie `httpOnly` + `Secure` + `SameSite`, thêm refresh token |
| 2.6 | **Không thu hồi được phiên** | Vai trò nằm trong JWT sống 8 giờ; khoá tài khoản hay đổi vai trò không có tác dụng cho tới khi token hết hạn; đăng xuất chỉ xoá ở trình duyệt | Kiểm tra `active` và vai trò từ DB mỗi request, hoặc dùng token ngắn hạn + danh sách thu hồi |
| 2.7 | **Chặn trang chỉ ở phía client** | Không có `middleware.ts`; `Shell` chuyển hướng sau khi tải trang | Chặn ở server (dễ làm sau khi có cookie ở 2.5) |
| 2.8 | Thiếu header bảo mật | `next.config.ts` trống | CSP, HSTS, `X-Frame-Options`, `Referrer-Policy` |
| 2.9 | Giới hạn tần suất trong RAM | Đã ghi trong README; chạy 2 instance là sai | Chuyển sang Redis |
| 2.10 | Xác thực hai lớp cho quản lý và kế toán | Chưa có | P1 |
| 2.11 | Tài liệu API công khai | `/docs` của FastAPI đang mở | Tắt hoặc bảo vệ ở production |

---

## 3. Trang quản trị còn thiếu – P0/P1

Hiện nhiều thứ chỉ có trong seed, không có màn hình để thêm, sửa.

| # | Trang | Hiện trạng | Mức |
|---|---|---|---|
| 3.1 | **Quản lý người dùng** | Quyền `user.admin` có khai báo nhưng không có API hay trang nào. Không tạo được tài khoản nhân viên mới, không khoá được tài khoản | P0 |
| 3.2 | **Cấp tài khoản cho học viên** | Ghi danh xong không tự tạo `app_user`; chỉ học viên demo đăng nhập được cổng học viên | P0 |
| 3.3 | **Quản lý khoá học** | Chỉ có `GET /courses`. Không thêm, sửa, ngừng bán được | P0 |
| 3.4 | **Quản lý giảng viên, phòng học, cơ sở** | Chỉ có `GET /teachers`, `GET /rooms` | P1 |
| 3.5 | **Cài đặt trung tâm** | Tên, logo, địa chỉ, email gửi đi đang cố định trong code | P1 |
| 3.6 | **Cấu hình luật nghiệp vụ** | Ngưỡng trả góp 5 triệu, hoàn phí 100/70/0%, voucher 15%/30% nằm cứng trong `rules.py` và `core.py`. Trung tâm khác luật là phải sửa code | P1 |
| 3.7 | **Quản lý kho tri thức (chính sách)** | Chính sách là file `.md` trong repo, muốn sửa phải chạy lại lệnh ingest. Cần trang sửa và tự cập nhật vector | P1 |
| 3.8 | **Lỗ hổng tri thức và ví dụ SQL** | Bảng `knowledge_gap`, `sql_examples` có dữ liệu nhưng không có trang xem; chỉ có script dòng lệnh | P2 |
| 3.9 | **Lịch sử email đã gửi** | `email_log` chỉ hiện một phần trong hồ sơ học viên; không có trang tổng, không thấy email lỗi | P1 |
| 3.10 | **Trang chủ riêng cho từng vai trò** | Chỉ quản lý có "Bản tin hôm nay". Kế toán, tư vấn, giáo vụ rơi vào Hộp duyệt; giảng viên rơi vào danh sách lớp. Nên có: giảng viên thấy buổi dạy hôm nay, kế toán thấy khoản đến hạn hôm nay, tư vấn thấy khách cần gọi | P1 |
| 3.11 | Trang hồ sơ cá nhân | Chưa có (đổi tên hiển thị, mật khẩu, thông báo) | P1 |
| 3.12 | Trang `404`, trang lỗi | Chưa có `not-found.tsx`, `error.tsx` | P1 |

---

## 4. Tính năng nghiệp vụ còn thiếu

### 4.1 Tài chính

| # | Tính năng | Ghi chú | Mức |
|---|---|---|---|
| a | **Thanh toán online / mã QR chuyển khoản** | README ghi ngoài phạm vi đồ án. Thực tế: kế toán phải đối chiếu sao kê và gõ tay từng khoản. Tối thiểu nên có mã VietQR kèm nội dung chuyển khoản theo mã đơn | P1 |
| b | **Phiếu thu, biên lai in được / PDF** | Chưa có | P1 |
| c | **Hoá đơn điện tử** | Trung tâm xuất hoá đơn cần tích hợp nhà cung cấp hoá đơn điện tử | P2 |
| d | Xuất Excel/CSV | Công nợ, doanh thu, danh sách lớp. Kiểm tra lại: tôi không thấy nút xuất nào | P1 |
| e | Sổ quỹ, đối soát cuối ngày, lương giảng viên theo buổi | | P2 |

### 4.2 Đào tạo

| # | Tính năng | Mức |
|---|---|---|
| a | **Thời khoá biểu dạng lịch** (tuần/tháng) theo phòng, giảng viên, học viên | P1 |
| b | Học bù, dạy thay, nghỉ lễ, dời buổi học | P1 |
| c | Danh sách chờ khi lớp đầy | P2 |
| d | Kiểm tra xếp lớp đầu vào | P2 |
| e | **Xuất chứng nhận PDF**: luật đủ điều kiện đã có (chuyên cần ≥ 80%, điểm ≥ 50); kiểm tra lại xem đã có file chứng nhận để tải chưa | P1 |
| f | Tài liệu, bài tập, nộp bài theo lớp | P2 |
| g | Nhập học viên hàng loạt từ Excel (trung tâm chuyển từ hệ thống cũ sang) | P1 |

### 4.3 Cổng học viên

| # | Tính năng | Mức |
|---|---|---|
| a | Xem chi tiết điểm danh và điểm từng buổi | P1 |
| b | Xem và tải biên lai, chứng nhận | P1 |
| c | Tự thanh toán đợt học phí (phụ thuộc 4.1a) | P2 |
| d | Tự đăng ký khoá mới | P2 |
| e | Đánh giá giảng viên, khoá học sau khi học xong | P2 |
| f | Vai trò phụ huynh (một phụ huynh, nhiều con) nếu trung tâm dạy thiếu nhi | P2 |
| g | Cài như ứng dụng trên điện thoại (PWA), thông báo đẩy | P2 |

### 4.4 Kênh liên lạc

| # | Tính năng | Ghi chú | Mức |
|---|---|---|---|
| a | **SMTP thật** | Đang dùng Mailpit (hộp thư giả). Cần nhà cung cấp email, cấu hình SPF/DKIM/DMARC, xác thực và TLS (code hiện gọi `smtplib.SMTP` không đăng nhập, không TLS) | P0 |
| b | Email HTML có thương hiệu, link huỷ nhận | Đang gửi chữ thuần | P1 |
| c | Xử lý email bị trả lại | | P2 |
| d | **Zalo OA / ZNS, SMS** | Ở Việt Nam học viên đọc Zalo nhiều hơn email; nhắc nợ qua email dễ bị bỏ qua | P1 |
| e | **Gửi email tách khỏi transaction** | `_deliver()` gửi SMTP ngay trong transaction nghiệp vụ. Nếu transaction rollback sau khi gửi thì email đã đi nhưng không có log, lần sau gửi trùng. Nên đưa email vào hàng đợi (outbox) rồi worker gửi | P1 |

### 4.5 Dùng chung

| # | Tính năng | Ghi chú | Mức |
|---|---|---|---|
| a | **Phân trang** | Danh sách đang cắt cứng `LIMIT 200–300` (khách, học viên, yêu cầu). Quá số đó là mất dữ liệu trên màn hình mà không báo | P0 |
| b | Tìm kiếm toàn hệ thống | | P2 |
| c | Lọc theo cơ sở, phân quyền theo cơ sở | Bảng `co_so` có nhưng quyền chưa gắn với cơ sở | P2 |
| d | Xoá mềm, khôi phục | | P2 |
| e | Chế độ tối | README đã ghi là chưa có | P2 |
| f | Tải file lên (ảnh khoá học, giấy tờ học viên) | Chưa có nơi lưu file | P1 |

---

## 5. AI và agent – P1

| # | Vấn đề | Ghi chú |
|---|---|---|
| 5.1 | **Groq gói miễn phí** | Giới hạn 8K token/phút (ghi trong `llm.py`). Vài người chat cùng lúc là nghẽn. Cần gói trả phí hoặc nhà cung cấp khác, theo dõi chi phí theo ngày |
| 5.2 | **Eval LLM đã cũ** | README ghi chưa chạy lại sau khi đổi schema và vai trò; bộ câu hỏi còn nhỏ (16 / 12 / 15 câu) |
| 5.3 | **Chống prompt injection từ dữ liệu** | Ghi chú khách hàng, nội dung yêu cầu của học viên là chữ tự do và được đưa vào ngữ cảnh agent. Cần bộ test riêng cho trường hợp học viên cài lệnh vào nội dung yêu cầu |
| 5.4 | **Nút dừng khẩn cấp** | Chưa thấy công tắc tắt toàn bộ agent nền khi có sự cố (hiện phải hạ từng loại thao tác về L0 hoặc tắt worker) |
| 5.5 | Cảnh báo khi agent lỗi | Lỗi được ghi vào `lan_chay_agent` nhưng không ai được báo |
| 5.6 | Hạn mức chi phí LLM theo người dùng | Chỉ có giới hạn 20 yêu cầu/phút |
| 5.7 | Langfuse | Đang tuỳ chọn; production nên bật để truy vết |

---

## 6. Hạ tầng và vận hành – P0

| # | Vấn đề | Hiện trạng | Việc cần làm |
|---|---|---|---|
| 6.1 | **HTTPS và reverse proxy** | Compose mở thẳng cổng 3000 và 8000 | Thêm Caddy/Nginx/Traefik, chứng chỉ TLS, tên miền |
| 6.2 | **Sao lưu DB** | Chỉ có volume `pgdata` | Sao lưu tự động hằng ngày, lưu ngoài máy chủ, **thử khôi phục** ít nhất một lần |
| 6.3 | **Cổng DB mở ra ngoài** | `5433:5432` | Bỏ ở production |
| 6.4 | **File compose cho production** | Một file dùng chung, có Mailpit và profile dev | Tách `docker-compose.prod.yml`, thêm `restart: unless-stopped`, giới hạn tài nguyên |
| 6.5 | **Quản lý bí mật** | File `.env` | Dùng secret của nền tảng triển khai; không để `.env` trên máy chủ dạng đọc được rộng |
| 6.6 | **Theo dõi lỗi và cảnh báo** | Log JSON ra stdout; không có Sentry, không có metrics | Sentry (API và web), giám sát uptime, cảnh báo khi worker chết |
| 6.7 | **Worker không có kiểm tra sức khoẻ** | Vòng `while True`; nếu treo thì không ai biết, agent nền ngừng chạy âm thầm | Ghi nhịp tim vào DB, cảnh báo khi quá hạn |
| 6.8 | **Múi giờ** | Container mặc định UTC; `DAILY_RUN_HOUR=7` và `date.today()` sẽ lệch 7 tiếng so với giờ Việt Nam (nhắc nợ chạy lúc 14h, ngày nghiệp vụ đổi lúc 7h sáng) | Đặt `TZ=Asia/Ho_Chi_Minh` cho container và DB |
| 6.9 | **Môi trường staging** | Chưa có | Một bản giống production để thử trước |
| 6.10 | **CI/CD** | CI chỉ chạy khi push `main` hoặc mở PR (push thẳng `platform` không chạy); chưa có bước build image và deploy | Thêm deploy tự động, quét lỗ hổng dependency, chạy migration có kiểm soát |
| 6.11 | **Migration tự chạy khi khởi động** | `setup` chạy `alembic upgrade head` mỗi lần `up` | Production nên chạy migration thành bước riêng, có sao lưu trước |
| 6.12 | **Image web nặng** | Copy cả `node_modules` | Dùng `output: "standalone"` của Next.js |
| 6.13 | **URL API nhúng lúc build** | `NEXT_PUBLIC_API_URL` cố định trong bản build; đổi tên miền phải build lại | Gọi API qua cùng tên miền (proxy `/api`) |
| 6.14 | **Sức chịu tải** | Pool DB tối đa 10 kết nối; chat SSE giữ một luồng suốt thời gian LLM trả lời; README ghi chưa thử tải 100 người | Thử tải, tăng pool, cân nhắc PgBouncer |
| 6.15 | Dọn dữ liệu cũ | `outbox_su_kien`, `audit_log`, checkpoint LangGraph, `query_log` tăng mãi | Lịch lưu trữ và xoá |

---

## 7. Chất lượng – P1

| # | Vấn đề | Ghi chú |
|---|---|---|
| 7.1 | **Web không có test** | Không có test đơn vị, không có test đầu-cuối (Playwright). Backend có 162 + 40 test |
| 7.2 | Web không có lint trong CI | `package.json` không có script `lint` |
| 7.3 | Thử với người dùng thật | README ghi chưa làm (3–5 người) |
| 7.4 | Trợ năng | README ghi chưa kiểm ở 320px, zoom 200%, trình đọc màn hình |
| 7.5 | Dữ liệu seed còn lỗi | README ghi còn vài cặp trùng lịch ngoài ý muốn |
| 7.6 | Tài sản mặc định | `web/public` còn icon mẫu của Next.js (`next.svg`, `vercel.svg`); thiếu ảnh chia sẻ mạng xã hội |
| 7.7 | Tài liệu vận hành | Chưa có hướng dẫn cho người dùng cuối, chưa có quy trình xử lý sự cố |
| 7.8 | Chainlit cũ | Thư mục `ui/` và profile `legacy` nên gỡ khỏi image production |

---

## 8. Pháp lý và dữ liệu cá nhân – P0

Phần này cần người có chuyên môn pháp lý xác nhận; tôi chỉ nêu điểm cần xem.

| # | Vấn đề | Ghi chú |
|---|---|---|
| 8.1 | **Dữ liệu học viên gửi sang LLM nước ngoài** | Agent phân tích được đọc bảng `hoc_vien`, `khach_tiem_nang` (họ tên, email, số điện thoại) và kết quả truy vấn được đưa cho LLM của Groq. Đây là chuyển dữ liệu cá nhân ra nước ngoài. Cần: che thông tin cá nhân trước khi đưa cho LLM, hoặc thoả thuận xử lý dữ liệu với nhà cung cấp, và ghi rõ trong chính sách quyền riêng tư |
| 8.2 | **Sự đồng ý** | Form đăng ký tư vấn và ghi danh cần ô đồng ý xử lý dữ liệu và nhận email/tin nhắn; lưu lại thời điểm đồng ý |
| 8.3 | Quyền của chủ thể dữ liệu | Xem, sửa, xoá dữ liệu của mình; chưa có chức năng xoá hay ẩn danh hoá học viên |
| 8.4 | Thời hạn lưu trữ | Khách tiềm năng không ghi danh lưu bao lâu thì xoá |
| 8.5 | Email tiếp thị | Thư tư vấn do agent soạn cần link huỷ nhận |
| 8.6 | Học viên dưới 16 tuổi | Cần sự đồng ý của phụ huynh nếu trung tâm nhận thiếu nhi |

---

## 9. Thứ tự làm đề xuất

**Đợt 1 – đủ an toàn để một trung tâm dùng thử nội bộ**

1. Bảo mật tài khoản: 2.1, 2.2, 2.3, 2.4, 2.6.
2. Quản lý người dùng, cấp tài khoản học viên, quản lý khoá học: 3.1, 3.2, 3.3.
3. Hạ tầng: HTTPS, sao lưu, đóng cổng DB, múi giờ, theo dõi lỗi (6.1, 6.2, 6.3, 6.6, 6.8).
4. SMTP thật (4.4a), phân trang (4.5a).
5. Che thông tin cá nhân trước khi gửi LLM (8.1).

**Đợt 2 – mở ra cho khách bên ngoài**

6. Web công khai: trang chủ, danh mục, chi tiết khoá, form tư vấn, chính sách, SEO (1.1–1.4, 1.7, 1.9, 1.10).
7. Tách ba khu giao diện; cổng học viên riêng (mục 0).
8. Chatbot tư vấn cho khách vãng lai (1.6).
9. Trang chủ theo vai trò, thời khoá biểu dạng lịch (3.10, 4.2a).

**Đợt 3 – giảm việc tay**

10. Mã QR thanh toán, biên lai, chứng nhận PDF, xuất Excel (4.1a, 4.1b, 4.2e, 4.1d).
11. Zalo / SMS (4.4d).
12. Cấu hình luật nghiệp vụ và kho tri thức trên giao diện (3.6, 3.7).
13. Test đầu-cuối cho web, thử tải, chạy lại eval LLM (7.1, 6.14, 5.2).

---

## 10. Những gì đã ổn, không cần làm lại

- Luật nghiệp vụ tập trung ở tầng Service, có test từng luật.
- Phân quyền kiểm tra ở backend cho mọi thao tác; agent bị chặn cứng với danh sách `AGENT_FORBIDDEN`.
- Hộp duyệt và mức tự chủ L0/L1/L2; số liệu trong đề xuất do code tính.
- Nhật ký kiểm toán, outbox trong cùng transaction.
- Text-to-SQL có role DB chỉ đọc và danh sách bảng cho phép.
- Mật khẩu băm PBKDF2 có salt; lỗi nghiệp vụ trả thông điệp rõ ràng.
- Docker chạy bằng user thường, có healthcheck cho DB và API.
- CI có lint, test đơn vị, test tích hợp với Postgres thật, mô phỏng 30 ngày.
