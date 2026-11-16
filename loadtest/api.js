// Test tải API EduAssist bằng k6 (https://k6.io).
//
//   k6 run loadtest/api.js                         # tăng dần 50 -> 1000 request/giây
//   k6 run -e PROFILE=steady -e RATE=300 loadtest/api.js   # giữ đều 300 request/giây trong 2 phút
//   k6 run -e PROFILE=smoke loadtest/api.js        # chạy thử nhanh
//   k6 run -e BASE=https://staging.example.vn/api loadtest/api.js
//
// Hỗn hợp request mô phỏng thao tác thật: giao diện nhân viên tự hỏi thông báo / số đề xuất định kỳ,
// mở danh sách, mở chi tiết, học viên mở cổng, khách xem trang công khai. Chat LLM KHÔNG nằm ở đây
// (tốn token thật, bị Groq giới hạn) - xem loadtest/README.md.
import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Rate } from "k6/metrics";

const BASE = __ENV.BASE || "http://localhost:8000";
const PROFILE = __ENV.PROFILE || "ramp";
const RATE = Number(__ENV.RATE || 300);
const PEAK = Number(__ENV.PEAK || 1000);

const profiles = {
  smoke: { executor: "constant-arrival-rate", rate: 20, timeUnit: "1s", duration: "15s", preAllocatedVUs: 20, maxVUs: 50 },
  steady: { executor: "constant-arrival-rate", rate: RATE, timeUnit: "1s", duration: __ENV.DURATION || "2m", preAllocatedVUs: 200, maxVUs: 3000 },
  ramp: {
    executor: "ramping-arrival-rate",
    startRate: 50,
    timeUnit: "1s",
    preAllocatedVUs: 300,
    maxVUs: 3000,
    stages: [
      { target: 100, duration: "30s" },
      { target: 200, duration: "30s" },
      { target: 400, duration: "30s" },
      { target: 600, duration: "30s" },
      { target: 800, duration: "30s" },
      { target: PEAK, duration: "30s" },
      { target: PEAK, duration: "30s" },
    ],
  },
};

export const options = {
  scenarios: { api: profiles[PROFILE] },
  // Mục tiêu (SLO): 95% request dưới 300 ms, 99% dưới 1 s, lỗi dưới 1%
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<300", "p(99)<1000"],
  },
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "p(99)", "max"],
  discardResponseBodies: true,
};

const byGroup = {};
for (const g of ["poll", "list", "detail", "dashboard", "portal", "public"]) byGroup[g] = new Trend(`t_${g}`, true);
const rejected = new Rate("rejected_503_429");

// Mỗi thao tác: [trọng số, nhóm, vai trò, đường dẫn]
const MIX = [
  [18, "poll", "tuvan", "/notifications"],
  [12, "poll", "tuvan", "/proposals/counts"],
  [6, "poll", "ketoan", "/me/today"],
  [8, "list", "tuvan", "/leads?trang_thai=moi&limit=50"], // cột đầu của bảng tuyển sinh
  [4, "list", "tuvan", "/leads/counts"],
  [7, "list", "giaovu", "/students?limit=50"],
  [5, "list", "giaovu", "/classes?limit=50"],
  [5, "list", "ketoan", "/invoices?trang_thai=con_no&limit=100"], // màn hình kế toán mặc định
  [3, "list", "ketoan", "/invoices/summary"],
  [4, "list", "giangvien", "/schedule?tu=2026-11-09&den=2026-11-15"],
  [3, "list", "quanly", "/proposals?limit=50"],
  [5, "detail", "giaovu", "/students/{student}"],
  [4, "detail", "giaovu", "/classes/{class}"],
  [3, "detail", "tuvan", "/leads/{lead}"],
  [2, "dashboard", "quanly", "/dashboard"],
  [7, "portal", "hocvien", "/portal"],
  [2, "public", null, "/public/courses"],
  [2, "public", null, "/public/schedule"],
];
const TOTAL = MIX.reduce((s, m) => s + m[0], 0);

export function setup() {
  const tokens = {};
  for (const u of ["quanly", "tuvan", "ketoan", "giaovu", "giangvien", "hocvien"]) {
    let r;
    for (let attempt = 0; attempt < 10; attempt++) {
      r = http.post(`${BASE}/auth/login`, JSON.stringify({ username: u, password: "demo123" }), {
        headers: { "Content-Type": "application/json" },
        responseType: "text",
      });
      if (r.status !== 429) break;
      sleep(7); // API giới hạn đăng nhập 10 lần/phút mỗi IP
    }
    if (r.status !== 200) throw new Error(`Đăng nhập ${u} thất bại: ${r.status} ${r.body}`);
    tokens[u] = r.json("access_token");
  }
  const auth = { headers: { Authorization: `Bearer ${tokens.quanly}` }, responseType: "text" };
  const ids = (path) => http.get(`${BASE}${path}`, auth).json().map((x) => x.id);
  return { tokens, students: ids("/students?limit=200"), classes: ids("/classes?limit=100"), leads: ids("/leads?limit=100") };
}

const pick = (a) => a[Math.floor(Math.random() * a.length)];

export default function (data) {
  let x = Math.random() * TOTAL;
  const [, group, role, tpl] = MIX.find((m) => (x -= m[0]) < 0) || MIX[0];
  const path = tpl
    .replace("{student}", pick(data.students))
    .replace("{class}", pick(data.classes))
    .replace("{lead}", pick(data.leads));
  const params = { tags: { name: tpl, group }, timeout: "10s" };
  if (role) params.headers = { Authorization: `Bearer ${data.tokens[role]}` };
  const r = http.get(`${BASE}${path}`, params);
  byGroup[group].add(r.timings.duration);
  rejected.add(r.status === 503 || r.status === 429);
  check(r, { "status 200": (res) => res.status === 200 });
}
