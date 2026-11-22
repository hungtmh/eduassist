#!/usr/bin/env bash
# Triển khai (hoặc cập nhật) EduAssist lên cluster.
#   bash deploy/k8s/scripts/deploy.sh <tag> [--seed] [--restart]
#     <tag>      tag image do workflow Images build (7 ký tự đầu của commit)
#     --seed     LẦN ĐẦU: nạp dữ liệu mẫu rồi khoá các tài khoản demo (DEMO_MODE=false)
#     --restart  khởi động lại các pod (sau khi đổi config.env, Caddyfile hoặc secrets.env)
#
# Thứ tự: Secret -> Postgres, Redis, NetworkPolicy -> chờ Postgres -> sao lưu (khi cập nhật) -> Job setup
# (migration) -> ứng dụng. Migration lỗi thì dừng trước khi đụng tới phiên bản đang chạy.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/common.sh

TAG=${1:?cần tag image, VD: deploy.sh 1a2b3c4}
SEED=false; RESTART=false
for a in "${@:2}"; do
  case $a in --seed) SEED=true ;; --restart) RESTART=true ;; *) echo "tham số lạ: $a"; exit 2 ;; esac
done

# ---- Bí mật -------------------------------------------------------------------------------------------------
# secrets.env: do bạn điền (Groq, Gmail). .state/generated.env: script tự sinh MỘT lần rồi dùng lại (mật khẩu DB đổi
# mỗi lần deploy thì ứng dụng mất kết nối). Cả hai đều nằm ngoài git.
[ -f secrets.env ] || { echo "thiếu deploy/k8s/secrets.env (chép từ secrets.env.example)"; exit 1; }
set -a; source secrets.env; set +a
: "${GROQ_API_KEY:?secrets.env thiếu GROQ_API_KEY}"
mkdir -p .state
if [ ! -f .state/generated.env ]; then
  rnd() { python -c "import secrets; print(secrets.token_urlsafe($1))"; }
  {
    echo "JWT_SECRET=$(rnd 48)"
    echo "PG_APP_PASSWORD=$(rnd 32)"
    echo "AGENT_RO_PASSWORD=$(rnd 32)"
    echo "METRICS_TOKEN=$(rnd 32)"
  } > .state/generated.env
  log "đã sinh mật khẩu mới vào deploy/k8s/.state/generated.env (giữ file này, đừng commit)"
fi
set -a; source .state/generated.env; set +a

kubectl apply -f namespace.yaml >/dev/null
kubectl -n "$NS" create secret generic eduassist-secrets --dry-run=client -o yaml \
  --from-literal=JWT_SECRET="$JWT_SECRET" \
  --from-literal=METRICS_TOKEN="$METRICS_TOKEN" \
  --from-literal=AGENT_RO_PASSWORD="$AGENT_RO_PASSWORD" \
  --from-literal=DATABASE_URL="postgresql://app_rw:$PG_APP_PASSWORD@eduassist-db-rw:5432/eduassist" \
  --from-literal=DATABASE_READ_URL="postgresql://app_rw:$PG_APP_PASSWORD@eduassist-db-ro:5432/eduassist" \
  --from-literal=AGENT_RO_URL="postgresql://agent_ro:$AGENT_RO_PASSWORD@eduassist-db-ro:5432/eduassist" \
  --from-literal=GROQ_API_KEY="$GROQ_API_KEY" \
  --from-literal=SMTP_USER="${SMTP_USER:-}" \
  --from-literal=SMTP_PASSWORD="${SMTP_PASSWORD:-}" \
  --from-literal=SMTP_FROM="${SMTP_FROM:-${SMTP_USER:-noreply@example.com}}" \
  --from-literal=ADMIN_EMAIL="${ADMIN_EMAIL:-}" \
  | kubectl apply -f - >/dev/null
kubectl -n "$NS" create secret generic eduassist-db-app --type=kubernetes.io/basic-auth --dry-run=client -o yaml \
  --from-literal=username=app_rw --from-literal=password="$PG_APP_PASSWORD" | kubectl apply -f - >/dev/null
BACKUP_KEY=$(az storage account keys list -n "$STORAGE" -g "$DATA_RG" --query "[0].value" -o tsv)
kubectl -n "$NS" create secret generic azure-backup --dry-run=client -o yaml --from-literal=connection-string=\
"DefaultEndpointsProtocol=https;AccountName=$STORAGE;AccountKey=$BACKUP_KEY;EndpointSuffix=core.windows.net" \
  | kubectl apply -f - >/dev/null
cat <<EOF | kubectl apply -f - >/dev/null
apiVersion: barmancloud.cnpg.io/v1
kind: ObjectStore
metadata:
  name: eduassist-backup
  namespace: $NS
spec:
  retentionPolicy: "14d"
  configuration:
    destinationPath: https://$STORAGE.blob.core.windows.net/backups/
    azureCredentials:
      connectionString: {name: azure-backup, key: connection-string}
    wal: {compression: gzip}
    data: {compression: gzip}
EOF

# ---- Dựng toàn bộ manifest một lần rồi tách: phần dữ liệu trước, ứng dụng sau ---------------------------------
RENDERED=$(mktemp)
kubectl kustomize . | sed "s#\(ghcr.io/hungtmh/eduassist-[a-z]*\):TAG#\1:$TAG#" > "$RENDERED"
FIRST_DEPLOY=false
kubectl -n "$NS" get cluster.postgresql.cnpg.io eduassist-db >/dev/null 2>&1 || FIRST_DEPLOY=true

log "Postgres, Redis, NetworkPolicy, ConfigMap"
python - "$RENDERED" <<'PY' | kubectl apply -f - >/dev/null
import sys, yaml
keep = {"Namespace", "ConfigMap", "Cluster", "ScheduledBackup", "NetworkPolicy"}
docs = [d for d in yaml.safe_load_all(open(sys.argv[1], encoding="utf-8")) if d]
out = [d for d in docs if d["kind"] in keep or (d["kind"] in ("Deployment", "Service") and d["metadata"]["name"] == "redis")]
print(yaml.safe_dump_all(out, allow_unicode=True, sort_keys=False))
PY
log "chờ Postgres sẵn sàng (lần đầu khoảng 3-5 phút)"
kubectl -n "$NS" wait cluster.postgresql.cnpg.io/eduassist-db --for=condition=Ready --timeout=15m
kubectl -n "$NS" rollout status deploy/redis --timeout=5m

if ! $FIRST_DEPLOY; then
  log "sao lưu trước khi chạy migration"
  BK="pre-deploy-$(date +%Y%m%d-%H%M%S)"
  cat <<EOF | kubectl apply -f - >/dev/null
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata: {name: $BK, namespace: $NS}
spec:
  cluster: {name: eduassist-db}
  method: plugin
  pluginConfiguration: {name: barman-cloud.cloudnative-pg.io}
EOF
  kubectl -n "$NS" wait "backup.postgresql.cnpg.io/$BK" --for=jsonpath='{.status.phase}'=completed --timeout=15m
fi

run_setup() {  # $1 = DEMO_MODE
  local name="setup-$TAG-$1-$(date +%H%M%S)"
  sed -e "s/__NAME__/$name/" -e "s/__TAG__/$TAG/" -e "s/__DEMO_MODE__/$1/" jobs/setup.yaml | kubectl apply -f - >/dev/null
  if ! kubectl -n "$NS" wait "job/$name" --for=condition=complete --timeout=30m; then
    kubectl -n "$NS" logs "job/$name" --tail=80 || true
    echo "Job setup lỗi: DỪNG, phiên bản đang chạy giữ nguyên"; exit 1
  fi
  kubectl -n "$NS" logs "job/$name" | grep -E "mật khẩu tạm|khoá tài khoản demo|ERROR" || true
}
if $SEED; then
  log "Job setup: migration + dữ liệu mẫu (DEMO_MODE=true)"
  run_setup true
fi
log "Job setup: migration + khoá tài khoản demo + tài khoản quản trị (DEMO_MODE=false)"
run_setup false

log "ứng dụng: api, api-chat, worker, web, caddy (image $TAG)"
kubectl apply -f "$RENDERED" >/dev/null
rm -f "$RENDERED"
if $RESTART; then
  kubectl -n "$NS" rollout restart deploy/api deploy/api-chat deploy/worker deploy/web deploy/caddy
fi
for d in api api-chat worker web caddy; do
  kubectl -n "$NS" rollout status "deploy/$d" --timeout=10m
done

IP=$(kubectl -n "$NS" get svc caddy -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
log "xong: https://$(grep ^APP_DOMAIN= config.env | cut -d= -f2)  (IP $IP)"
