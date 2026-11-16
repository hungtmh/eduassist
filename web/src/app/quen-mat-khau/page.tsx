"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthCard } from "@/components/auth-card";
import { Button, Field, Input } from "@/components/ui";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [ident, setIdent] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ message: string }>("/auth/forgot-password", { body: { ten_dang_nhap_hoac_email: ident.trim() } });
      setSent(r.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không gửi được yêu cầu.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title="Quên mật khẩu"
      description="Nhập tên đăng nhập hoặc email. Trung tâm gửi link đặt lại mật khẩu tới email gắn với tài khoản."
    >
      {sent ? (
        <div className="flex flex-col gap-4">
          <p role="status" className="rounded-lg bg-success-subtle px-3 py-2 text-success-fg">
            {sent}
          </p>
          <p className="text-fg-secondary">
            Tài khoản không có email? Liên hệ quản lý trung tâm để được cấp lại mật khẩu tạm.
          </p>
          <Link href="/login" className="font-medium text-accent-fg hover:underline">
            Quay lại đăng nhập
          </Link>
        </div>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <Field label="Tên đăng nhập hoặc email">
            {(p) => (
              <Input
                {...p}
                autoComplete="username"
                autoCapitalize="none"
                required
                value={ident}
                onChange={(e) => setIdent(e.target.value)}
              />
            )}
          </Field>
          {error && (
            <p role="alert" className="rounded-lg bg-danger-subtle px-3 py-2 text-danger-fg">
              {error}
            </p>
          )}
          <Button type="submit" variant="primary" loading={busy} disabled={ident.trim().length < 3} className="h-10 w-full">
            Gửi link đặt lại
          </Button>
          <Link href="/login" className="self-center text-[0.8125rem] font-medium text-accent-fg hover:underline">
            Quay lại đăng nhập
          </Link>
        </form>
      )}
    </AuthCard>
  );
}
