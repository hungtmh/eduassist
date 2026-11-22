# Biến dùng chung cho các script (source, không chạy trực tiếp).
LOCATION=${LOCATION:-malaysiawest}
RG=${RG:-eduassist-prod}
DATA_RG=${DATA_RG:-eduassist-data}
CLUSTER=${CLUSTER:-eduassist}
VM=${VM:-Standard_B2als_v2}
NS=eduassist

# Git Bash trên Windows: Azure CLI cài bằng winget có thể chưa nằm trong PATH của phiên này
if ! command -v az >/dev/null 2>&1; then
  for d in "/c/Program Files/Microsoft SDKs/Azure/CLI2/wbin" "/c/Program Files (x86)/Microsoft SDKs/Azure/CLI2/wbin"; do
    [ -d "$d" ] && PATH="$d:$PATH"
  done
fi

# Tên Storage Account phải duy nhất trên toàn Azure: ghép từ ID subscription để lần nào chạy cũng ra cùng một tên
SUB_ID=$(az account show --query id -o tsv)
STORAGE=${STORAGE:-eduassist$(printf '%s' "$SUB_ID" | tr -d '-' | cut -c1-12)}

log() { printf '\n==> %s\n' "$*"; }
