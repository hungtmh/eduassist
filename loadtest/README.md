# Test tải API

Dùng [k6](https://k6.io). Kịch bản `api.js` mô phỏng hỗn hợp thao tác theo màn hình mặc định thật: giao diện nhân viên
tự hỏi thông báo và số đề xuất định kỳ, mở danh sách (kế toán lọc "còn nợ", bảng tuyển sinh theo cột), mở chi tiết,
học viên mở cổng, khách xem trang công khai. Mục tiêu (SLO) khai trong script: 95% request dưới 300 ms, 99% dưới
1 giây, lỗi dưới 1%.

```bash
k6 run -e PROFILE=smoke loadtest/api.js                       # chạy thử 15 giây
k6 run -e PROFILE=steady -e RATE=200 -e DURATION=60s loadtest/api.js   # giữ đều 200 request/giây
k6 run loadtest/api.js                                        # tăng dần 50 -> 1000 request/giây (3,5 phút)
k6 run -e BASE=https://staging.example.vn/api loadtest/api.js # chạy vào môi trường khác
k6 run -e PROFILE=steady -e RATE=150 --out csv=ket_qua.csv loadtest/api.js   # ghi từng request (xem theo giây)
```

Cần dữ liệu demo (`uv run eduassist-setup`). Script tự đăng nhập 6 tài khoản demo; API giới hạn đăng nhập 10 lần/phút
mỗi IP nên chạy liên tiếp nhiều lần thì script tự chờ (hoặc xoá bộ đếm: `docker compose exec redis redis-cli flushall`).

Trên Windows, gọi API bằng `127.0.0.1` thay vì `localhost` khi tự đo bằng script: "localhost" thử IPv6 trước, mỗi kết
nối mới mất thêm khoảng 200 ms.

Xem truy vấn tốn thời gian nhất sau một lần chạy (Postgres đã bật `pg_stat_statements`):

```sql
SELECT calls, round(mean_exec_time::numeric, 2) AS mean_ms, round(total_exec_time::numeric) AS total_ms, query
FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 10;
-- đặt lại bộ đếm trước mỗi lần đo: SELECT pg_stat_statements_reset();
```

Chat LLM không có trong kịch bản này: mỗi câu tốn token thật và bị nhà cung cấp LLM giới hạn. Sức chịu tải của chat
tính riêng, xem `docs/SCALING_PLAN.md` mục 6.

## Dữ liệu cỡ thật

Dữ liệu demo nhỏ (421 học viên, 618 đơn) làm mọi truy vấn nhanh hơn thực tế. `scale_data.sql` nhân bản dữ liệu demo
vào một database RIÊNG (từ chối chạy nếu tên database không chứa "scale"):

```bash
docker compose exec -T db createdb -U app_rw eduassist_scale
docker compose exec -T db sh -c "pg_dump -U app_rw eduassist | psql -q -U app_rw eduassist_scale"
docker compose exec -T db psql -U app_rw -d eduassist_scale -v ON_ERROR_STOP=1 -f - < loadtest/scale_data.sql
# khoảng 30 giây: 10.104 học viên, 50.058 đơn, 2.150 lớp, 55.975 buổi học, 1,3 triệu lượt điểm danh, 3.009 khách
```

Cho API dùng database đó bằng một file compose phụ (`DATABASE_URL` / `AGENT_RO_URL` trỏ tới `eduassist_scale`), rồi
chạy k6 như trên. Xoá khi xong: `docker compose exec db dropdb -U app_rw eduassist_scale`.

## Kết quả đo ngày 14/11/2026

Máy: Docker Desktop trên Windows, **2 vCPU, 3,8 GB RAM** (tương đương một VPS nhỏ), k6 chạy trên cùng máy. Số liệu dùng
để so sánh trước/sau và ước lượng, sai số khoảng ±30%; gần trần thì dao động mạnh giữa các lần chạy.

### Bài tăng dần 50 -> 1000 request/giây

| Lần đo | Request thành công | Chuyện gì xảy ra |
|---|---|---|
| Ban đầu | 1.220 | Khoảng 100 req/s thì API **treo cứng**, vẫn treo sau khi hết tải (deadlock thứ nhất) |
| Gỡ deadlock giữa 2 pool, chờ kết nối có hạn | 3.282 | Không còn treo vĩnh viễn nhưng vẫn kẹt theo chu kỳ 5 giây (deadlock thứ hai) |
| Kiểm soát cửa vào (`api/overload.py`) | 17.923 | Ổn định; vượt sức thì trả 503 trong vài giây, tự hồi phục |
| Trả JSON bằng orjson, middleware log ASGI thuần | 30.923 | Cùng 1 nhân CPU, thêm 72% |
| Index khoá ngoại, 2 tiến trình API | 42.037 | Gấp 34 lần ban đầu (dữ liệu demo) |
| Dữ liệu cỡ thật, 2 tiến trình, Redis | 36.337 | Dữ liệu lớn lộ ra truy vấn chậm |
| + sửa truy vấn danh sách, cache bản tin, migration `0007` | **46.210** | Phần vượt sức (máy hết CPU) bị từ chối nhanh bằng 503 |

### Tải đều 60 giây

| Cấu hình | Dữ liệu | Tải | Lỗi | p50 | p95 | p99 |
|---|---|---|---|---|---|---|
| 1 tiến trình, chưa có Redis | demo | 150 req/s | 0% | 7 ms | 62 ms | 360 ms |
| 1 tiến trình, chưa có Redis | demo | 200 req/s | 0% | 26 ms | 364 ms | 704 ms |
| 1 tiến trình, **có Redis** (cache tài khoản) | demo | 170 req/s | 0% | 7–10 ms | 69–98 ms | 155 ms |
| 2 tiến trình, có Redis | demo | 300 req/s | 0% | 54 ms | 625 ms | 797 ms |
| 2 tiến trình, có Redis, trước khi sửa truy vấn | cỡ thật | 300 req/s | 3,5–5% | 2,4 s | 3,3 s | 3,4 s |
| 2 tiến trình, có Redis, sau khi sửa truy vấn | cỡ thật | 250 req/s | 0% | 16 ms | 140 ms | 255 ms |
| 2 tiến trình, có Redis, sau khi sửa truy vấn | cỡ thật | 300 req/s | 0% | 755 ms | 1,35 s | 1,5 s |

Ở 300 req/s trên dữ liệu cỡ thật, API dùng khoảng 107% CPU, Postgres khoảng 37%: máy 2 vCPU đã hết CPU.

### PgBouncer trên cùng một máy

| Tải | Nối thẳng | Qua PgBouncer |
|---|---|---|
| 200 req/s | 0% lỗi, p95 294 ms | 0% lỗi, p95 131 ms |
| 300 req/s | 0% lỗi, p95 625 ms | 7–14% lỗi (503) |

Mỗi truy vấn qua PgBouncer chậm thêm khoảng 0,1 ms; gần trần thì PgBouncer và Postgres tranh CPU với API. Một máy thì
nối thẳng; PgBouncer dành cho nhiều máy API (xem `docs/SCALING_PLAN.md`). Tắt prepared statement không đổi kết quả.

### Truy vấn trên dữ liệu cỡ thật (đo từng request, không tải)

| Endpoint | Trước | Sau |
|---|---|---|
| `/invoices?limit=50` (mọi đơn) | 223 ms | 17 ms |
| `/invoices` trang sâu (offset 49.990) | 695 ms | 32 ms |
| `/classes?limit=50` | 90 ms (trả cả 2.150 lớp) | 11 ms |
| `/dashboard` | 113 ms | 5,5 ms (cache 60 giây) |
| Mọi endpoint còn lại trong kịch bản | 4–14 ms | 4–14 ms |

Mỗi lần sửa truy vấn đều so kết quả bản cũ và bản mới trên cả hai database (demo và cỡ thật): giống hệt.

### Diễn tập sự cố (2 tiến trình, dữ liệu cỡ thật, tải đều 150 req/s)

| Sự cố | Kết quả |
|---|---|
| `kill -9` một tiến trình API | 0 request lỗi; uvicorn khởi động lại tiến trình, p95 lên 173 ms vài giây |
| Tắt Redis 30 giây rồi bật lại | 0 request lỗi, không có lúc đứng; bật lại thì tự dùng Redis |
| Khoá cả bảng `hoc_vien` 20 giây (`LOCK TABLE ... ACCESS EXCLUSIVE`) | Không treo; trong lúc khoá mọi trang trả 503; nhả khoá khoảng 3 giây sau thì bình thường |
| Groq: khoá API sai | Chat báo lỗi sau 1,2 giây (trước khi chỉ thử lại lỗi tạm thời: 15 giây) |
| Groq: gói miễn phí hết hạn mức (429, bắt chờ 17–22 giây) | Câu chat bị cắt ở 45 giây, báo người dùng thử lại |

Lần đầu diễn tập tắt Redis, API đứng 1–3 giây mỗi 5 giây (mọi luồng cùng thử lại Redis một lúc): đã sửa để chỉ một
request thử lại. Lần đầu diễn tập khoá bảng, request chờ khoá tới 15 giây: thêm `lock_timeout` 5 giây.

### Chi phí mỗi request (dùng để tính số máy)

| | Lúc đầu | Dữ liệu demo, sau khi sửa | Dữ liệu cỡ thật, sau khi sửa |
|---|---|---|---|
| CPU Python của API | khoảng 10 ms | khoảng 3,7 ms | khoảng 4 ms |
| CPU Postgres | – | khoảng 1,2 ms | khoảng 1,3 ms (2,2 ms trước khi sửa truy vấn) |
| Chuyển kết quả sang JSON (1.200 request) | 6,3 s | 0,08 s | |
