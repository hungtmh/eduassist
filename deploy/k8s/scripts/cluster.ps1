# Bật / tắt / xem trạng thái cluster EduAssist trên Azure.
#   powershell -ExecutionPolicy Bypass -File deploy\k8s\scripts\cluster.ps1 start
#   powershell -ExecutionPolicy Bypass -File deploy\k8s\scripts\cluster.ps1 stop
#   powershell -ExecutionPolicy Bypass -File deploy\k8s\scripts\cluster.ps1 status
#
# stop: tắt các máy ảo (hết tiền máy). Dữ liệu Postgres, chứng chỉ HTTPS, IP và tên miền GIỮ NGUYÊN.
#       Vẫn tính phần nhỏ: Load Balancer, IP, ổ đĩa (khoảng 1 đô/ngày).
# start: bật lại khoảng 5-10 phút; Postgres và ứng dụng tự chạy lại, không cần deploy.
param([ValidateSet('start', 'stop', 'status')][string]$Action = 'status')

$RG = 'eduassist-prod'
$Cluster = 'eduassist'
$Url = 'https://eduassist-hcmus.malaysiawest.cloudapp.azure.com'
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')

switch ($Action) {
    'start' {
        Write-Host "Đang bật cluster (5-10 phút)..."
        az aks start -g $RG -n $Cluster
        az aks get-credentials -g $RG -n $Cluster --overwrite-existing -o none
        Write-Host "Chờ ứng dụng sẵn sàng..."
        kubectl -n eduassist wait cluster.postgresql.cnpg.io/eduassist-db --for=condition=Ready --timeout=15m
        foreach ($d in 'api', 'api-chat', 'worker', 'web', 'caddy') {
            kubectl -n eduassist rollout status "deploy/$d" --timeout=10m
        }
        Write-Host "Đã bật: $Url  (nhớ tắt khi xong: cluster.ps1 stop)"
    }
    'stop' {
        Write-Host "Đang tắt cluster..."
        az aks stop -g $RG -n $Cluster
        Write-Host "Đã tắt. Dữ liệu giữ nguyên; bật lại bằng: cluster.ps1 start"
    }
    'status' {
        az aks show -g $RG -n $Cluster --query "{trang_thai:powerState.code, phien_ban:kubernetesVersion}" -o table
    }
}
