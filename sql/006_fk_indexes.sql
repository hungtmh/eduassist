-- 006: index cho các cột khoá ngoại và cột lọc thường dùng.
--
-- Postgres KHÔNG tự tạo index cho khoá ngoại. Thiếu index, mỗi lần đếm sĩ số một lớp, tính công nợ một đơn,
-- hay mở hồ sơ một học viên đều phải quét cả bảng (phát hiện khi test tải: danh sách lớp quét toàn bộ don_hang
-- một lần cho MỖI lớp). Dữ liệu demo nhỏ nên chưa thấy chậm; ở trung tâm thật (hàng chục nghìn đơn,
-- hàng trăm nghìn lượt điểm danh) đây là khác biệt giữa vài mili-giây và vài giây.
--
-- Bảng đã lớn trên production: chạy từng lệnh bằng CREATE INDEX CONCURRENTLY ngoài transaction để không khoá
-- ghi; migration này dùng bản thường vì chạy lúc cài đặt / dữ liệu còn nhỏ.

-- Ghi danh: đếm sĩ số theo lớp, lịch sử học theo học viên
CREATE INDEX IF NOT EXISTS don_hang_lop_hoc_idx      ON don_hang (lop_hoc_id, trang_thai_hoc);
CREATE INDEX IF NOT EXISTS don_hang_hoc_vien_idx     ON don_hang (hoc_vien_id);
CREATE INDEX IF NOT EXISTS don_hang_voucher_idx      ON don_hang (voucher_id) WHERE voucher_id IS NOT NULL;

-- Tiền: công nợ = phải thu - tổng đã thu của từng đơn
CREATE INDEX IF NOT EXISTS thanh_toan_don_hang_idx   ON thanh_toan (don_hang_id);
CREATE INDEX IF NOT EXISTS hoan_phi_don_hang_idx     ON hoan_phi (don_hang_id);
CREATE INDEX IF NOT EXISTS bao_luu_don_hang_idx      ON bao_luu (don_hang_id);
CREATE INDEX IF NOT EXISTS voucher_hoc_vien_idx      ON voucher (hoc_vien_id);

-- Học vụ: điểm danh theo học viên (tỉ lệ vắng), lớp theo khoá / giảng viên / phòng
-- Ngày kết thúc lớp = max(ngay) các buổi: thiếu index này Postgres quét ngược cả bảng buổi học cho TỪNG lớp
CREATE INDEX IF NOT EXISTS buoi_hoc_lop_ngay_idx     ON buoi_hoc (lop_hoc_id, ngay);
CREATE INDEX IF NOT EXISTS diem_danh_don_hang_idx    ON diem_danh (don_hang_id);
CREATE INDEX IF NOT EXISTS lop_hoc_khoa_hoc_idx      ON lop_hoc (khoa_hoc_id);
CREATE INDEX IF NOT EXISTS lop_hoc_giang_vien_idx    ON lop_hoc (giang_vien_id);
CREATE INDEX IF NOT EXISTS lop_hoc_phong_hoc_idx     ON lop_hoc (phong_hoc_id);
CREATE INDEX IF NOT EXISTS yeu_cau_hoc_vien_idx      ON yeu_cau (hoc_vien_id);
CREATE INDEX IF NOT EXISTS yeu_cau_don_hang_idx      ON yeu_cau (don_hang_id);

-- Tuyển sinh: bảng khách theo người phụ trách, lịch hẹn theo khách
CREATE INDEX IF NOT EXISTS khach_phu_trach_idx       ON khach_tiem_nang (phu_trach, trang_thai);
CREATE INDEX IF NOT EXISTS khach_khoa_quan_tam_idx   ON khach_tiem_nang (khoa_quan_tam_id);
CREATE INDEX IF NOT EXISTS khach_hoc_vien_idx        ON khach_tiem_nang (hoc_vien_id) WHERE hoc_vien_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS lich_hen_khach_idx        ON lich_hen (khach_id);
CREATE INDEX IF NOT EXISTS lich_hen_lop_hoc_idx      ON lich_hen (lop_hoc_id) WHERE lop_hoc_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS viec_nguoi_phu_trach_idx  ON viec_can_lam (nguoi_phu_trach);

-- Nhật ký, email, đề xuất
CREATE INDEX IF NOT EXISTS email_log_hoc_vien_idx    ON email_log (hoc_vien_id);
CREATE INDEX IF NOT EXISTS audit_log_de_xuat_idx     ON audit_log (de_xuat_id) WHERE de_xuat_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS de_xuat_lan_chay_idx      ON de_xuat_agent (lan_chay_id);
CREATE INDEX IF NOT EXISTS password_reset_user_idx   ON password_reset (username);

ANALYZE;
