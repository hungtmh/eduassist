"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthCard, PASSWORD_HINT, checkNewPassword } from "@/components/auth-card";
import { homeFor, useAuth } from "@/components/providers";
import { Button, Field, Input, Spinner } from "@/components/ui";
import { api, setToken } from "@/lib/api";

export default function ChangePasswordPage() {
  const { user, loading, logout } = useAuth();
  const [oldPw, setOldPw] = useState("");
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && !user) window.location.href = "/login";
  }, [loading, user]);
  if (loading || !user) return <Spinner />;
  const forced = user.must_change_password;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const problem = checkNewPassword(pw, confirm);
    if (problem) return setError(problem);
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ access_token: string }>("/auth/change-password", { body: { mat_khau_cu: oldPw, mat_khau_moi: pw } });
      // Mọi phiên khác đã bị đăng xuất; phiên này dùng token mới. Tải lại để lấy hồ sơ mới.
      setToken(r.access_token);
      window.location.href = homeFor({ ...user!, must_change_password: false });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không đổi được mật khẩu.");
      setBusy(false);
    }
  }

  async function logoutAll() {
    if (!window.confirm("Đăng xuất khỏi mọi thiết bị, kể cả thiết bị này?")) return;
    try {
      await api("/auth/logout-all", { method: "POST" });
    } finally {
      logout();
    }
  }

  return (
    <AuthCard
      title={forced ? "Đặt mật khẩu của riêng bạn" : "Đổi mật khẩu"}
      description={
        forced
          ? `Chào ${user.display_name}. Bạn đang dùng mật khẩu tạm do trung tâm cấp, hãy đổi trước khi tiếp tục.`
          : "Sau khi đổi, các thiết bị khác đang đăng nhập tài khoản này sẽ bị đăng xuất."
      }
    >
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <input type="text" name="username" autoComplete="username" value={user.username} readOnly hidden />
        <Field label={forced ? "Mật khẩu tạm" : "Mật khẩu hiện tại"}>
          {(p) => (
            <Input {...p} type="password" autoComplete="current-password" required value={oldPw} onChange={(e) => setOldPw(e.target.value)} />
          )}
        </Field>
        <Field label="Mật khẩu mới" hint={PASSWORD_HINT}>
          {(p) => <Input {...p} type="password" autoComplete="new-password" required value={pw} onChange={(e) => setPw(e.target.value)} />}
        </Field>
        <Field label="Nhập lại mật khẩu mới">
          {(p) => (
            <Input {...p} type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          )}
        </Field>
        {error && (
          <p role="alert" className="rounded-lg bg-danger-subtle px-3 py-2 text-danger-fg">
            {error}
          </p>
        )}
        <Button type="submit" variant="primary" loading={busy} disabled={!oldPw} className="h-10 w-full">
          Đổi mật khẩu
        </Button>
      </form>
      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4 text-[0.8125rem]">
        {forced ? (
          <button type="button" onClick={logout} className="font-medium text-fg-secondary hover:text-fg">
            Đăng xuất
          </button>
        ) : (
          <Link href={homeFor(user)} className="font-medium text-accent-fg hover:underline">
            Quay lại
          </Link>
        )}
        <button type="button" onClick={logoutAll} className="font-medium text-danger-fg hover:underline">
          Đăng xuất mọi thiết bị
        </button>
      </div>
    </AuthCard>
  );
}
