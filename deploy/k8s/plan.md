# Kế hoạch đưa EduAssist lên Kubernetes (Azure AKS) theo chuẩn production

> Lập ngày 22/11/2026. Các số liệu về tài khoản Azure, quota và giá ở mục 1 và mục 8 đã được kiểm tra trực tiếp
> ngày hôm đó (giá lấy từ Azure Retail Prices API, chưa gồm thuế). Riêng giá Load Balancer là ước tính, phải kiểm tra
> lại trong Cost Management sau buổi chạy đầu tiên.

## 0. Tóm tắt

- **Mục tiêu:** chạy EduAssist trên AKS với đầy đủ các thực hành mà hệ thống production thật cần: nhiều node, nhiều
  bản, tự phục hồi, tự mở rộng, database có bản sao và sao lưu, bí mật không nằm trong git, triển khai bằng CI.
- **Cách làm:** viết **một bộ manifest dùng chung** (`base`) và hai cấu hình khác nhau:
  - **`lab`**: dựng mỗi buổi học khoảng 1 giờ, xoá ngay sau buổi. Đây cũng là môi trường staging.
  - **`prod`**: chạy liên tục. Chỉ bật khi có người dùng thật, vì 100 đô không đủ chạy 24/7 lâu (mục 8).
- **Không sửa logic ứng dụng.** Chỉ thêm file hạ tầng. Một số việc nhỏ trong code được ghi riêng ở mục 6.
- **Ràng buộc lớn nhất:** tối đa 6 vCPU (3 node × 2 vCPU), chỉ được dùng 5 vùng, và 100 đô credit.

## 1. Hiện trạng tài khoản Azure (đã kiểm tra 22/11/2026)

| Mục | Kết quả |
|---|---|
| Subscription | Azure for Students, tenant VNU-HCMUS |
| Chi phí hiện tại | 0 đô, chưa có tài nguyên nào |
| Resource provider | `Microsoft.Compute`, `ContainerService`, `Network`, `Storage`: **Registered** |
| Vùng được phép (policy của trường) | `malaysiawest`, `eastasia`, `centralindia`, `indiasouthcentral`, `uaenorth`. **Không có** `southeastasia` |
| Quota vCPU (malaysiawest, eastasia) | **Tổng 6**; dòng BS (B2s) 4; dòng Basv2 10 |
| Loại máy ở malaysiawest | **Không có B2s.** `B2als_v2`, `B2as_v2` dùng được (chỉ bị chặn ở vùng con số 2) |
| Phiên bản AKS ở malaysiawest | 1.34 đến 1.37 |
| Công cụ trên máy | `az` (đã đăng nhập), `kubectl` v1.36.1 (đi kèm Docker Desktop) |

**Chọn vùng:** `malaysiawest`, vì gần Việt Nam và rẻ. Dự phòng: `eastasia`.
**Chọn máy:** `Standard_B2als_v2` (2 vCPU, 4 GB, 31,2 đô/tháng).

## 2. Kiến trúc đích

```
                       Internet
                          │  eduassist-lab.malaysiawest.cloudapp.azure.com
                          ▼
              Azure Load Balancer (IP tĩnh)       ← giữ IP công khai, chỉ gửi vào node có Caddy
                          │  externalTrafficPolicy: Local (giữ IP thật của người dùng)
        ┌─────────────────┼───────────────────────────────────────────────┐
        │ AKS             ▼                                               │
        │        caddy ×2 (2 node khác nhau)   HTTPS, header bảo mật, định tuyến
        │          │            │            │
        │          ▼            ▼            ▼
        │      api ×2–6     api-chat ×2     web ×2        ← Deployment, HPA cho api
        │      (HPA CPU)    (SSE, async)    (Next.js)
        │          │            │
        │          ├────────────┴──────────────┐
        │          ▼                           ▼
        │   Postgres (CloudNativePG)        redis ×1      ← bộ đếm, cache (mất không sao)
        │   primary ──WAL──► replica
        │   Service -rw (ghi) / -ro (đọc)
        │          │
        │          └── sao lưu WAL + bản đầy đủ hằng ngày ──► Azure Blob Storage
        │
        │   worker ×2 (SKIP LOCKED, an toàn khi chạy nhiều bản)
        │   setup: Job chạy migration, chạy TRƯỚC khi cập nhật ứng dụng
        └──────────────────────────────────────────────────────────────────┘
   System pool: 1 node (coredns, metrics-server... + Postgres, Redis)
   User pool:   1–2 node, Cluster Autoscaler (api, api-chat, web, worker, caddy)
```

Ánh xạ biến môi trường hiện có sang K8s:

| Biến | Giá trị trong cluster |
|---|---|
| `DATABASE_URL` | `postgresql://app_rw:…@eduassist-db-rw:5432/eduassist` |
| `DATABASE_READ_URL` | `postgresql://app_rw:…@eduassist-db-ro:5432/eduassist` |
| `AGENT_RO_URL` | `postgresql://agent_ro:…@eduassist-db-ro:5432/eduassist` (SQL của AI đọc từ bản sao) |
| `REDIS_URL` | `redis://redis:6379/0` |
| `API_INTERNAL_URL` (web) | `http://api:8000` |

Ở Giai đoạn 2–3, Postgres là StatefulSet 1 bản nên cả ba URL database đều trỏ về `postgres:5432`.

## 3. Chuẩn production và cách đáp ứng

| Nhóm | Yêu cầu | Cách làm | lab | prod |
|---|---|---|---|---|
| **Image** | Mỗi bản build có tag riêng, không dùng `latest` | GitHub Actions build, gắn tag bằng git SHA, đẩy lên GHCR | ✅ | ✅ |
| | Quét lỗ hổng | Trivy trong workflow, lỗi `CRITICAL` thì dừng | ✅ | ✅ |
| | Chạy không phải root | Đã có (`uid 1000` trong `Dockerfile`), thêm `runAsNonRoot` | ✅ | ✅ |
| **Cấu hình** | Bí mật không nằm trong git | `up.sh` sinh ngẫu nhiên rồi tạo Secret. Prod: Azure Key Vault + Secrets Store CSI | Secret | Key Vault |
| | Kiểm tra cấu hình khi khởi động | `APP_ENV=production`: API từ chối chạy nếu còn khoá yếu (đã có trong `config.py`) | ✅ | ✅ |
| **Tài nguyên** | Mọi pod khai báo `requests`/`limits` | Theo số đo thật (mục 4) | ✅ | ✅ |
| **Sức khoẻ** | Phân biệt "còn sống" và "sẵn sàng" | liveness `/health/live`, readiness `/health`, startupProbe cho api (nạp mô hình embedding) | ✅ | ✅ |
| **Sẵn sàng cao** | Mọi thành phần không giữ dữ liệu có ≥ 2 bản, nằm ở node khác nhau | `replicas ≥ 2` + `topologySpreadConstraints` | ✅ | ✅ |
| | Bảo trì không làm mất dịch vụ | `PodDisruptionBudget` `minAvailable: 1` | ✅ | ✅ |
| | Tắt máy êm, không cắt ngang request | `preStop: sleep 5`. `terminationGracePeriodSeconds: 60` cho api-chat, vì một câu chat được chạy tới 45 giây | ✅ | ✅ |
| | Chịu được mất cả một trung tâm dữ liệu | Rải node qua các vùng con 1 và 3 | — | ✅ |
| **Mở rộng** | Tự thêm pod | HPA cho api (CPU 70%, 2–6 pod) | ✅ | ✅ |
| | Tự thêm máy | Cluster Autoscaler cho user pool (1–2 node, giới hạn bởi quota) | ✅ | ✅ |
| **Database** | Có bản sao, tự chuyển khi bản chính chết | CloudNativePG 2 bản, đồng bộ (vì có dữ liệu thanh toán) | 1 bản → CNPG | CNPG |
| | Sao lưu ra ngoài cluster, khôi phục tới từng phút | CNPG + Barman: WAL liên tục + bản đầy đủ hằng ngày lên Azure Blob | — | ✅ |
| | **Đã thử khôi phục** | Diễn tập khôi phục vào cluster mới, ghi lại thời gian | ✅ (1 lần) | định kỳ |
| | Migration có kiểm soát | Job `setup` chạy **trước** khi rollout, chụp sao lưu trước đó (checklist 6.11) | ✅ | ✅ |
| **Mạng** | Chỉ Caddy mở ra ngoài | Các Service khác là `ClusterIP` | ✅ | ✅ |
| | Pod chỉ nói chuyện với đúng pod cần | NetworkPolicy mặc định chặn hết, rồi mở từng đường (api→db, worker→db...). Cần bật Cilium khi tạo cluster | ✅ | ✅ |
| | IP thật của người dùng (giới hạn đăng nhập theo IP) | `externalTrafficPolicy: Local` + `--proxy-headers` của uvicorn | ✅ | ✅ |
| | HTTPS thật | lab: `tls internal`. prod: Let's Encrypt, chứng chỉ lưu trên Azure Files để 2 Caddy dùng chung | tự ký | ✅ |
| **Quyền** | Pod không có quyền gọi API của K8s khi không cần | `automountServiceAccountToken: false` | ✅ | ✅ |
| | Không leo thang quyền | `allowPrivilegeEscalation: false`, bỏ mọi capability | ✅ | ✅ |
| **Theo dõi** | Xem log | `kubectl logs` (log JSON có sẵn) | ✅ | ✅ |
| | Số liệu + cảnh báo | Prometheus đọc `/metrics` (đã có), Grafana, cảnh báo: pod khởi động lại, 5xx tăng, DB gần đầy | tuỳ chọn | ✅ |
| | Biết khi worker treo | Worker ghi nhịp tim, cảnh báo khi quá hạn (**cần sửa code**, mục 6) | — | ✅ |
| | Giám sát từ bên ngoài | UptimeRobot (miễn phí) gọi `/health/live` | — | ✅ |
| **CI/CD** | Triển khai lặp lại được, không gõ tay | `kubectl apply -k overlays/<môi trường>` từ script / workflow | script | workflow |
| | CI không giữ mật khẩu Azure | GitHub OIDC + federated credential | — | ✅ |
| | Thử trước khi lên prod | `lab` đóng vai staging | ✅ | ✅ |
| **Chi phí** | Không cháy tiền | Bậc Free, ổ node 30 GB, không bật Container Insights, Budget alert, xoá lab sau mỗi buổi | ✅ | ✅ |

## 4. Tài nguyên cho từng thành phần

Số đo trên máy dev: api khi rảnh khoảng 300 MB, khoảng 800 MB sau khi nạp mô hình embedding; worker khoảng 50 MB;
web khoảng 35 MB; Postgres khoảng 55 MB khi rảnh. Mỗi node `B2als_v2` còn khoảng **2,5 GB** dùng được sau phần AKS giữ lại.

| Thành phần | Số bản | requests (CPU / RAM) | limits (RAM) | Ghi chú |
|---|---|---|---|---|
| api | 2 (HPA tới 6) | 250m / 768Mi | 1280Mi | `WEB_CONCURRENCY=1`: mở rộng bằng pod, không bằng tiến trình |
| api-chat | 2 | 100m / 512Mi | 1Gi | `MAX_CONCURRENT_STREAMS=500` |
| web | 2 | 50m / 192Mi | 384Mi | |
| worker | 2 | 50m / 128Mi | 512Mi | |
| caddy | 2 | 50m / 64Mi | 256Mi | |
| redis | 1 | 50m / 64Mi | 320Mi | `maxmemory 256mb` như compose |
| postgres | 1 → 2 (CNPG) | 250m / 768Mi | 1Gi | `shared_buffers=256MB`, `effective_cache_size=768MB`, `max_connections=150` |
| setup (Job) | chạy 1 lần | 250m / 768Mi | 1280Mi | Tạo embedding cho tài liệu |

Tổng `requests` lúc bình thường khoảng 5 GB trên khoảng 7,5 GB dùng được của 3 node, còn chỗ để HPA thêm pod. Khi
HPA thêm pod mà hết chỗ thì pod ở trạng thái Pending, và Cluster Autoscaler thêm node (bài lab 4).

**Số kết nối database:** mỗi pod api mở tối đa 10 (app) + 4 (auth) + 10 (async) kết nối. 6 pod api + 2 api-chat + 2
worker có thể chạm khoảng 200, vượt `max_connections=150`. Cách xử lý: Pooler của CloudNativePG (PgBouncer) ở Giai
đoạn 5, hoặc giảm `DB_POOL_SIZE` cho từng pod. Phải đo `pg_stat_activity` trong bài lab HPA.

## 5. Cấu trúc thư mục sẽ tạo

```
.github/workflows/images.yml       build + quét + đẩy eduassist-api, eduassist-web lên GHCR (tag = git SHA)
deploy/k8s/
  plan.md                          file này
  base/                            manifest dùng chung
    kustomization.yaml
    namespace.yaml
    config.yaml                    ConfigMap: APP_ENV, TZ, CORS_ORIGINS, REDIS_URL...
    redis.yaml
    postgres.yaml                  StatefulSet 1 bản (Giai đoạn 2–4)
    setup-job.yaml
    api.yaml  api-chat.yaml  worker.yaml  web.yaml
    caddy.yaml  Caddyfile           Service LoadBalancer + nhãn DNS
    hpa.yaml  pdb.yaml
    networkpolicy.yaml
  cnpg/                            CloudNativePG: Cluster 2 bản, sao lưu, Pooler (Giai đoạn 5)
  overlays/
    lab/                           DEMO_MODE=true, tls internal, mailpit, 1 bản DB
    prod/                          DEMO_MODE=false, Let's Encrypt, SMTP thật, CNPG
  scripts/
    up.sh                          tạo resource group + AKS + Secret + apply, chờ tới khi chạy
    down.sh                        xoá cả resource group
    secrets.sh                     sinh JWT_SECRET, mật khẩu DB; đọc GROQ_API_KEY từ máy
docs/K8S_LAB.md                    hướng dẫn từng bước + 8 bài lab
```

## 6. Thay đổi nhỏ trong code (làm riêng, có test)

| Việc | Vì sao | Giai đoạn |
|---|---|---|
| Worker ghi nhịp tim vào DB + endpoint/metric báo tuổi nhịp tim | Không có HTTP để probe; worker treo thì không ai biết (checklist 6.7) | 6 |
| Đọc `--forwarded-allow-ips` từ biến môi trường thay vì `*` | Chỉ tin header IP do Caddy gửi, không tin mọi nguồn | 4 |
| (Tuỳ chọn) Web dùng URL API tương đối `/api` | Image web không phụ thuộc tên miền, khỏi build lại khi đổi tên (checklist 6.13). `NEXT_PUBLIC_SITE_URL` vẫn cần cho SEO | 7 |

Ngoài ra còn lỗi đã biết: COMMIT của dependency `db` chạy **sau khi** gửi response. Sửa bằng `Depends(db, scope="function")`
trước khi có người dùng thật.

## 7. Lộ trình

Mỗi giai đoạn chỉ coi là xong khi đạt mục "Xong khi".

### Giai đoạn 0: Chuẩn bị tài khoản (gần xong)
- [x] Cài `az`, đăng nhập, đăng ký resource provider, kiểm tra quota, vùng và loại máy.
- [ ] **Bạn làm:** Budget alert 10 / 30 / 50 / 80 đô (Cost Management → Budgets).
- Xong khi: có email cảnh báo ngân sách.

### Giai đoạn 1: Build image tự động (miễn phí)
- [ ] `images.yml`: chạy khi bấm tay hoặc khi push tag `v*`. Build 2 image, tag = SHA, quét Trivy, đẩy GHCR.
- [ ] Image web build với `NEXT_PUBLIC_API_URL=https://eduassist-lab.malaysiawest.cloudapp.azure.com/api`.
- [ ] **Bạn làm:** chạy workflow, đặt 2 package thành Public.
- Xong khi: `docker pull ghcr.io/hungtmh/eduassist-api:<sha>` chạy được từ máy không đăng nhập.

### Giai đoạn 2: Chạy thử trên Kubernetes của Docker Desktop (miễn phí)
- [ ] Viết `base/` và `overlays/lab/`.
- [ ] **Bạn làm:** bật Kubernetes trong Docker Desktop, `kubectl apply -k deploy/k8s/overlays/lab`.
- Xong khi:
  - Mọi pod `Running`, Job setup `Completed`.
  - Dùng `kubectl port-forward` vào Caddy: đăng nhập được, Copilot trả lời được.
  - Worker xử lý outbox (có bản ghi `processed_at`).

### Giai đoạn 3: Cluster AKS lab (~0,2 đô/giờ)
- [ ] `up.sh`:
  ```
  az group create -n eduassist-lab -l malaysiawest
  az aks create  --tier free --node-vm-size Standard_B2als_v2 --node-count 1 \
                 --node-osdisk-size 30 --network-plugin azure --network-plugin-mode overlay \
                 --network-dataplane cilium \
                 --generate-ssh-keys   (không bật monitoring)
  az aks nodepool add  --name user --mode User --enable-cluster-autoscaler --min-count 1 --max-count 2
  az aks get-credentials
  secrets.sh; kubectl apply -k overlays/lab; chờ rollout
  ```
- [ ] `down.sh`: `az group delete -n eduassist-lab --yes --no-wait`, rồi kiểm tra không còn resource group `MC_*`.
- Xong khi:
  - Mở được `https://eduassist-lab.malaysiawest.cloudapp.azure.com` (chứng chỉ tự ký).
  - `up.sh` mất dưới 20 phút.
  - Sau `down.sh`, Cost analysis không còn phát sinh.

### Giai đoạn 4: Sẵn sàng cao và mở rộng: các bài lab
| # | Bài lab | Thao tác | Kết quả mong đợi |
|---|---|---|---|
| 1 | Chia tải | `kubectl scale deploy api --replicas=4`, xem log từng pod | Request rải đều các pod |
| 2 | Tự phục hồi | `kubectl delete pod` một pod api | Pod mới thay trong vài giây, không lỗi |
| 3 | HPA | k6 `loadtest/api.js` | Số pod api tăng theo CPU, giảm lại sau tải |
| 4 | Cluster Autoscaler | Tăng tải tới khi pod Pending | Azure thêm node thứ 3, pod được đặt lên |
| 5 | Bảo trì node | `kubectl drain` node có api + caddy trong lúc chạy k6 | 0 lỗi nhờ PDB. **Postgres 1 bản bị gián đoạn**: ghi lại số giây |
| 6 | Rolling update | Đổi tag image | Thay dần, 0 lỗi |
| 7 | IP thật | Đổi `externalTrafficPolicy` Local ↔ Cluster | Thấy IP thật / IP node trong log, hiểu vì sao cần Local |
| 8 | Chặn mạng | Áp NetworkPolicy, thử gọi db từ pod web | Bị chặn |
- Xong khi: có bảng kết quả (số lỗi, thời gian phục hồi) dùng được cho báo cáo đồ án.

### Giai đoạn 5: Database đúng chuẩn
- [ ] Cài operator CloudNativePG, `Cluster` 2 bản đồng bộ, image Postgres có pgvector (kiểm tra lại image phù hợp lúc làm).
- [ ] Sao lưu lên Azure Blob (Storage Account Standard LRS) bằng workload identity, không dùng khoá tĩnh.
- [ ] Pooler (PgBouncer) nếu số kết nối vượt ngưỡng ở mục 4; đặt `DB_VIA_PGBOUNCER=true`.
- [ ] Diễn tập: xoá pod primary trong lúc chạy k6 → đo thời gian chuyển; khôi phục vào cluster mới → đo thời gian, kiểm tra dữ liệu.
- Xong khi: lặp lại bài lab 5 mà database không gián đoạn quá vài giây; khôi phục thành công ít nhất 1 lần.

### Giai đoạn 6: Bảo mật và theo dõi
- [ ] securityContext cho mọi pod, NetworkPolicy đầy đủ.
- [ ] Nhịp tim worker (mục 6) + cảnh báo.
- [ ] Prometheus + Grafana (nếu đủ RAM), hoặc tối thiểu: UptimeRobot + Sentry.
- Xong khi: tắt worker thì nhận được cảnh báo trong vòng 5 phút.

### Giai đoạn 7: Go-live (chỉ khi có người dùng thật)
- [ ] `overlays/prod`: `DEMO_MODE=false`, tài khoản quản trị qua `ADMIN_*`, SMTP thật (SPF/DKIM), Let's Encrypt.
- [ ] Tên miền riêng (tuỳ chọn), cluster chạy liên tục, node rải qua vùng con 1 và 3.
- [ ] Workflow deploy bằng OIDC; migration là bước riêng có sao lưu trước.
- [ ] Rà lại `docs/PRODUCTION_CHECKLIST.md` (mục 6 và 8: pháp lý, dữ liệu cá nhân).
- Xong khi: chạy liên tục 7 ngày không can thiệp tay, đã diễn tập khôi phục, có người trực cảnh báo.

## 8. Chi phí (malaysiawest)

| Khoản | lab ($/giờ) | prod chạy liên tục ($/tháng) |
|---|---|---|
| 3 node `B2als_v2` | 0,13 | 94 |
| Load Balancer (ước tính) | 0,025 | ~18 |
| IP công khai tĩnh | 0,005 | 3,7 |
| Ổ đĩa node 3 × 30 GB + ổ DB | ~0,02 | ~15 |
| Azure Blob (sao lưu) | — | ~1 |
| Control plane bậc Free, GHCR, Groq gói miễn phí | 0 | 0 |
| **Tổng** | **~0,2** | **~130** |

- **lab:** mỗi buổi khoảng 1 giờ 20 phút (kể cả dựng và xoá), tức **~0,25 đô**. 100 đô đủ cho rất nhiều buổi.
- **prod 24/7:** khoảng 130 đô/tháng, **vượt 100 đô credit**. Muốn chạy thật lâu dài thì phải có kinh phí riêng, hoặc
  quay về 1 máy ảo + Docker Compose (~40 đô/tháng, mất tính sẵn sàng cao).
- Lúc nghỉ, cluster lab **không tồn tại**, nên không tốn gì.

## 9. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| Quên chạy `down.sh` (3 node ≈ 4,5 đô/ngày) | Budget alert; `up.sh` in giờ tạo và nhắc; tuỳ chọn workflow tự xoá lúc 23h |
| Hết quota hoặc hết loại máy trong vùng | Dự phòng `eastasia`; kiểm tra `az vm list-skus` trước khi đổi loại máy |
| Hết RAM trên node 4 GB | Đặt `requests` theo số đo, theo dõi `kubectl top`; nếu cần đổi sang `B2as_v2` (8 GB, gấp đôi tiền) |
| Let's Encrypt giới hạn 5 chứng chỉ trùng tên mỗi tuần | Lab dùng `tls internal`; chỉ prod dùng chứng chỉ thật |
| Nhãn DNS bị người khác lấy giữa hai buổi | Đổi nhãn và build lại image web (hoặc làm mục 6, URL tương đối) |
| `DEMO_MODE=true` công khai: ai cũng đăng nhập bằng `demo123` và dùng hạn mức Groq | Chỉ bật lúc học hoặc demo; `PUBLIC_CHAT_GLOBAL_PER_MINUTE` giữ thấp |
| Dữ liệu nằm ở Malaysia | Nghị định 13/2023/NĐ-CP: dữ liệu thật của học viên cần đánh giá chuyển dữ liệu ra nước ngoài trước khi go-live |
| B-series là CPU "burstable", bị giảm tốc khi hết điểm CPU | Chỉ dùng để học và demo. Kết quả đo tải ghi rõ cấu hình, không so với máy thường |

## 10. Ngoài phạm vi

- Multi-tenant (xem `docs/MULTI_TENANT.md`).
- Nhiều vùng địa lý, CDN.
- Service mesh, GitOps (Argo CD / Flux). Có thể thêm sau Giai đoạn 7.
- Azure Database for PostgreSQL managed: đơn giản hơn CNPG nhưng tốn thêm tiền và ít bài học hơn. Ghi lại làm phương án thay thế.

## 11. Cần bạn quyết định

1. Vùng `malaysiawest` và nhãn DNS `eduassist-lab`: đồng ý hay đổi?
2. Có làm Giai đoạn 2 (Docker Desktop, miễn phí) trước khi lên Azure không? Đề xuất: **có**.
3. Giai đoạn 7 có cần không, hay dừng ở Giai đoạn 6 cho đồ án?
