"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { homeFor, useAuth } from "@/components/providers";
import { Button, Field, Input } from "@/components/ui";

const DEMO = [
  ["quanly", "Quản lý"],
  ["ketoan", "Kế toán"],
  ["tuvan", "Tư vấn viên"],
  ["giaovu", "Giáo vụ"],
  ["giangvien", "Giảng viên"],
  ["hocvien", "Học viên"],
] as const;

function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const expired = useSearchParams().get("expired");
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
    <main className="grid min-h-dvh place-items-center px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-8">
          <p className="text-xs font-medium tracking-[0.05em] text-accent-fg uppercase">EduAssist Platform</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-[-0.02em] text-balance">Trung tâm Đào tạo Ánh Dương</h1>
          <p className="mt-1 text-fg-secondary">Đăng nhập để quản lý lớp học, học viên và duyệt việc của agent.</p>
        </div>
        <form onSubmit={submit} className="flex flex-col gap-4 rounded-2xl bg-surface p-6 shadow-card" noValidate>
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
          <Button type="submit" variant="primary" loading={busy} className="mt-1 w-full">
            Đăng nhập
          </Button>
        </form>
        <div className="mt-6">
          <p className="text-xs text-fg-secondary">Tài khoản demo (mật khẩu demo123) — chọn để điền sẵn:</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {DEMO.map(([u, r]) => (
              <button
                key={u}
                type="button"
                onClick={() => {
                  setUsername(u);
                  setPassword("demo123");
                }}
                className="pressable rounded-md bg-surface px-2.5 py-1.5 text-[0.8125rem] shadow-card hover:bg-surface-hover"
              >
                {r}
              </button>
            ))}
          </div>
          <p className="mt-4 text-xs text-fg-tertiary">Toàn bộ học viên, đơn hàng và chính sách là dữ liệu giả lập.</p>
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
