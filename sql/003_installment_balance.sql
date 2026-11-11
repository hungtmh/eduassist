-- Phần CHƯA ĐÓNG của từng đợt: tiền đã thu của hoá đơn được phân bổ lần lượt vào đợt 1, rồi đợt 2.
-- Mọi số "nợ quá hạn", "sắp tới hạn" và số tiền trong email nhắc nợ đều đọc từ view này (một nguồn duy nhất).
CREATE OR REPLACE VIEW dot_con_lai AS
SELECT x.id, x.don_hang_id, x.so_thu_tu,
       (x.so_tien - LEAST(x.so_tien, GREATEST(0, coalesce(p.da_dong, 0)
            - coalesce(sum(x.so_tien) OVER (PARTITION BY x.don_hang_id ORDER BY x.so_thu_tu
                                            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0))))::int AS con_lai
FROM dot_thanh_toan x
LEFT JOIN (SELECT don_hang_id, sum(so_tien) FILTER (WHERE so_tien > 0) AS da_dong
           FROM thanh_toan GROUP BY don_hang_id) p ON p.don_hang_id = x.don_hang_id
WHERE x.trang_thai <> 'da_huy';
COMMENT ON VIEW dot_con_lai IS 'Số tiền còn phải đóng của từng đợt (đã trừ phần tiền đã thu phân bổ theo thứ tự đợt)';
