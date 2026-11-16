import type { NextConfig } from "next";

const isProd = process.env.NODE_ENV === "production";
const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const apiOrigin = (() => {
  try {
    return new URL(apiUrl).origin;
  } catch {
    return "";
  }
})();

// CSP chỉ bật ở bản build production (next dev cần eval và websocket cho hot reload).
// Next.js chèn script inline để khởi động trang -> cần 'unsafe-inline' cho script khi không dùng nonce.
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self' ${apiOrigin}`.trim(),
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const nextConfig: NextConfig = {
  // Bản build gọn cho Docker: chỉ chép server.js + phụ thuộc thật sự dùng, không cần cả node_modules
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    const common = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
    ];
    return [{ source: "/:path*", headers: isProd ? [...common, { key: "Content-Security-Policy", value: csp }] : common }];
  },
};

export default nextConfig;
