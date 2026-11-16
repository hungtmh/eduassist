"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import useSWR from "swr";
import { homeFor, useAuth } from "@/components/providers";
import { Button, Field, Input, SunMark, cx } from "@/components/ui";

const DEMO = [
  ["quanly", "Quản lý", "Bản tin, duyệt agent, mức tự chủ"],
  ["ketoan", "Kế toán", "Thang nhắc nợ, ghi nhận tiền"],
  ["tuvan", "Tư vấn viên", "Bảng tuyển sinh, sổ việc"],
  ["giaovu", "Giáo vụ", "Thời khoá biểu, mở lớp"],
  ["giangvien", "Giảng viên", "Lịch dạy, điểm danh"],
  ["hocvien", "Học viên", "Thẻ học viên, học phí"],
] as const;

function Hero() {
  return (
    <section className="relative hidden overflow-hidden bg-side p-10 text-side-fg lg:flex lg:flex-col" aria-label="Giới thiệu">
      {/* mặt trời mọc: các vòng đồng tâm, trang trí */}
      <svg viewBox="0 0 600 600" className="pointer-events-none absolute -end-56 -bottom-80 w-[46rem] opacity-90" aria-hidden>
        {[280, 230, 180, 130].map((r, i) => (
          <circle key={r} cx="300" cy="300" r={r} fill="none" stroke="var(--color-brand)" strokeOpacity={0.12 + i * 0.1} strokeWidth="1.5" />
        ))}
        <circle cx="300" cy="300" r="90" fill="var(--color-brand)" />
      </svg>
      <div className="relative flex items-center gap-3">
        <SunMark className="size-10" />
        <span>
          <span className="font-display block text-xl font-semibold">Ánh Dương</span>
          <span className="block text-xs text-side-fg-secondary">Trung tâm Đào tạo</span>
        </span>
      </div>
      <div className="relative mt-auto mb-40 max-w-md">
        <p className="font-display text-[2.5rem] leading-[1.1] font-medium text-balance">
          Mỗi sáng, các agent đã làm xong phần việc lặp lại. Bạn chỉ còn việc quyết định.
        </p>
        <ul className="mt-6 flex flex-col gap-2 text-side-fg-secondary">
          <li>Nhắc học phí theo từng bậc, không gửi trùng</li>
          <li>Gợi ý gộp lớp khi thiếu sĩ số</li>
          <li>Mọi thao tác có nhật ký, ai duyệt cũng ghi lại</li>
        </ul>
      </div>
    </section>
  );
}

function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const expired = useSearchParams().get("expired");
  // Nút tài khoản demo chỉ hiện khi máy chủ bật DEMO_MODE (mặc định ẩn trong lúc chờ để không lộ ở production)
  const { data: config } = useSWR<{ demo_mode: boolean }>("/public/config", { revalidateOnFocus: false });
  const demo = config?.demo_mode === true;
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(expired ? "Phiên đăng nhập đã hết hạn. Đăng nhập lại để tiếp tục." : null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const p = await login(username.trim(), password);
      router.replace(homeFor(p));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không đăng nhập được.");
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-dvh lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <Hero />
      <div className="flex items-center justify-center px-4 py-10 sm:px-10">
        <div className="w-full max-w-md">
          <div className="mb-6 flex items-center gap-3 lg:hidden">
            <SunMark className="size-10" />
            <span className="font-display text-xl font-semibold">Ánh Dương</span>
          </div>
          <p className="text-xs font-medium tracking-[0.05em] text-fg-tertiary uppercase">EduAssist Platform</p>
          <h1 className="font-display mt-1 text-3xl font-medium text-balance">Chào buổi làm việc mới</h1>
          <p className="mt-1 text-fg-secondary">Đăng nhập để vào bàn làm việc của bạn.</p>

          <form onSubmit={submit} className="mt-6 flex flex-col gap-4" noValidate>
            <Field label="Tên đăng nhập">
              {(p) => (
                <Input
                  {...p}
                  name="username"
                  autoComplete="username"
                  autoCapitalize="none"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="quanly"
                />
              )}
            </Field>
            <Field label="Mật khẩu">
              {(p) => (
                <Input
                  {...p}
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              )}
            </Field>
            {error && (
              <p role="alert" className="rounded-lg bg-danger-subtle px-3 py-2 text-danger-fg">
                {error}
              </p>
            )}
            <Button type="submit" variant="primary" loading={busy} className="mt-1 h-10 w-full">
              Đăng nhập
            </Button>
            <Link href="/quen-mat-khau" className="self-center text-[0.8125rem] font-medium text-accent-fg hover:underline">
              Quên mật khẩu?
            </Link>
          </form>

          {demo && (
          <fieldset className="mt-8">
            <legend className="text-xs font-medium text-fg-secondary">Thử nhanh với tài khoản demo (mật khẩu demo123)</legend>
            <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
              {DEMO.map(([u, r, hint]) => (
                <button
                  key={u}
                  type="button"
                  aria-pressed={username === u}
                  onClick={() => {
                    setUsername(u);
                    setPassword("demo123");
                  }}
                  className={cx(
                    "pressable rounded-xl px-3 py-2 text-start shadow-card",
                    username === u ? "bg-accent-subtle ring-2 ring-accent-solid" : "bg-surface hover:bg-surface-hover",
                  )}
                >
                  <span className="block text-[0.8125rem] font-semibold">{r}</span>
                  <span className="block text-[0.6875rem] leading-snug text-fg-tertiary">{hint}</span>
                </button>
              ))}
            </div>
          </fieldset>
          )}
          {demo && <p className="mt-6 text-xs text-fg-tertiary">Toàn bộ học viên, đơn hàng và chính sách là dữ liệu giả lập.</p>}
        </div>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
