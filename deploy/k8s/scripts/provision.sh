#!/usr/bin/env bash
# Tạo hạ tầng Azure MỘT LẦN (chạy lại cũng an toàn): AKS, Storage Account sao lưu, operator trong cluster.
#   bash deploy/k8s/scripts/provision.sh
# Bắt đầu TÍNH TIỀN từ đây. Tắt khi không dùng: deploy/k8s/scripts/cluster.ps1 stop
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/common.sh

CERT_MANAGER=v1.21.3
CNPG=1.30.1
BARMAN=v0.15.1

log "resource group $RG ($LOCATION)"
az group create -n "$RG" -l "$LOCATION" -o none

if ! az aks show -g "$RG" -n "$CLUSTER" -o none 2>/dev/null; then
  log "tạo AKS $CLUSTER: 1 node hệ thống $VM (khoảng 5-10 phút)"
  # --tier free: control plane miễn phí. Không bật Container Insights (tính tiền theo lượng log).
  # Cilium: thực thi NetworkPolicy. Ổ đĩa node 30 GB thay vì 128 GB mặc định.
  az aks create -g "$RG" -n "$CLUSTER" -l "$LOCATION" --tier free \
    --nodepool-name system --node-vm-size "$VM" --node-count 1 --node-osdisk-size 30 --max-pods 60 \
    --network-plugin azure --network-plugin-mode overlay --network-dataplane cilium \
    --auto-upgrade-channel patch --node-os-upgrade-channel NodeImage \
    --ssh-access disabled -o none
fi

if ! az aks nodepool show -g "$RG" --cluster-name "$CLUSTER" -n user -o none 2>/dev/null; then
  log "node pool user: autoscaler 1-2 node (quota 6 vCPU = tối đa 3 node tính cả node hệ thống)"
  az aks nodepool add -g "$RG" --cluster-name "$CLUSTER" -n user --mode User --node-vm-size "$VM" \
    --node-count 1 --node-osdisk-size 30 --max-pods 60 \
    --enable-cluster-autoscaler --min-count 1 --max-count 2 -o none
fi

az aks get-credentials -g "$RG" -n "$CLUSTER" --overwrite-existing -o none

log "Storage Account sao lưu $STORAGE (resource group riêng $DATA_RG: xoá cluster không mất bản sao lưu)"
az group create -n "$DATA_RG" -l "$LOCATION" -o none
if ! az storage account show -n "$STORAGE" -g "$DATA_RG" -o none 2>/dev/null; then
  az storage account create -n "$STORAGE" -g "$DATA_RG" -l "$LOCATION" --sku Standard_LRS --kind StorageV2 \
    --min-tls-version TLS1_2 --allow-blob-public-access false -o none
fi
KEY=$(az storage account keys list -n "$STORAGE" -g "$DATA_RG" --query "[0].value" -o tsv)
az storage container create --account-name "$STORAGE" --account-key "$KEY" -n backups -o none

log "cert-manager $CERT_MANAGER (plugin sao lưu của CloudNativePG cần nó)"
kubectl apply -f "https://github.com/cert-manager/cert-manager/releases/download/$CERT_MANAGER/cert-manager.yaml" >/dev/null
kubectl -n cert-manager rollout status deploy/cert-manager-webhook --timeout=5m

log "CloudNativePG $CNPG"
kubectl apply --server-side -f \
  "https://github.com/cloudnative-pg/cloudnative-pg/releases/download/v$CNPG/cnpg-$CNPG.yaml" >/dev/null
kubectl -n cnpg-system rollout status deploy/cnpg-controller-manager --timeout=5m

log "plugin Barman Cloud $BARMAN"
kubectl apply -f "https://github.com/cloudnative-pg/plugin-barman-cloud/releases/download/$BARMAN/manifest.yaml" >/dev/null
kubectl -n cnpg-system rollout status deploy/barman-cloud --timeout=5m

log "xong. Tiếp theo: bash deploy/k8s/scripts/deploy.sh <tag image> --seed"
