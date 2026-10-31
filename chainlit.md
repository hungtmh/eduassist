# EduAssist 🎓

Trợ lý AI multi-agent cho **Trung tâm Đào tạo Ánh Dương** (dữ liệu giả lập, phục vụ demo).

## Tài khoản demo (mật khẩu `demo123`)

| Tài khoản | Vai trò | Thử hỏi |
|---|---|---|
| `hocvien` | Học viên | "Có cho trả góp học phí không?", "Mình đang học những lớp nào?" |
| `nhanvien` | Nhân viên | "Doanh thu 3 tháng gần nhất?", "Gửi email nhắc 3 học viên nợ nhiều nhất" |
| `quanly` | Quản lý | Như nhân viên, được cấp voucher tới 30% |

## Cách hoạt động
- Mỗi câu hỏi được **Supervisor** giao cho agent phù hợp: Tư vấn (RAG), Phân tích dữ liệu (Text-to-SQL), Vận hành.
- Thao tác thật (gửi email, cấp voucher) luôn **dừng lại chờ bạn duyệt**.
- Bấm 👍 / 👎 dưới câu trả lời để giúp hệ thống học. 👍 của nhân viên cho câu trả lời có SQL sẽ được thêm vào kho ví dụ.
