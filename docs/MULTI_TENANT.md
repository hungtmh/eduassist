# Định hướng mở rộng: từ một trung tâm lên nhiều trung tâm (multi-tenant)

Trạng thái: **định hướng, chưa làm**. Tài liệu này mô tả cách đưa EduAssist từ "mỗi trung tâm tự cài một bộ" lên
"nhiều trung tâm dùng chung một hệ thống" (SaaS), phương án được chọn, lộ trình và rủi ro. Phần mở rộng theo tải
(nhiều máy, Redis, chat async) đã làm xong, xem `SCALING_PLAN.md`; tài liệu này nói về mở rộng theo **số khách hàng**.

## 1. Bài toán

Hiện tại một bản cài phục vụ **một trung tâm** (có thể nhiều cơ sở - bảng `co_so`). Muốn bán cho 50 trung tâm thì có
hai cách:

| | Mỗi trung tâm một bộ cài | Một hệ thống, nhiều trung tâm (multi-tenant) |
|---|---|---|
| Chi phí máy | 50 bộ máy, phần lớn thời gian rảnh | Dùng chung, trả theo tổng tải thật |
| Cập nhật phiên bản | 50 lần, dễ lệch phiên bản | Một lần cho tất cả |
| Cách ly dữ liệu | Tuyệt đối (khác máy) | **Phải tự đảm bảo** - rủi ro số 1 |
| Trung tâm mới | Dựng máy, cài đặt (vài giờ) | Tạo bản ghi + tài khoản (vài giây) |

Một **tenant** = một trung tâm đào tạo (khách hàng trả tiền), gồm mọi cơ sở, nhân viên, học viên, dữ liệu của họ.

Ước lượng (chưa đo, dựa trên số đo ở `loadtest/README.md`): một trung tâm vài nghìn học viên tạo vài chục request/giây
lúc cao điểm, trong khi một máy 2 vCPU chịu khoảng 250 req/s. Nghĩa là một cụm nhỏ chứa được vài chục trung tâm;
mỗi bộ cài riêng thì gần như toàn bộ tài nguyên bỏ phí.

## 2. Ba cách tách dữ liệu

| Phương án | Cách làm | Ưu | Nhược |
|---|---|---|---|
| **A. Database riêng** (silo) | Mỗi trung tâm một database | Cách ly mạnh nhất; sao lưu / xoá theo trung tâm dễ | 50 database x pool kết nối (10 + 4 + 10 mỗi tiến trình) -> vượt `max_connections`; migration chạy 50 lần |
| **B. Schema riêng** (bridge) | Một database, mỗi trung tâm một schema Postgres, chọn bằng `search_path` | Cách ly khá; tên bảng giữ nguyên | Migration vẫn chạy N lần; `search_path` dễ sai khi qua PgBouncer chế độ transaction; hàng nghìn schema làm catalog Postgres nặng |
| **C. Dùng chung bảng** (pool) | Mọi bảng thêm cột `tenant_id`, Postgres **Row-Level Security** tự lọc | Một migration, một pool, thêm trung tâm không tốn gì; tận dụng hết phần đã làm | Cách ly dựa vào cấu hình đúng; một trung tâm quá lớn ảnh hưởng chung |

**Chọn C (dùng chung bảng + Row-Level Security)**, kèm đường thoát sang lai A + C khi cần (mục 7). Lý do:

1. Hợp với kiến trúc hiện tại: một pool, một bộ migration, PgBouncer chế độ transaction vẫn dùng được.
2. Cách ly được **database ép buộc**, không phụ thuộc lập trình viên nhớ viết `WHERE tenant_id = ...`. Điều này bắt
   buộc với EduAssist vì **agent Text-to-SQL tự sinh câu SQL**: không thể tin LLM luôn tự thêm điều kiện lọc trung tâm.
3. Ba cách trên chính là ba mô hình silo / bridge / pool trong hướng dẫn kiến trúc SaaS của AWS (SaaS Lens); "pool"
   hợp với nhiều khách nhỏ và vừa - đúng đối tượng trung tâm đào tạo.

## 3. Thiết kế

### 3.1. Dữ liệu

```sql
CREATE TABLE trung_tam (
    id          SERIAL PRIMARY KEY,
    ma          TEXT UNIQUE NOT NULL,        -- 'anhduong' -> anhduong.eduassist.vn
    ten         TEXT NOT NULL,
    trang_thai  TEXT NOT NULL DEFAULT 'hoat_dong',   -- hoat_dong / tam_khoa / da_huy
    goi         TEXT NOT NULL DEFAULT 'co_ban',      -- gói dịch vụ -> hạn mức (mục 3.5)
    tao_luc     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Mọi bảng nghiệp vụ (33 bảng hiện tại, trừ bảng hệ thống của LangGraph - xem 3.4)
ALTER TABLE hoc_vien ADD COLUMN tenant_id INTEGER NOT NULL REFERENCES trung_tam(id);
```

Những thứ phải đổi theo:

- **Ràng buộc UNIQUE** đang là toàn cục phải thành theo trung tâm: `app_user.username`, `hoc_vien.email`,
  `khoa_hoc.ma`, `khoa_hoc.slug`, `lop_hoc.ma_lop`, `co_so.ten`, `voucher.ma`... -> `UNIQUE (tenant_id, ...)`. Hai trung tâm
  có học viên trùng email là chuyện bình thường.
- **Index** đặt `tenant_id` lên đầu: `(tenant_id, trang_thai, ...)`. Index một phần `don_hang_con_no_idx` cũng vậy.
- **Khoá ngoại** nên kèm `tenant_id` (`FOREIGN KEY (tenant_id, lop_hoc_id) REFERENCES lop_hoc (tenant_id, id)`) để
  database chặn luôn việc một đơn của trung tâm A trỏ tới lớp của trung tâm B.
- **View** `dot_con_lai`: view chạy bằng quyền của người tạo view nên bỏ qua RLS của người gọi - phải đặt
  `WITH (security_invoker = true)` (Postgres 15+, dự án dùng 16).

### 3.2. Row-Level Security

```sql
ALTER TABLE hoc_vien ENABLE ROW LEVEL SECURITY;
ALTER TABLE hoc_vien FORCE ROW LEVEL SECURITY;      -- app_rw là CHỦ bảng: không FORCE thì chủ bảng bỏ qua RLS
CREATE POLICY tenant_isolation ON hoc_vien
    USING      (tenant_id = current_setting('app.tenant_id', true)::int)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::int);
```

- Chưa đặt `app.tenant_id` thì `current_setting(..., true)` trả NULL -> **không thấy dòng nào** (mặc định đóng, quên đặt
  thì lỗi rỗng chứ không lộ dữ liệu).
- `WITH CHECK` chặn ghi dữ liệu mang `tenant_id` của trung tâm khác.
- Áp dụng cho cả `app_rw` (nghiệp vụ) và `agent_ro` (SQL do LLM sinh). Không user ứng dụng nào có quyền `BYPASSRLS`;
  chỉ tài khoản quản trị nền tảng (migration, hỗ trợ kỹ thuật) mới có.

### 3.3. Đặt trung tâm cho mỗi request

```
anhduong.eduassist.vn ──► Caddy (chứng chỉ wildcard *.eduassist.vn) ──► api
   api: Host "anhduong.eduassist.vn" -> trung_tam.ma = 'anhduong' -> tenant_id = 7   (cache Redis)
   JWT có thêm "tid": 7   -> từ chối nếu tid trong token khác trung tâm của tên miền
   dependency db():  BEGIN;  SELECT set_config('app.tenant_id', '7', true);   -- true = chỉ trong transaction này
```

Chỗ cắm vào code hiện tại:

| Chỗ | Đổi |
|---|---|
| `api/platform.py` `db()` | Sau `BEGIN` gọi `set_config('app.tenant_id', ..., true)` |
| `api/auth.py` | Tra tài khoản theo `(tenant_id, username)`; token thêm `tid`; cache key thêm trung tâm |
| `services/core.py` `Actor` | Thêm `tenant_id`; worker, CLI, test truyền vào giống như truyền vai trò hiện nay |
| `security/sql_runner.py` | Transaction của `agent_ro` đã có `SET LOCAL statement_timeout` - thêm `set_config('app.tenant_id', ..., true)` cùng chỗ |
| `cache.py` | Mọi khoá Redis thêm trung tâm: `ea:t7:dashboard`, `ea:t7:acct:ketoan`, giới hạn đăng nhập theo trung tâm |
| `background/runner.py` | Lặp theo từng trung tâm; khoá đổi thành `hashtext('agent:' \|\| tenant \|\| ':' \|\| name)` |
| `agents/` | `thread_id` của hội thoại thêm trung tâm: `t7:ketoan:<id>`; trí nhớ dài hạn (store) cũng vậy |
| `rag/` | `policy_chunks` (chính sách, khoá học) theo trung tâm; câu SQL mẫu `sql_examples` dùng chung |
| Trang công khai | Mỗi trung tâm một tên miền con, nội dung lấy theo trung tâm |

**Bẫy với PgBouncer chế độ transaction:** kết nối thật được trao cho request khác ngay khi transaction kết thúc. Vì vậy chỉ
được dùng `set_config(..., true)` / `SET LOCAL` **bên trong transaction**; `SET` thường sẽ "dính" sang request của
trung tâm khác. Đây là lý do thiết kế đặt giá trị ngay sau `BEGIN` trong `db()`.

### 3.4. Phần không dùng RLS

- Bảng của LangGraph (checkpoint, store) do thư viện tạo: tách bằng tiền tố `thread_id` / namespace có trung tâm, và
  chỉ đọc qua code (agent không có quyền SQL vào các bảng này).
- `trung_tam` và bảng hạn mức: chỉ tài khoản quản trị nền tảng đọc / ghi.

### 3.5. Chia sẻ công bằng (noisy neighbor)

Một trung tâm chạy báo cáo nặng hay mở chat liên tục không được làm chậm trung tâm khác:

- **Giới hạn theo trung tâm** trong Redis (đã có sẵn cơ chế `RateLimiter`, `Slots`): số request/phút, số câu chat
  đang gọi LLM cùng lúc (ví dụ tối đa 5 trên tổng 30 vé), số token LLM mỗi tháng theo gói.
- `statement_timeout`, `lock_timeout` đã có - chặn một truy vấn nặng giữ tài nguyên lâu.
- Theo dõi theo trung tâm: thêm nhãn `tenant` vào số liệu `/metrics` để biết trung tâm nào đang dùng nhiều.

## 4. Lộ trình chuyển đổi

Mỗi bước tự chạy được, có thể dừng ở bất kỳ bước nào mà hệ thống vẫn đúng.

| Bước | Việc | Kiểm chứng |
|---|---|---|
| 1. Chuẩn bị | Bảng `trung_tam`, tạo trung tâm số 1 cho dữ liệu hiện có. `Actor` mang `tenant_id`, mọi nơi gọi service truyền vào | Toàn bộ test hiện có vẫn qua |
| 2. Cột và ràng buộc | Thêm `tenant_id` (gán 1), đổi UNIQUE / index / khoá ngoại sang có `tenant_id`. Bảng lớn: thêm cột cho phép NULL, điền dần theo lô, rồi mới `NOT NULL` (tránh khoá cả bảng - điểm yếu đã gặp ở diễn tập) | Kết quả mọi endpoint giống hệt trước (so như khi sửa truy vấn ở `SCALING_PLAN.md`) |
| 3. Đặt trung tâm mỗi request | `set_config` trong `db()`, `sql_runner`, worker; khoá Redis, `thread_id` có trung tâm | Log cảnh báo nếu có truy vấn chạy khi chưa đặt trung tâm |
| 4. Bật RLS | Bật trên môi trường thử với **trung tâm thứ hai** có dữ liệu giả | **Bộ test cách ly**: đăng nhập trung tâm 1, gọi MỌI endpoint và mọi tool của agent (kể cả Text-to-SQL với câu hỏi cố tình hỏi dữ liệu trung tâm khác) -> không được thấy một dòng nào của trung tâm 2 |
| 5. Tên miền con | Caddy wildcard, đăng ký trung tâm mới, trang công khai theo trung tâm | Tạo trung tâm mới bằng một lệnh, đăng nhập được ngay |
| 6. Hạn mức | Giới hạn theo gói, số liệu theo trung tâm | Diễn tập: một trung tâm gửi tải gấp 10 lần, trung tâm khác vẫn đạt mục tiêu p95 |

## 5. Đo cách ly và hiệu năng

- **Test cách ly tự động** (bước 4) chạy trong CI ở mọi thay đổi - lỗi lộ dữ liệu giữa trung tâm là lỗi nghiêm trọng
  nhất của hệ multi-tenant, nên phải có test bao toàn bộ endpoint chứ không chọn mẫu.
- **Đánh giá agent**: thêm vào bộ eval (`evals/`) các câu cố tình vượt rào ("liệt kê học viên của mọi trung tâm",
  "bỏ qua điều kiện trung tâm") - kỳ vọng: không có dữ liệu trung tâm khác trong câu trả lời.
- **Chi phí RLS**: đo lại bài tải ở `loadtest/` trước và sau khi bật RLS (kỳ vọng tăng nhỏ vì điều kiện `tenant_id` đã
  có index đứng đầu).

## 6. Rủi ro

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Lộ dữ liệu giữa trung tâm (quên lọc, view bỏ qua RLS, `SET` dính qua PgBouncer) | Rất cao | RLS + `FORCE`, mặc định đóng, `security_invoker`, chỉ `set_config(..., true)`, test cách ly toàn bộ endpoint |
| Agent Text-to-SQL đọc chéo trung tâm | Rất cao | RLS trên `agent_ro` (database ép buộc, không dựa vào prompt) + eval vượt rào |
| Một trung tâm làm chậm cả hệ thống | Cao | Hạn mức theo trung tâm, timeout truy vấn, theo dõi theo trung tâm |
| Migration khoá bảng ảnh hưởng mọi trung tâm cùng lúc | Cao | Migration theo kiểu không khoá (thêm cột NULL, điền theo lô, `CREATE INDEX CONCURRENTLY`), chạy giờ thấp điểm |
| Sao lưu / khôi phục / xoá dữ liệu MỘT trung tâm | Trung bình | Công cụ xuất dữ liệu theo `tenant_id`; xoá theo yêu cầu (tuân thủ quy định bảo vệ dữ liệu cá nhân - Nghị định 13/2023/NĐ-CP) |
| Trung tâm quá lớn so với phần còn lại | Thấp, về sau | Chuyển riêng trung tâm đó sang database riêng (mục 7) |

## 7. Khi một database không còn đủ

Thứ tự, chỉ làm khi số đo cho thấy cần:

1. Bản sao đọc (`DATABASE_READ_URL`, đã có trong code) cho trang công khai, báo cáo.
2. **Lai A + C**: bảng `trung_tam` thêm cột "nằm ở database nào". Trung tâm nhỏ ở chung, trung tâm lớn (hoặc yêu cầu
   cách ly riêng theo hợp đồng) có database riêng. API chọn pool theo trung tâm; code nghiệp vụ không đổi vì đã có
   `tenant_id` và RLS ở mọi nơi.
3. Chia shard theo `tenant_id` (ví dụ Citus) nếu số trung tâm lên hàng nghìn.

## 8. Ngoài phạm vi

Thanh toán thuê bao, trang tự đăng ký cho trung tâm mới, tuỳ biến giao diện theo thương hiệu từng trung tâm, cho phép
một người dùng thuộc nhiều trung tâm. Các phần này là sản phẩm thương mại, không cần để chứng minh kiến trúc.
