# Kế hoạch mở rộng: 1.000 request/giây không sập

> Lập 14/11/2026 sau khi test tải thật (`loadtest/`), cập nhật cùng ngày sau khi làm giai đoạn 1–5 phần code.
> Số "đo được" lấy từ máy Docker 2 vCPU, có dùng dữ liệu cỡ thật sinh bằng `loadtest/scale_data.sql`, sai số khoảng
> ±30%. Số cho cấu hình đích là **ước tính** từ số đo đó: phải chạy lại `loadtest/api.js` trên staging có cấu hình
> như mục 3 trước khi mua máy (mục 4, giai đoạn 5).

## 1. Mục tiêu

| Chỉ số | Mục tiêu |
|---|---|
| Thông lượng | 1.000 request/giây API nghiệp vụ, kéo dài, không kể chat LLM |
| Độ trễ | 95% request dưới 300 ms, 99% dưới 1 giây |
| Lỗi | Dưới 1% khi tải trong mức; vượt mức thì từ chối nhanh (503) chứ không treo |
| Chịu lỗi | Mất 1 máy API vẫn phục vụ đủ 1.000 req/s; database chậm thì hệ thống báo lỗi nhanh và tự hồi phục |
| Chat | Tính riêng theo số người chat cùng lúc (mục 6), không tính bằng req/s |

**1.000 req/s là bao nhiêu người dùng?** Giao diện nhân viên tự hỏi số đề xuất mỗi 30 giây và thông báo mỗi 60 giây;
khi thao tác, mỗi lần chuyển trang gọi 2–4 API. Một người đang dùng tạo khoảng 0,1–0,2 req/s, nên 1.000 req/s tương
đương **5.000–10.000 người cùng mở web**. Một trung tâm cỡ vừa (30 nhân viên, vài trăm học viên online giờ cao điểm)
chỉ khoảng 50 req/s. Mục tiêu 1.000 req/s là cỡ một chuỗi lớn hoặc bán phần mềm cho khoảng 20 trung tâm.

## 2. Hiện trạng đo được

Chi tiết, cách chạy lại và số liệu từng lần đo: [`loadtest/README.md`](../loadtest/README.md).

**Lúc bắt đầu, API treo cứng ở khoảng 100 req/s** và không tự hồi phục: hai lỗi deadlock (pool kết nối, thread pool).
Sau giai đoạn 1–5:

| Đo trên 2 vCPU (k6 chạy cùng máy) | Dữ liệu demo (618 đơn) | Dữ liệu cỡ thật (50.000 đơn, 1,3 triệu lượt điểm danh) |
|---|---|---|
| 1 tiến trình API, có Redis | 170 req/s, p95 70–100 ms | – |
| 2 tiến trình API, có Redis | 300 req/s, p95 625 ms | **250 req/s, p95 140 ms, 0% lỗi**; 300 req/s 0% lỗi nhưng p95 1,3 s |
| Bài tăng dần tới 1.000 req/s (request thành công) | 1.220 lúc đầu (rồi treo) → 42.037 | 36.337 → **46.210** sau khi sửa truy vấn |
| CPU Python mỗi request | khoảng 3,7 ms (lúc đầu 10 ms) | khoảng 4 ms |
| CPU Postgres mỗi request | khoảng 1,2 ms | khoảng 1,3 ms (2,2 ms trước khi sửa truy vấn) |

**Dữ liệu cỡ thật lộ ra 3 endpoint chậm** mà dữ liệu demo che mất (đã sửa, kết quả kiểm tra giống hệt bản cũ):

| Endpoint | Trước | Sau | Cách sửa |
|---|---|---|---|
| Danh sách hoá đơn | 223 ms (trang sâu 695 ms) | 17 ms (32 ms) | Lấy id của trang trước, tính số đã đóng chỉ cho 50 dòng (LATERAL); partial index cho lọc "còn nợ" |
| Danh sách lớp | 90 ms, trả cả 2.150 lớp | 11 ms | Phân trang; thời khoá biểu chỉ lấy lớp đang mở |
| Bản tin quản lý | 113 ms (1,3 s khi đông) | 5 ms | Cache chung 60 giây, chỉ một request tính lại khi hết hạn |
| Mọi danh sách phân trang | `count(*) OVER ()` tính đủ cột cho mọi dòng | đếm riêng | `paginate` trong `services/core.py` |

**Điểm nghẽn hiện tại là CPU của Python** (API dùng khoảng 105% CPU, Postgres khoảng 35% ở 300 req/s). Python chỉ dùng
được 1 nhân mỗi tiến trình, nên mở rộng bằng nhiều tiến trình trên nhiều nhân, nhiều máy - điều kiện cho việc này
(Redis, khoá worker) đã xong ở giai đoạn 2.

## 3. Kiến trúc đích

```
                         Người dùng (trình duyệt, điện thoại)
                                      │
                       CDN: ảnh, JS, CSS, trang công khai có cache
                                      │
                     Load balancer (Caddy ×2, HTTPS, tắt đệm cho SSE)
            kiểm tra /health/live (còn sống) và /health (sẵn sàng, có DB)
          ┌──────────────┬────────────┴───────┬──────────────────┐
          ▼              ▼                    ▼                  ▼
     Web Next.js    API nghiệp vụ ×3 máy   API chat ×2       (thêm máy khi cần)
       ×2 bản       mỗi máy 4 vCPU,        async, ngăn riêng
                    4 tiến trình uvicorn   để LLM chậm không
                    = 12 tiến trình        kéo theo trang thường
          └──────────────┴─────────┬──────────┴──────────┐
                                   ▼                     ▼
                        PgBouncer (gộp kết nối)        Redis
                                   │              giới hạn lượt gọi, cache tài khoản,
                     ┌─────────────┴────────┐     cache số liệu tổng hợp,
                     ▼                      ▼     số lượt chat LLM toàn hệ thống
            Postgres chính             Postgres bản sao chỉ đọc
            4 vCPU, 16 GB              trang công khai, SQL của AI
            ghi + đọc cần mới nhất     (DATABASE_READ_URL, AGENT_RO_URL)
                     │
       Sao lưu liên tục (WAL, khôi phục tới từng phút) + bản sao ra ngoài máy chủ
                     ▲
            Worker ×2 (outbox SKIP LOCKED + agent theo lịch có khoá, chạy trùng an toàn)
```

`docker-compose.prod.yml` đã có đủ các thành phần này cho **một máy** (api, api-chat, worker, redis, pgbouncer tuỳ
chọn, Caddy chia tải). Lên nhiều máy: chạy service `api` / `api-chat` trên các máy khác và liệt kê địa chỉ trong
`API_UPSTREAMS` / `CHAT_UPSTREAMS` của Caddy.

### Tính số máy (cập nhật theo số đo trên dữ liệu cỡ thật)

| Thành phần | Phép tính | Đề xuất |
|---|---|---|
| API nghiệp vụ | 1.000 req/s × 4 ms CPU = 4 nhân bận. Giữ CPU dưới 60% để còn chỗ cho đỉnh tải: khoảng 7 nhân | **3 máy × 4 vCPU, mỗi máy 4 tiến trình** = 12 tiến trình × 125–150 req/s = 1.500–1.800 req/s. Mất 1 máy còn 1.000–1.200 req/s |
| Postgres | 1.000 × 1,3 ms CPU = 1,3 nhân, chưa kể ghi và tranh khoá | **4 vCPU, 16 GB RAM**, SSD; bản sao chỉ đọc cho trang công khai và SQL của AI |
| Kết nối DB | Mỗi tiến trình mở tối đa khoảng 39 kết nối (chính 10, đăng nhập 4, AI 5, LangGraph 10 + 10 async). 12 tiến trình = 468 | **PgBouncer**: hàng trăm kết nối phía ứng dụng dùng chung 40–80 kết nối thật |
| Redis | Mỗi request 1–2 lệnh; vài nghìn lệnh mỗi giây là rất nhẹ | 1 bản nhỏ (1 vCPU, 1 GB). Redis chết thì API tự dùng RAM (đã diễn tập) |
| Web Next.js | Trang công khai có cache 5 phút, trang nội bộ chỉ gửi JS tĩnh | 2 bản, mỗi bản 1–2 vCPU |

## 4. Lộ trình

### Giai đoạn 0: Đo — ✅ xong

- [x] Kịch bản test tải `loadtest/api.js` (k6): hỗn hợp thao tác giống màn hình thật, mục tiêu độ trễ, 3 kiểu chạy.
- [x] Bật `pg_stat_statements` (docker-compose; `eduassist-setup` tự tạo extension).
- [x] Đo profiler CPU của API: tìm ra chuyển JSON tốn 5 ms CPU mỗi request.

### Giai đoạn 1: Chống sập dây chuyền — ✅ xong

| Việc | Ở đâu |
|---|---|
| Pool riêng cho bước kiểm tra đăng nhập (gỡ deadlock 1) | `db.py`, `api/auth.py` |
| Kiểm soát cửa vào: số request chạy cùng lúc luôn ít hơn số luồng, dư thì xếp hàng trên event loop có hạn, đầy thì 503 (gỡ deadlock 2) | `api/overload.py` |
| Chat có ngăn riêng, không chiếm chỗ trang thường | `api/overload.py` |
| Chờ kết nối tối đa 5 giây rồi trả 503 + `Retry-After` | `db.py`, `api/main.py` |
| Câu SQL quá 15 giây bị huỷ; **chờ khoá quá 5 giây** báo bận (503); transaction đứng im quá 60 giây bị đóng | `db.py`, `scripts/setup.py` (ALTER ROLE) |
| `/health/live` không đụng DB, luôn trả lời khi quá tải | `api/main.py` |
| Index cho 23 khoá ngoại; index ngày thu tiền; partial index "còn nợ" | migration `0006`, `0007` |
| Trả JSON bằng orjson; middleware log ASGI thuần | `api/fastjson.py`, `api/main.py` |
| Cấu hình chặn giá trị gây kẹt, sai thì không khởi động | `config.py` |
| Web: nhận 503 thì request đọc tự thử lại theo `Retry-After`, tăng dần, lệch ngẫu nhiên (không thử dồn dập) | `web/src/lib/api.ts` |

### Giai đoạn 2: Bỏ trạng thái trong bộ nhớ (điều kiện để chạy nhiều tiến trình) — ✅ xong

| Việc | Ở đâu | Kiểm chứng |
|---|---|---|
| Giới hạn lượt gọi trong Redis (đăng nhập theo IP, chat theo người, chat công khai theo IP và tổng) | `cache.py`, `api/ratelimit.py` | 2 tiến trình: đúng 10 lần đăng nhập rồi chặn (trước: mỗi tiến trình 10) |
| Redis lỗi: ngắt mạch, dùng RAM; hết hạn ngắt chỉ một request thử lại | `cache.py` | Diễn tập tắt Redis: 0 lỗi |
| Khoá agent theo tên (`pg_try_advisory_xact_lock`) và kiểm tra lại lịch bên trong khoá | `background/runner.py` | Test: worker thứ hai bỏ qua; dùng được qua PgBouncer |
| Cache tài khoản trong Redis 30 giây, xoá ngay và xoá lại SAU commit khi đổi mật khẩu / khoá / đổi quyền / đăng xuất mọi nơi | `cache.py`, `api/auth.py`, `services/accounts.py` | 1 tiến trình: 170 req/s p95 70 ms (không có cache: quá tải ở mức này) |
| Cache số liệu ít đổi (bản tin 60 giây, trang công khai 60 giây), chỉ một request tính lại khi hết hạn | `cache.py`, `api/platform.py`, `api/public_routes.py` | Test cùng tiến trình và giữa tiến trình |
| `WEB_CONCURRENCY` trong compose (`API_WORKERS`); production từ chối chạy nhiều tiến trình nếu thiếu `REDIS_URL` | `docker-compose*.yml`, `config.py` | |

### Giai đoạn 3: Tách chat và chuyển sang async — ✅ xong

| Việc | Ở đâu |
|---|---|
| Chat `async def` + `graph.astream` + `AsyncPostgresSaver`; tool giao việc cho agent con có bản `ainvoke`; tool lá (SQL, RAG) chạy trong thread pool riêng | `chat.py`, `public_chat.py`, `agents/supervisor.py`, `agents/persistence.py` |
| Dịch vụ chat riêng `api-chat` (cùng image), Caddy chia `/api/chat*`, `/api/public/chat` | `docker-compose.prod.yml`, `deploy/Caddyfile` |
| Tối đa 45 giây mỗi câu, kể cả mọi lần thử lại và model dự phòng | `chat.py` (`CHAT_TURN_TIMEOUT_SECONDS`) |
| Chỉ thử lại lỗi tạm thời (429, 5xx, mất mạng); khoá sai / yêu cầu sai báo lỗi ngay | `llm.py` |
| Tối đa `LLM_MAX_CONCURRENT` lượt chat đang chạy trên toàn hệ thống (Redis, có hạn thuê); đầy thì báo bận ngay | `cache.py`, `chat.py` |
| Người dùng đóng trình duyệt: đóng generator, huỷ lời gọi LLM, trả chỗ ngay | `api/sse.py`, `chat.py` |
| Worker: soạn lời văn bằng LLM tối đa 15 giây, không thử lại (đang mở transaction); agent tuyển sinh soạn thư trước khi khoá dòng khách | `llm.py`, `background/agents.py` |
| Nút "Chạy ca ngay": API chỉ ghi yêu cầu vào outbox, worker chạy đúng một lần, web hỏi kết quả | `background/runner.py`, `api/platform.py`, `web/.../agents/page.tsx` |
| `idle_in_transaction_session_timeout` 60 giây | `db.py`, setup |

Chưa làm: worker vẫn mở transaction trong lúc chờ LLM (tối đa 15 giây). Tách hẳn "soạn rồi mới mở transaction" cần
viết lại từng agent thành hai bước; khó vì khi tự duyệt (mức L2) thao tác gửi email nằm trong cùng transaction.

### Giai đoạn 4: Nhân bản và hạ tầng — phần code ✅, phần hạ tầng ⏳ (cần máy thật)

| Việc | Trạng thái |
|---|---|
| PgBouncer chế độ transaction (`deploy/pgbouncer/start.sh`, profile `pgbouncer`); timeout đặt bằng ALTER ROLE; giữ prepared statement (PgBouncer 1.24) | ✅ Cả 88 test tích hợp qua PgBouncer |
| Caddy chia tải nhiều bản (`least_conn`, kiểm tra `/health/live` mỗi 5 giây, thử bản khác khi lỗi kết nối) | ✅ cấu hình đã kiểm tra hợp lệ |
| Postgres tinh chỉnh bộ nhớ, nén WAL, log câu chậm > 500 ms, log chờ khoá (compose production, chỉnh qua biến môi trường) | ✅ |
| Đọc từ bản sao: `DATABASE_READ_URL` (trang công khai), `AGENT_RO_URL` (SQL của AI) | ✅ code; ⏳ dựng bản sao |
| `/metrics` dạng Prometheus: độ trễ, số request theo route/mã, hàng chờ, pool DB, Redis, lượt chat LLM | ✅; ⏳ dựng Prometheus + Grafana, cảnh báo |
| Load balancer 2 bản, 3 máy API, 2 web, 2 worker | ⏳ cần máy |
| Sao lưu liên tục bằng WAL (pgBackRest / WAL-G) ra kho ngoài máy chủ. Hiện `pg_dump` mỗi đêm: có thể mất tới 24 giờ dữ liệu | ⏳ cần kho lưu trữ (S3...) |
| CDN cho file tĩnh và trang công khai (`Cache-Control` đã có) | ⏳ cần nhà cung cấp |

**Đo được về PgBouncer:** trên cùng một máy 2 vCPU, PgBouncer làm trần giảm từ khoảng 300 xuống 250 req/s (PgBouncer
và Postgres tranh CPU với API; mỗi truy vấn chậm thêm khoảng 0,1 ms). Ở 200 req/s thì như nhau. Vì vậy compose để
PgBouncer **tuỳ chọn**: một máy nối thẳng; nhiều máy API (vượt `max_connections`) mới bật.

### Giai đoạn 5: Kiểm chứng — ✅ trên máy dev, ⏳ trên staging

- [x] Sinh dữ liệu cỡ thật vào database riêng (`loadtest/scale_data.sql`): 10.104 học viên, 50.058 đơn, 2.150 lớp,
      1,3 triệu lượt điểm danh. Tìm ra và sửa 3 endpoint chậm (mục 2).
- [x] Kịch bản k6 theo màn hình mặc định thật (kế toán lọc "còn nợ", bảng tuyển sinh theo cột).
- [x] Diễn tập sự cố trong lúc chạy 150 req/s (kết quả ở mục 5).
- [ ] Chạy trên staging cấu hình như mục 3: tải đều 1.000 req/s 30 phút; tải đột biến 0 → 1.500 trong 10 giây; chạy
      dài 2 giờ để tìm rò bộ nhớ.
- [ ] Thêm thao tác ghi (ghi danh, thu tiền, điểm danh) vào kịch bản k6: hiện chỉ đo đọc.
- [ ] Bài test tải nhỏ trong CI (`PROFILE=steady RATE=100` vào staging) để phát hiện thay đổi làm chậm.

## 5. Khi có sự cố, hệ thống phản ứng thế nào (đã diễn tập)

Diễn tập trên máy dev, 2 tiến trình API, dữ liệu cỡ thật, k6 bắn đều 150 req/s:

| Tình huống | Lúc đầu | Bây giờ (đo được) |
|---|---|---|
| Tải vượt sức | Treo cứng, phải khởi động lại | Phần vượt xếp hàng tối đa 3 giây rồi 503; hết tải tự hồi phục |
| Giết 1 tiến trình API (kill -9) | – | **0 request lỗi**; uvicorn tự khởi động lại tiến trình, p95 lên 173 ms vài giây |
| Tắt Redis 30 giây | – | **0 request lỗi**, không có lúc đứng (bản đầu tiên của cơ chế dự phòng bị đứng 1–3 giây mỗi 5 giây: đã sửa) |
| Khoá cả bảng học viên 20 giây | – | Không treo. Trong lúc khoá **mọi trang đều trả 503**; nhả khoá thì khoảng 3 giây sau chạy lại bình thường |
| Một câu SQL chạy mãi | Giữ kết nối vô hạn | Bị huỷ sau 15 giây; chờ khoá quá 5 giây cũng bị huỷ |
| Groq khoá sai / lỗi | Thử lại cộng dồn có thể vài phút | Khoá sai: báo lỗi sau 1,2 giây (trước khi lọc lỗi: 15 giây). Bị giới hạn (429): tối đa 45 giây |
| Chat dồn nhiều | Chiếm chung 40 luồng, trang thường chậm theo | Chat async không giữ luồng; tối đa `LLM_MAX_CONCURRENT` lượt toàn hệ thống, quá thì báo bận ngay |
| Người dùng đóng trình duyệt giữa câu chat | LLM chạy tiếp tới hết | Huỷ lời gọi, trả chỗ ngay (đo: chỗ được trả trong vài giây) |
| Chạy 2 worker | Agent hằng ngày có thể chạy trùng | Khoá theo tên agent, worker thứ hai bỏ qua |
| 1 máy API chết | Toàn hệ thống dừng | Cấu hình: Caddy gỡ máy đó sau tối đa 5 giây, lỗi kết nối thì thử máy khác (cần ≥ 2 máy; chưa diễn tập nhiều máy) |
| Máy database chết | Dừng; mất dữ liệu tới 24 giờ | ⏳ như cũ cho tới khi có bản sao + sao lưu WAL |

**Còn lại một điểm yếu:** khoá cả bảng (migration nặng, `VACUUM FULL`, `LOCK TABLE`) làm mọi trang lỗi trong thời
gian khoá, vì các request kẹt chờ khoá giữ chỗ chạy (tối đa 5 giây mỗi request) và đẩy các request khác quá hạn. Cách
giảm: chạy migration nặng lúc vắng, migration tự đặt `lock_timeout` ngắn; về lâu dài tách ngăn chỗ chạy theo nhóm
trang (bulkhead) để một bảng kẹt không kéo theo cả hệ thống.

## 6. Chat LLM: tính theo số người chat cùng lúc

Chat không đo được bằng req/s như trang thường: mỗi câu kéo dài 5–20 giây và tốn token.

- **Giới hạn thật là nhà cung cấp LLM.** Đã đo: một câu hỏi Copilot cần agent phân tích chạy SQL bị Groq gói miễn phí
  trả 429 và bắt chờ 17–22 giây giữa các lần gọi; giới hạn 45 giây cắt câu đó lại và báo người dùng. Chạy thật bắt
  buộc phải dùng gói trả phí và đặt hạn mức chi tiêu, rồi đặt `LLM_MAX_CONCURRENT` theo hạn mức đó.
- **Phía máy chủ:** chat đã async, một tiến trình `api-chat` giữ được hàng trăm cuộc chat đang chờ LLM
  (`MAX_CONCURRENT_STREAMS`, mặc định 500 trong compose production). Giới hạn còn lại là hạn mức LLM và tiền.
- **Ước lượng nhu cầu:** nếu 5% người đang dùng hỏi Copilot mỗi phút, 5.000 người là 250 câu/phút, khoảng 1 triệu
  token mỗi phút. Cần đàm phán hạn mức với nhà cung cấp, và cache câu trả lời cho câu hỏi lặp lại của chatbot công
  khai (học phí, lịch khai giảng).
- Câu trả lời đã đo qua đường async: học viên hỏi học phí + trả góp, 2 tool, 156 mẩu chữ, 6,8 giây.

## 7. Cấu hình (biến môi trường)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `REDIS_URL` | trống | Bắt buộc khi nhiều tiến trình / nhiều máy. Trống = RAM của từng tiến trình |
| `REDIS_TIMEOUT` | 0.25 | Giây chờ mỗi lệnh Redis, lỗi thì dùng RAM (thử lại mỗi 5 giây) |
| `DB_POOL_SIZE` | 10 | Kết nối pool chính mỗi tiến trình |
| `DB_AUTH_POOL_SIZE` | 4 | Pool riêng cho bước kiểm tra đăng nhập |
| `DB_ASYNC_POOL_SIZE` | 10 | Pool async của chat (trạng thái hội thoại) |
| `DB_POOL_TIMEOUT` | 5 | Giây chờ kết nối tối đa, quá thì 503 |
| `DB_STATEMENT_TIMEOUT_MS` | 15000 | Câu SQL quá thời gian này bị huỷ |
| `DB_LOCK_TIMEOUT_MS` | 5000 | Chờ khoá quá thời gian này thì 503 |
| `DB_IDLE_IN_TRANSACTION_TIMEOUT_MS` | 60000 | Transaction đứng im quá lâu bị đóng, nhả khoá |
| `DB_VIA_PGBOUNCER` | false | Đi qua PgBouncer: không gửi tham số phiên (timeout đặt bằng ALTER ROLE khi chạy setup) |
| `DB_PGBOUNCER_PREPARED` | true | Giữ prepared statement qua PgBouncer >= 1.21; bản cũ hơn đặt false |
| `DATABASE_READ_URL` | trống | Bản sao chỉ đọc cho trang công khai |
| `THREAD_POOL_SIZE` | 100 | Số luồng chạy hàm `def` (FastAPI mặc định 40) |
| `MAX_CONCURRENT_REQUESTS` | 32 | Request thường chạy cùng lúc mỗi tiến trình (0 = tắt kiểm soát) |
| `MAX_QUEUED_REQUESTS` | 500 | Hàng chờ tối đa, đầy thì 503 |
| `QUEUE_TIMEOUT_SECONDS` | 3 | Chờ trong hàng quá lâu thì 503 |
| `MAX_CONCURRENT_STREAMS` | 200 | Chat đang trả lời mỗi tiến trình (async, không giữ luồng) |
| `CHAT_TURN_TIMEOUT_SECONDS` | 45 | Tổng thời gian tối đa một câu chat |
| `LLM_MAX_CONCURRENT` | 30 | Lượt chat đang gọi LLM trên toàn hệ thống |
| `LLM_REQUEST_TIMEOUT_SECONDS` | 25 | Một lần gọi LLM |
| `BACKGROUND_LLM_TIMEOUT_SECONDS` | 15 | Worker soạn lời văn, quá thì dùng bản mẫu |
| `CHAT_TOOL_THREADS` | 64 | Luồng chạy tool lá của chat async |
| `METRICS_TOKEN` | trống | Bảo vệ `/metrics` |
| `WEB_CONCURRENCY` (`API_WORKERS`) | 1 (2 ở production) | Số tiến trình uvicorn. Production cần `REDIS_URL` nếu > 1 |

Ràng buộc: `MAX_CONCURRENT_REQUESTS + 16 < THREAD_POOL_SIZE`, sai thì API không khởi động. Tổng kết nối của mọi tiến
trình phải nhỏ hơn `max_connections` của Postgres (production mặc định 150), hoặc bật PgBouncer.

## 8. Giới hạn của phép đo

- Máy đo là laptop chạy Docker Desktop 2 vCPU; k6 chạy trên cùng máy nên tranh CPU với hệ thống. Gần trần, kết quả
  dao động mạnh giữa các lần chạy (cùng cấu hình có lần lỗi 0%, có lần vài %).
- Dữ liệu cỡ thật là dữ liệu demo nhân bản: phân bố giống nhau, nên có thể còn truy vấn chậm với dữ liệu thật lệch
  hơn (VD tìm theo tên trên 50.000 đơn mất khoảng 210 ms: cần index trigram `pg_trgm` nếu dùng nhiều).
- Chỉ đo request đọc (GET). Ghi ít hơn nhiều nhưng tốn hơn và giữ khoá; cần thêm vào kịch bản (giai đoạn 5).
- Chat chỉ đo từng câu, chưa đo nhiều người chat cùng lúc (cần hạn mức LLM trả phí).
- Con số cho cấu hình đích là ngoại suy tuyến tính từ 1–2 tiến trình; mục 3 đã để dư khoảng 40%.
