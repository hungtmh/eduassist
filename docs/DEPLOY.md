# Triển khai EduAssist lên production

Hướng dẫn này dùng một máy chủ Linux có Docker, một tên miền trỏ về máy chủ, và một dịch vụ gửi email thật.

## 1. Chuẩn bị

| Cần có | Ghi chú |
|---|---|
| Máy chủ | Tối thiểu 2 vCPU, 4 GB RAM, 30 GB ổ đĩa (máy 4 GB: đặt `PG_SHARED_BUFFERS=512MB`, `API_WORKERS=1`). Nên dùng 4 vCPU, 8 GB. Ubuntu 24.04 + Docker Engine + Docker Compose v2. Máy 2 vCPU chịu khoảng 250 request/giây (đo trong `loadtest/README.md`), đủ cho trung tâm vài nghìn người dùng |
| Tên miền | Bản ghi A trỏ về IP máy chủ (VD `app.anhduong.vn`). Mở cổng 80 và 443 |
| Email gửi đi | SMTP của Google Workspace, Amazon SES, SendGrid, Mailgun... Cấu hình SPF, DKIM, DMARC cho tên miền gửi |
| Khoá LLM | `GROQ_API_KEY` (gói trả phí nếu nhiều người dùng; gói miễn phí giới hạn 8K token/phút) |

## 2. Cấu hình

```bash
git clone <repo> eduassist && cd eduassist
cp .env.production.example .env.production
chmod 600 .env.production
```

Điền `.env.production`. Tạo chuỗi ngẫu nhiên cho `JWT_SECRET`, `POSTGRES_PASSWORD`, `AGENT_RO_PASSWORD`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

API **từ chối khởi động** nếu `APP_ENV=production` mà còn khoá mặc định, khoá ngắn hơn 32 ký tự, `CORS_ORIGINS=*`,
hoặc SMTP không mã hoá tới máy chủ email thật.

## 3. Chạy

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.production logs setup
```

Log của `setup` in mật khẩu tạm của tài khoản quản lý đầu tiên (nếu không đặt `ADMIN_PASSWORD`). Đăng nhập tại
`https://<APP_DOMAIN>`, hệ thống bắt đổi mật khẩu ngay.

Production không có dữ liệu giả lập. Thứ tự nhập dữ liệu ban đầu:

1. **Danh mục đào tạo** → Cơ sở & phòng → Giảng viên → Khoá học.
2. **Người dùng** → tạo tài khoản nhân viên (mật khẩu tạm hiện một lần, hoặc gửi link kích hoạt qua email).
3. **Lớp học** → mở lớp. **Học viên** → ghi danh → nút *Cấp tài khoản* gửi link kích hoạt cho học viên.

## 4. Những gì file production đã lo

- HTTPS tự động (Caddy + Let's Encrypt), chuyển http → https, header bảo mật (HSTS, chống nhúng iframe...).
- Web và API chung một tên miền: `/api/*` → API. Không có vấn đề CORS, không lộ cổng 8000.
- Chống quá tải: API chạy `API_WORKERS` tiến trình, chat chạy dịch vụ riêng (`api-chat`, async), Redis giữ giới hạn
  lượt gọi và cache dùng chung; vượt sức thì trả 503 nhanh và tự hồi phục. Lên nhiều máy, PgBouncer, theo dõi bằng
  `/metrics`: [`SCALING_PLAN.md`](SCALING_PLAN.md).
- Database **không mở cổng** ra ngoài.
- Giờ Việt Nam cho container và PostgreSQL (lịch agent, "hôm nay", hạn thanh toán).
- Tự khởi động lại khi lỗi, log xoay vòng (20 MB × 5 file mỗi service).
- `/docs` của API tắt ở production.
- Sao lưu DB mỗi ngày lúc `BACKUP_HOUR` vào `./backups`, giữ `BACKUP_KEEP_DAYS` ngày.

## 5. Sao lưu: việc bạn PHẢI làm thêm

`./backups` nằm trên cùng máy chủ: máy hỏng là mất cả dữ liệu lẫn bản sao lưu. Chép ra nơi khác mỗi ngày, ví dụ
bằng `rclone` lên Google Drive / S3 (cron trên máy chủ):

```cron
30 3 * * * rclone sync /opt/eduassist/backups remote:eduassist-backups
```

**Thử khôi phục** ít nhất một lần, tốt nhất trên máy khác:

```bash
sh deploy/restore.sh backups/eduassist-20261112-0200.dump
```

## 6. Cập nhật phiên bản

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production exec backup pg_dump -Fc -f /backups/truoc-cap-nhat.dump
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

Service `setup` chạy migration trước khi API khởi động lại.

## 7. Theo dõi lỗi (tuỳ chọn)

Đặt `SENTRY_DSN` để API và worker báo lỗi lên Sentry. Không gửi IP, cookie hay header đăng nhập
(`send_default_pii=False`).

## 8. Còn thiếu (xem docs/PRODUCTION_CHECKLIST.md)

Web công khai giới thiệu khoá học, cookie httpOnly thay cho localStorage, rate limit dùng Redis khi chạy nhiều
instance, cảnh báo khi worker ngừng chạy, sao lưu tự động ra ngoài máy chủ, môi trường staging.
