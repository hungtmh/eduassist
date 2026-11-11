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

export async function api<T = unknown>(path: string, init?: { method?: string; body?: unknown }): Promise<T> {
  const token = getToken();
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: init?.method ?? (init?.body !== undefined ? "POST" : "GET"),
      headers: {
        ...(init?.body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
  } catch {
    throw new ApiError(detailOf(null, 0), 0);
  }
  if (res.status === 401 && path !== "/auth/login") {
    setToken(null);
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login?expired=1";
    }
  }
  const body = res.headers.get("content-type")?.includes("json") ? await res.json() : null;
  if (!res.ok) throw new ApiError(detailOf(body, res.status), res.status);
  return body as T;
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
