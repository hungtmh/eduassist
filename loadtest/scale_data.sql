-- Phóng to dữ liệu demo lên cỡ một trung tâm lớn để test tải (docs/SCALING_PLAN.md, giai đoạn 5).
-- CHỈ chạy trên database RIÊNG chép từ dữ liệu demo, KHÔNG chạy trên dữ liệu thật (xem loadtest/README.md):
--
--   docker compose exec -T db createdb -U app_rw eduassist_scale
--   docker compose exec -T db sh -c "pg_dump -U app_rw eduassist | psql -q -U app_rw eduassist_scale"
--   docker compose exec -T db psql -U app_rw -d eduassist_scale -v ON_ERROR_STOP=1 -f - < loadtest/scale_data.sql
--
-- Kết quả (từ 421 học viên / 618 đơn / 86 lớp demo): khoảng 10.100 học viên, 50.000 đơn, 2.150 lớp, 56.000 buổi học,
-- 1,2 triệu lượt điểm danh, 3.000 khách tiềm năng. Lớp nhân bản dời về quá khứ (lớp đã học xong) nên lịch tuần
-- này của giảng viên không bị nhân lên, còn mọi truy vấn tổng hợp (công nợ, chuyên cần, doanh thu) chạy trên bảng lớn.
\set ON_ERROR_STOP 1
\timing on
SET statement_timeout = 0;

DO $$
BEGIN
  IF current_database() NOT LIKE '%scale%' THEN
    RAISE EXCEPTION 'Chỉ chạy trên database có tên chứa "scale" (đang ở %)', current_database();
  END IF;
  IF EXISTS (SELECT 1 FROM lop_hoc WHERE ma_lop LIKE '%-S1') THEN
    RAISE EXCEPTION 'Database này đã được phóng to rồi';
  END IF;
END $$;

BEGIN;

-- Lớp: mỗi lớp demo thêm 24 bản, bản thứ k lùi về quá khứ k*35 ngày
CREATE TEMP TABLE map_lop AS
  SELECT l.id AS old_id, k, nextval('lop_hoc_id_seq')::int AS new_id FROM lop_hoc l, generate_series(1, 24) k;
INSERT INTO lop_hoc (id, ma_lop, khoa_hoc_id, ngay_khai_giang, ca_hoc, lich_hoc, hinh_thuc, si_so_toi_da, giang_vien,
                     trang_thai, giang_vien_id, phong_hoc_id, si_so_toi_thieu)
SELECT m.new_id, l.ma_lop || '-S' || m.k, l.khoa_hoc_id, l.ngay_khai_giang - m.k * 35, l.ca_hoc, l.lich_hoc,
       l.hinh_thuc, l.si_so_toi_da, l.giang_vien,
       CASE WHEN l.trang_thai = 'da_huy' THEN 'da_huy' ELSE 'da_ket_thuc' END,
       l.giang_vien_id, l.phong_hoc_id, l.si_so_toi_thieu
FROM map_lop m JOIN lop_hoc l ON l.id = m.old_id;

CREATE TEMP TABLE map_buoi AS
  SELECT b.id AS old_id, m.k, m.new_id AS lop_new, nextval('buoi_hoc_id_seq')::int AS new_id
  FROM buoi_hoc b JOIN map_lop m ON m.old_id = b.lop_hoc_id;
INSERT INTO buoi_hoc (id, lop_hoc_id, so_thu_tu, ngay, trang_thai)
SELECT mb.new_id, mb.lop_new, b.so_thu_tu, b.ngay - mb.k * 35, CASE WHEN b.trang_thai = 'nghi' THEN 'nghi' ELSE 'da_hoc' END
FROM map_buoi mb JOIN buoi_hoc b ON b.id = mb.old_id;

-- Học viên: thêm 23 bản mỗi người (email / SĐT khác nhau)
CREATE TEMP TABLE map_hv AS
  SELECT h.id AS old_id, k, nextval('hoc_vien_id_seq')::int AS new_id FROM hoc_vien h, generate_series(1, 23) k;
INSERT INTO hoc_vien (id, ho_ten, email, so_dien_thoai, nam_sinh, thanh_pho, nguon, ngay_dang_ky)
SELECT m.new_id, h.ho_ten, 's' || m.k || '.' || h.email, '09' || lpad(((m.new_id * 7919) % 100000000)::text, 8, '0'),
       h.nam_sinh, h.thanh_pho, h.nguon, h.ngay_dang_ky - m.k * 35
FROM map_hv m JOIN hoc_vien h ON h.id = m.old_id;

-- Đơn: mỗi đơn demo thêm 80 bản, gắn học viên bản (k mod 23) và lớp bản (k mod 24)
CREATE TEMP TABLE map_dh AS
  SELECT d.id AS old_id, k, ((k - 1) % 24) + 1 AS lop_k, nextval('don_hang_id_seq')::int AS new_id
  FROM don_hang d, generate_series(1, 80) k;
INSERT INTO don_hang (id, hoc_vien_id, lop_hoc_id, ngay_dat, hoc_phi_goc, giam_gia, thanh_tien, trang_thai,
                      trang_thai_hoc, tra_gop, voucher_id, da_chuyen_lop, created_by)
SELECT m.new_id, hv.new_id, ml.new_id, d.ngay_dat - m.lop_k * 35, d.hoc_phi_goc, d.giam_gia, d.thanh_tien,
       -- Lớp đã học xong: phần lớn đã đóng đủ, một ít còn nợ (để báo cáo công nợ có dữ liệu)
       CASE WHEN d.trang_thai IN ('da_huy', 'da_hoan_tien') THEN d.trang_thai
            WHEN m.k % 10 = 0 THEN 'thanh_toan_mot_phan' ELSE 'da_thanh_toan' END,
       CASE WHEN d.trang_thai IN ('da_huy', 'da_hoan_tien') THEN 'da_huy' ELSE 'hoan_thanh' END,
       d.tra_gop, NULL, false, d.created_by
FROM map_dh m
JOIN don_hang d ON d.id = m.old_id
JOIN map_hv hv ON hv.old_id = d.hoc_vien_id AND hv.k = ((m.k - 1) % 23) + 1
JOIN map_lop ml ON ml.old_id = d.lop_hoc_id AND ml.k = m.lop_k;

INSERT INTO thanh_toan (don_hang_id, ngay_thanh_toan, so_tien, phuong_thuc, ghi_chu, created_by)
SELECT d.id, d.ngay_dat + 3, CASE WHEN d.trang_thai = 'da_thanh_toan' THEN d.thanh_tien ELSE d.thanh_tien / 2 END,
       (ARRAY['chuyen_khoan', 'tien_mat', 'the'])[1 + d.id % 3], 'dữ liệu test tải', 'loadtest'
FROM don_hang d JOIN map_dh m ON m.new_id = d.id
WHERE d.trang_thai IN ('da_thanh_toan', 'thanh_toan_mot_phan');

-- Điểm danh: mọi buổi đã học của lớp, mỗi học viên của lớp (khoảng 1,2 triệu dòng)
INSERT INTO diem_danh (buoi_hoc_id, don_hang_id, trang_thai, updated_by)
SELECT mb.new_id, m.new_id,
       CASE WHEN (m.new_id + mb.new_id) % 23 = 0 THEN 'vang'
            WHEN (m.new_id + mb.new_id) % 31 = 0 THEN 'vang_co_phep'
            WHEN (m.new_id + mb.new_id) % 17 = 0 THEN 'di_tre' ELSE 'co_mat' END,
       'loadtest'
FROM map_dh m
JOIN don_hang d ON d.id = m.new_id AND d.trang_thai_hoc = 'hoan_thanh'
JOIN map_buoi mb ON mb.lop_new = d.lop_hoc_id
JOIN buoi_hoc b ON b.id = mb.new_id AND b.trang_thai = 'da_hoc';

-- Khách tiềm năng: thêm 50 bản mỗi khách, phần lớn đã xử lý xong (ghi danh / dừng)
INSERT INTO khach_tiem_nang (ho_ten, so_dien_thoai, email, nguon, nhu_cau, khoa_quan_tam_id, trang_thai, phu_trach,
                             diem, lien_he_cuoi, created_at, updated_at)
SELECT k.ho_ten, '08' || lpad(((k.id * 104729 + g) % 100000000)::text, 8, '0'),
       CASE WHEN k.email IS NULL THEN NULL ELSE 'k' || g || '.' || k.email END,
       k.nguon, k.nhu_cau, k.khoa_quan_tam_id,
       CASE WHEN g % 5 = 0 THEN k.trang_thai WHEN g % 2 = 0 THEN 'da_ghi_danh' ELSE 'khong_tiep_tuc' END,
       k.phu_trach, k.diem, k.lien_he_cuoi - make_interval(days => g * 7), k.created_at - make_interval(days => g * 7),
       k.updated_at - make_interval(days => g * 7)
FROM khach_tiem_nang k, generate_series(1, 50) g;

COMMIT;

ANALYZE;

SELECT 'hoc_vien' AS bang, count(*) FROM hoc_vien
UNION ALL SELECT 'don_hang', count(*) FROM don_hang
UNION ALL SELECT 'lop_hoc', count(*) FROM lop_hoc
UNION ALL SELECT 'buoi_hoc', count(*) FROM buoi_hoc
UNION ALL SELECT 'diem_danh', count(*) FROM diem_danh
UNION ALL SELECT 'thanh_toan', count(*) FROM thanh_toan
UNION ALL SELECT 'khach_tiem_nang', count(*) FROM khach_tiem_nang;
