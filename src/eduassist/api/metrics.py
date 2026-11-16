"""Số liệu vận hành dạng Prometheus (GET /metrics), không cần thư viện ngoài.

Mỗi tiến trình API tự đếm; chạy nhiều tiến trình thì mỗi lần Prometheus hỏi sẽ trúng một tiến trình ngẫu nhiên, nên
mọi số đều gắn nhãn pid - cộng theo pid ở Grafana, hoặc cho Prometheus hỏi thẳng từng tiến trình / từng máy.

Cảnh báo nên đặt (docs/SCALING_PLAN.md, giai đoạn 4):
- p95 độ trễ > 300 ms trong 5 phút:  histogram_quantile(0.95, sum by (le) (rate(eduassist_request_seconds_bucket[5m])))
- tỉ lệ 503 > 1% trong 5 phút:       sum(rate(eduassist_requests_total{status="503"}[5m])) / sum(rate(...[5m]))
- request đang xếp hàng kéo dài:     eduassist_admission_waiting > 0
- có request chờ kết nối DB:          eduassist_db_pool_requests_waiting > 0
"""

import os
import time

BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
STREAM_ROUTES = frozenset({"/chat", "/chat/resume", "/public/chat"})
_PID = str(os.getpid())
_START = time.time()

# Chỉ đổi trên event loop (AccessLog là middleware async) nên không cần khoá
_requests: dict[tuple[str, str, str], int] = {}
_bucket_counts = [0] * (len(BUCKETS) + 1)
_totals = {"sum": 0.0, "count": 0}


def observe(route: str, method: str, status: int, seconds: float) -> None:
    key = (route, method, str(status))
    _requests[key] = _requests.get(key, 0) + 1
    if route in STREAM_ROUTES:
        return  # chat kéo dài nhiều giây: không trộn vào độ trễ của trang thường
    for i, b in enumerate(BUCKETS):
        if seconds <= b:
            _bucket_counts[i] += 1
            break
    else:
        _bucket_counts[-1] += 1
    _totals["sum"] += seconds
    _totals["count"] += 1


def _esc(v: str) -> str:
    return v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def render(admission: dict) -> str:
    from eduassist import cache
    from eduassist.db import all_pools

    p = f'pid="{_PID}"'
    out = [
        "# TYPE eduassist_up gauge",
        f"eduassist_up{{{p}}} 1",
        f"eduassist_start_time_seconds{{{p}}} {_START:.0f}",
        "# TYPE eduassist_requests_total counter",
    ]
    for (route, method, status), n in sorted(_requests.items()):
        out.append(f'eduassist_requests_total{{{p},route="{_esc(route)}",method="{method}",status="{status}"}} {n}')
    out.append("# TYPE eduassist_request_seconds histogram")
    cum = 0
    for b, n in zip(BUCKETS, _bucket_counts, strict=False):
        cum += n
        out.append(f'eduassist_request_seconds_bucket{{{p},le="{b}"}} {cum}')
    out.append(f'eduassist_request_seconds_bucket{{{p},le="+Inf"}} {cum + _bucket_counts[-1]}')
    out.append(f"eduassist_request_seconds_sum{{{p}}} {_totals['sum']:.6f}")
    out.append(f"eduassist_request_seconds_count{{{p}}} {_totals['count']}")

    for k, v in admission.items():
        kind = "counter" if k == "rejected" else "gauge"
        out += [f"# TYPE eduassist_admission_{k} {kind}", f"eduassist_admission_{k}{{{p}}} {v}"]

    for name, pool in all_pools().items():
        st = pool.get_stats()
        for k in ("pool_size", "pool_available", "requests_waiting", "requests_num", "requests_errors", "usage_ms"):
            if k in st:
                out.append(f'eduassist_db_pool_{k}{{{p},pool="{name}"}} {st[k]}')

    out.append(f"eduassist_redis_up{{{p}}} {1 if cache.redis_status() == 'ok' else 0}")
    # Đếm chung toàn hệ thống (Redis) - mọi tiến trình trả cùng một số
    out.append(f"eduassist_llm_turns_in_use {cache.llm_slots().in_use()}")
    return "\n".join(out) + "\n"
