#!/bin/sh
# Sao lưu PostgreSQL mỗi ngày một lần lúc BACKUP_HOUR (giờ Việt Nam), giữ BACKUP_KEEP_DAYS ngày.
# File: /backups/eduassist-YYYYmmdd-HHMM.dump (định dạng custom của pg_dump, khôi phục bằng deploy/restore.sh).
set -eu

HOUR="${BACKUP_HOUR:-2}"
KEEP="${BACKUP_KEEP_DAYS:-14}"
mkdir -p /backups

dump() {
    name="/backups/eduassist-$(date +%Y%m%d-%H%M).dump"
    if pg_dump --format=custom --no-owner --file="$name.part"; then
        mv "$name.part" "$name"
        echo "$(date -Iseconds) backup ok: $name ($(du -h "$name" | cut -f1))"
    else
        rm -f "$name.part"
        echo "$(date -Iseconds) BACKUP LỖI" >&2
    fi
    find /backups -name 'eduassist-*.dump' -mtime +"$KEEP" -delete
}

# Bản sao lưu đầu tiên ngay khi khởi động, sau đó mỗi ngày một lần
dump
last="$(date +%Y%m%d)"
while true; do
    sleep 600
    today="$(date +%Y%m%d)"
    if [ "$today" != "$last" ] && [ "$(date +%H | sed 's/^0//')" -ge "$HOUR" ]; then
        dump
        last="$today"
    fi
done
