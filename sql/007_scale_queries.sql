-- Truy vấn nhanh trên dữ liệu lớn (đo bằng loadtest/scale_data.sql: 50.000 đơn, 45.000 lần thu tiền).

-- dot_con_lai: trước đây cộng TOÀN BỘ bảng thanh_toan theo đơn rồi mới ghép với các đợt trả góp (khoảng 10 ms mỗi
-- lần, cho mọi đơn kể cả đơn không trả góp). LATERAL chỉ cộng tiền của đúng những đơn có đợt, tra theo index
-- thanh_toan_don_hang_idx. Cùng kết quả.
CREATE OR REPLACE VIEW dot_con_lai AS
SELECT x.id, x.don_hang_id, x.so_thu_tu,
       (x.so_tien - LEAST(x.so_tien, GREATEST(0, coalesce(p.da_dong, 0)
            - coalesce(sum(x.so_tien) OVER (PARTITION BY x.don_hang_id ORDER BY x.so_thu_tu
                                            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0))))::int AS con_lai
FROM dot_thanh_toan x
LEFT JOIN LATERAL (SELECT sum(so_tien) FILTER (WHERE so_tien > 0) AS da_dong
                   FROM thanh_toan t WHERE t.don_hang_id = x.don_hang_id) p ON true
WHERE x.trang_thai <> 'da_huy';
COMMENT ON VIEW dot_con_lai IS 'Số tiền còn phải đóng của từng đợt (đã trừ phần tiền đã thu phân bổ theo thứ tự đợt)';

-- Doanh thu theo ngày / tháng, "đã thu hôm nay" (bản tin, việc hôm nay của kế toán)
CREATE INDEX IF NOT EXISTS thanh_toan_ngay_idx ON thanh_toan (ngay_thanh_toan);

ANALYZE thanh_toan;

-- Màn hình kế toán mặc định lọc "còn nợ": chỉ vài phần trăm số đơn. Partial index -> đếm và lấy trang không quét
-- cả bảng don_hang.
CREATE INDEX IF NOT EXISTS don_hang_con_no_idx ON don_hang (id)
    WHERE trang_thai IN ('chua_thanh_toan', 'thanh_toan_mot_phan') AND trang_thai_hoc <> 'da_huy';

ANALYZE don_hang;
