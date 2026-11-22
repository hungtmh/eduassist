# Vận hành EduAssist trên Azure Kubernetes (AKS)

Địa chỉ: **https://eduassist-hcmus.malaysiawest.cloudapp.azure.com**
Kế hoạch và lý do thiết kế: [plan.md](plan.md).

## Bật / tắt (việc hằng ngày)

Cluster **chỉ bật khi cần**. Bật cả ngày tốn khoảng 3,5 đô; khi tắt chỉ còn khoảng 1 đô/ngày (Load Balancer, IP, ổ đĩa).

```powershell
powershell -ExecutionPolicy Bypass -File deploy\k8s\scripts\cluster.ps1 start    # 5-10 phút
powershell -ExecutionPolicy Bypass -File deploy\k8s\scripts\cluster.ps1 stop
powershell -ExecutionPolicy Bypass -File deploy\k8s\scripts\cluster.ps1 status
```

Tắt **không mất gì**: dữ liệu Postgres, chứng chỉ HTTPS, IP và tên miền giữ nguyên. Bật lại thì mọi thứ tự chạy, không
phải deploy lại.

## Có gì đang chạy

| Thành phần | Số bản | Ghi chú |
|---|---|---|
| caddy | 2 | Cổng vào duy nhất, HTTPS Let's Encrypt, hai node khác nhau |
| api | 2–6 | HPA thêm pod khi CPU > 70% |
| api-chat | 2 | Chat SSE |
| web | 2 | Next.js |
| worker | 2 | Agent nền + outbox; liveness bằng nhịp tim |
| eduassist-db | 2 | CloudNativePG: bản chính + bản sao đồng bộ, tự chuyển khi bản chính chết |
| redis | 1 | Bộ đếm, cache (mất không sao) |

Node: 1 node hệ thống + 1–2 node ứng dụng (`Standard_B2als_v2`, 2 vCPU, 4 GB), vùng Malaysia West.
Sao lưu: WAL liên tục + bản đầy đủ mỗi 6 giờ lên Azure Blob (resource group riêng `eduassist-data`), giữ 14 ngày.

## Xem tình hình

```bash
kubectl -n eduassist get pods -o wide          # pod nào ở node nào, có pod nào khởi động lại không
kubectl -n eduassist get hpa                   # HPA đang giữ bao nhiêu pod api
kubectl -n eduassist top pods                  # CPU / RAM thật
kubectl -n eduassist logs deploy/api --tail=50
kubectl -n eduassist logs deploy/worker --tail=50
kubectl -n eduassist get cluster.postgresql.cnpg.io eduassist-db   # bản chính là pod nào, có khoẻ không
kubectl -n eduassist get backups.postgresql.cnpg.io                # các bản sao lưu
```

## Cập nhật phiên bản mới

1. Push code lên `main` → workflow **Images** build, quét lỗ hổng và đẩy image có tag = 7 ký tự đầu của commit.
2. `bash deploy/k8s/scripts/deploy.sh <tag>`. Script tự sao lưu database, chạy migration (Job `setup`), rồi thay dần
   từng pod (không gián đoạn). Migration lỗi thì dừng, phiên bản cũ vẫn chạy.
3. Quay lại bản cũ: `bash deploy/k8s/scripts/deploy.sh <tag cũ>` (nếu migration mới không đổi cấu trúc bảng).

Đổi `config.env`, `Caddyfile` hoặc `secrets.env`: `bash deploy/k8s/scripts/deploy.sh <tag đang chạy> --restart`.

## Bí mật

| File | Ai điền | Nội dung |
|---|---|---|
| `secrets.env` | Bạn | Groq key, Gmail (App Password), email quản trị |
| `.state/generated.env` | Script tự sinh lần đầu | JWT_SECRET, mật khẩu database, METRICS_TOKEN |

Cả hai **không nằm trong git**. Mất `.state/generated.env` thì vẫn đọc lại được từ Secret trong cluster
(`kubectl -n eduassist get secret eduassist-secrets -o yaml`), nhưng nên giữ một bản an toàn.

## Khi có sự cố

| Hiện tượng | Xem gì |
|---|---|
| Trang không mở được | `cluster.ps1 status` (đang tắt?), `kubectl -n eduassist get pods`, `kubectl -n eduassist logs deploy/caddy` |
| Lỗi chứng chỉ HTTPS | `kubectl -n eduassist logs deploy/caddy | grep -i acme` |
| 503 hàng loạt | `kubectl -n eduassist get cluster.postgresql.cnpg.io` (database đang chuyển bản chính?), `kubectl top nodes` |
| Worker không chạy agent | `kubectl -n eduassist logs deploy/worker`; pod khởi động lại nhiều lần = nhịp tim quá hạn (vòng lặp treo) |
| Hết tiền / gần hết credit | Email từ Budget `eduassist-100usd` ở mốc 10/30/50/80 đô. Tắt ngay: `cluster.ps1 stop` |

## Khôi phục database từ bản sao lưu

CloudNativePG tạo cluster MỚI từ bản sao lưu (khôi phục được tới một thời điểm bất kỳ trong 14 ngày):

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata: {name: eduassist-db-restore, namespace: eduassist}
spec:
  instances: 1
  imageName: ghcr.io/cloudnative-pg/postgresql:16.16-standard-trixie
  storage: {size: 16Gi, storageClass: managed-csi}
  bootstrap:
    recovery:
      source: origin
      # recoveryTarget: {targetTime: "2026-11-22 15:30:00+07"}   # bỏ dòng này = khôi phục tới mới nhất
  externalClusters:
    - name: origin
      plugin:
        name: barman-cloud.cloudnative-pg.io
        parameters: {barmanObjectName: eduassist-backup, serverName: eduassist-db}
```

Kiểm tra dữ liệu trên `eduassist-db-restore`, rồi trỏ `DATABASE_URL` sang `eduassist-db-restore-rw` (hoặc đổi tên).

## Xoá hẳn (không dùng nữa)

```bash
az group delete -n eduassist-prod --yes      # cluster, máy ảo, Load Balancer, IP, ổ đĩa
az group delete -n eduassist-data --yes      # bản sao lưu (chỉ xoá khi chắc chắn không cần dữ liệu)
```
