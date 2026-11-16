#!/bin/sh
# PgBouncer chế độ transaction trước Postgres: hàng trăm kết nối phía ứng dụng (mỗi tiến trình API mở vài pool)
# dùng chung vài chục kết nối Postgres thật. Cấu hình sinh từ biến môi trường mỗi lần khởi động.
#
# Ứng dụng đi qua PgBouncer phải đặt DB_VIA_PGBOUNCER=true (eduassist/db.py): không gửi tham số phiên.
# Timeout của phiên do setup đặt bằng ALTER ROLE. Setup / migration / sao lưu nối THẲNG Postgres.
set -eu

: "${DB_HOST:=db}" "${DB_PORT:=5432}" "${DB_NAME:=eduassist}"
: "${APP_USER:=app_rw}" "${APP_PASSWORD:?đặt APP_PASSWORD}"
: "${RO_USER:=agent_ro}" "${RO_PASSWORD:?đặt RO_PASSWORD}"
# Kết nối Postgres thật cho mỗi cặp (database, user). Tổng phải nhỏ hơn max_connections của Postgres.
: "${POOL_SIZE:=40}" "${RO_POOL_SIZE:=10}" "${MAX_DB_CONNECTIONS:=80}" "${MAX_CLIENT_CONN:=3000}"

umask 077
cat > /etc/pgbouncer/userlist.txt <<EOF
"${APP_USER}" "${APP_PASSWORD}"
"${RO_USER}" "${RO_PASSWORD}"
EOF

cat > /etc/pgbouncer/pgbouncer.ini <<EOF
[databases]
${DB_NAME} = host=${DB_HOST} port=${DB_PORT} dbname=${DB_NAME}

[users]
${RO_USER} = pool_size=${RO_POOL_SIZE}

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
default_pool_size = ${POOL_SIZE}
reserve_pool_size = 10
reserve_pool_timeout = 2
max_db_connections = ${MAX_DB_CONNECTIONS}
max_client_conn = ${MAX_CLIENT_CONN}
; Chờ kết nối Postgres quá 10 giây thì báo lỗi cho ứng dụng (ứng dụng trả 503), không treo
query_wait_timeout = 10
server_idle_timeout = 60
server_reset_query =
; Prepared statement của psycopg qua chế độ transaction (PgBouncer >= 1.21). Tắt đi thì Postgres tốn thêm CPU
max_prepared_statements = 200
; Client lỡ gửi options (quên DB_VIA_PGBOUNCER) thì bỏ qua thay vì từ chối; timeout vẫn có nhờ ALTER ROLE
ignore_startup_parameters = extra_float_digits,options
stats_users = ${APP_USER}
log_connections = 0
log_disconnections = 0
EOF

exec pgbouncer /etc/pgbouncer/pgbouncer.ini
