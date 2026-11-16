#!/bin/sh
# Khôi phục database từ một file sao lưu. GHI ĐÈ toàn bộ dữ liệu hiện tại.
#
#   sh deploy/restore.sh backups/eduassist-20261112-0200.dump
#
# Nên thử khôi phục định kỳ vào một máy khác (hoặc database tạm) để chắc file sao lưu dùng được.
set -eu

FILE="${1:?Cách dùng: sh deploy/restore.sh <file .dump>}"
COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.production"

[ -f "$FILE" ] || { echo "Không thấy file $FILE"; exit 1; }
printf "Sẽ GHI ĐÈ database bằng %s. Gõ 'khoi phuc' để tiếp tục: " "$FILE"
read -r answer
[ "$answer" = "khoi phuc" ] || { echo "Đã huỷ."; exit 1; }

$COMPOSE stop api worker
$COMPOSE exec -T db pg_restore --clean --if-exists --no-owner -U app_rw -d eduassist < "$FILE"
$COMPOSE start api worker
echo "Đã khôi phục. Kiểm tra lại bằng cách đăng nhập và xem vài màn hình."
