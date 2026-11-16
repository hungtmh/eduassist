-- 005: dữ liệu cho web công khai - trang khoá học (slug, mô tả ngắn, lộ trình, đối tượng, đầu ra),
--      hồ sơ giảng viên công khai, ghi nhận sự đồng ý của khách đăng ký tư vấn qua website.

ALTER TABLE khoa_hoc ADD COLUMN IF NOT EXISTS slug       TEXT;
ALTER TABLE khoa_hoc ADD COLUMN IF NOT EXISTS mo_ta_ngan TEXT;
ALTER TABLE khoa_hoc ADD COLUMN IF NOT EXISTS doi_tuong  TEXT;
ALTER TABLE khoa_hoc ADD COLUMN IF NOT EXISTS ket_qua    TEXT;
ALTER TABLE khoa_hoc ADD COLUMN IF NOT EXISTS lo_trinh   JSONB NOT NULL DEFAULT '[]';
UPDATE khoa_hoc SET slug = lower(ma) WHERE slug IS NULL;
ALTER TABLE khoa_hoc ALTER COLUMN slug SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS khoa_hoc_slug_uidx ON khoa_hoc (slug);
COMMENT ON COLUMN khoa_hoc.slug IS 'Đường dẫn trang khoá học trên web công khai: /khoa-hoc/<slug>';
COMMENT ON COLUMN khoa_hoc.lo_trinh IS 'Danh sách giai đoạn [{"ten": ..., "noi_dung": ...}] hiện trên web công khai';

ALTER TABLE giang_vien ADD COLUMN IF NOT EXISTS tieu_su           TEXT;
ALTER TABLE giang_vien ADD COLUMN IF NOT EXISTS hien_thi_cong_khai BOOLEAN NOT NULL DEFAULT true;

ALTER TABLE khach_tiem_nang ADD COLUMN IF NOT EXISTS dong_y_luc   TIMESTAMPTZ;
ALTER TABLE khach_tiem_nang ADD COLUMN IF NOT EXISTS kenh_chi_tiet TEXT;
COMMENT ON COLUMN khach_tiem_nang.dong_y_luc IS 'Lúc khách đồng ý cho trung tâm liên hệ / xử lý dữ liệu (form website)';
COMMENT ON COLUMN khach_tiem_nang.kenh_chi_tiet IS 'Nơi khách để lại thông tin, VD: form:/khoa-hoc/eng-if, chat';
