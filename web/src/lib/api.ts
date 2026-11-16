// Client mỏng của EduAssist API. Mọi luật nghiệp vụ nằm ở backend; lỗi nghiệp vụ trả về `detail` tiếng Việt
// và được hiển thị nguyên văn cho người dùng.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "eduassist.token";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* trình duyệt chặn storage: phiên chỉ sống trong tab */
  }
}

function detailOf(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d) && d[0]?.msg) return `Dữ liệu chưa hợp lệ: ${d[0].msg}`;
  }
  if (status === 0) return "Không kết nối được máy chủ. Kiểm tra API đang chạy rồi thử lại.";
  return `Không thực hiện được (mã ${status}). Thử lại sau ít phút.`;
}

export const MUST_CHANGE_PATH = "/doi-mat-khau";

// API quá tải trả 503 + Retry-After (giây). Request ĐỌC tự thử lại tối đa 3 lần, chờ theo Retry-After, tăng dần
// và lệch ngẫu nhiên: hàng nghìn trình duyệt không cùng thử lại một lúc (dồn tải đúng lúc hệ thống đang hồi phục).
// Request GHI không tự thử lại: người dùng bấm lại khi thấy thông báo, tránh ghi hai lần.
const MAX_RETRIES = 3;

function retryDelayMs(res: Response, attempt: number): number {
  const after = Number(res.headers.get("Retry-After"));
  const base = Number.isFinite(after) && after > 0 ? Math.min(after, 10) * 1000 : 1000;
  return base * 2 ** attempt * (0.75 + Math.random() * 0.5);
}

async function request(path: string, init?: { method?: string; body?: unknown }): Promise<{ res: Response; body: unknown }> {
  const token = getToken();
  const method = init?.method ?? (init?.body !== undefined ? "POST" : "GET");
  let res: Response;
  for (let attempt = 0; ; attempt++) {
    try {
      res = await fetch(`${API_URL}${path}`, {
        method,
        headers: {
          ...(init?.body !== undefined ? { "Content-Type": "application/json" } : {}),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
      });
    } catch {
      throw new ApiError(detailOf(null, 0), 0);
    }
    if (res.status !== 503 || method !== "GET" || attempt >= MAX_RETRIES) break;
    await new Promise((ok) => setTimeout(ok, retryDelayMs(res, attempt)));
  }
  if (res.status === 401 && path !== "/auth/login") {
    setToken(null);
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login?expired=1";
    }
  }
  // Tài khoản mới / vừa được cấp lại mật khẩu: API chặn mọi thứ cho tới khi đổi mật khẩu
  if (res.status === 403 && res.headers.get("X-Must-Change-Password") === "1" && typeof window !== "undefined") {
    if (window.location.pathname !== MUST_CHANGE_PATH) window.location.href = MUST_CHANGE_PATH;
  }
  const body = res.headers.get("content-type")?.includes("json") ? await res.json() : null;
  if (!res.ok) throw new ApiError(detailOf(body, res.status), res.status);
  return { res, body };
}

export async function api<T = unknown>(path: string, init?: { method?: string; body?: unknown }): Promise<T> {
  return (await request(path, init)).body as T;
}

export type Paged<T> = { items: T[]; total: number };

/** Danh sách có phân trang: body là mảng, tổng số dòng nằm ở header X-Total-Count. */
export async function apiPage<T>(path: string): Promise<Paged<T>> {
  const { res, body } = await request(path);
  const items = (body as T[]) ?? [];
  const total = Number(res.headers.get("X-Total-Count") ?? items.length);
  return { items, total: Number.isFinite(total) ? total : items.length };
}

export const fetcher = <T,>(path: string) => api<T>(path);

/** POST SSE (fetch + ReadableStream, vì EventSource không gửi được header Authorization). */
export async function streamSSE(
  path: string,
  body: unknown,
  onEvent: (type: string, data: Record<string, unknown>) => void,
  signal?: AbortSignal,
) {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    const b = res.headers.get("content-type")?.includes("json") ? await res.json() : null;
    throw new ApiError(detailOf(b, res.status), res.status);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let type = "message";
      let data = "";
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event: ")) type = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (data) onEvent(type, JSON.parse(data));
    }
  }
}
