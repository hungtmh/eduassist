"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import useSWR from "swr";
import { AuthCard, PASSWORD_HINT, checkNewPassword } from "@/components/auth-card";
import { Button, ErrorBox, Field, Input, Spinner } from "@/components/ui";
import { api } from "@/lib/api";

type LinkInfo = { username: string; display_name: string; muc_dich: "dat_lai" | "kich_hoat" };

function SetPassword() {
  const token = useSearchParams().get("token") ?? "";
  const { data, error } = useSWR<LinkInfo>(token ? `/auth/reset-token?token=${encodeURIComponent(token)}` : null, {
    revalidateOnFocus: false,
  });
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const problem = checkNewPassword(pw, confirm);
    if (problem) return setFormError(problem);
    setBusy(true);
    setFormError(null);
    try {
      await api("/auth/reset-password", { body: { token, mat_khau_moi: pw } });
      setDone(true);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Không đặt được mật khẩu.");
    } finally {
      setBusy(false);
    }
  }

  if (!token || error)
    return (
      <AuthCard title="Link không dùng được">
        <ErrorBox error={error ?? new Error("Thiếu mã trong link. Mở lại link từ email.")} />
        <Link href="/quen-mat-khau" className="mt-4 inline-block font-medium text-accent-fg hover:underline">
          Yêu cầu link mới
        </Link>
      </AuthCard>
    );
  if (!data) return <Spinner />;

  const activation = data.muc_dich === "kich_hoat";
  if (done)
    return (
      <AuthCard title={activation ? "Tài khoản đã sẵn sàng" : "Đã đặt mật khẩu mới"}>
        <p role="status" className="text-fg-secondary">
          Đăng nhập bằng tên <span className="font-mono font-medium text-fg">{data.username}</span> và mật khẩu vừa đặt.
        </p>
        <Link href="/login" className="mt-4 inline-flex h-10 w-full items-center justify-center rounded-lg bg-accent-solid font-medium text-white">
          Đăng nhập
        </Link>
      </AuthCard>
    );

  return (
    <AuthCard
      title={activation ? "Kích hoạt tài khoản" : "Đặt mật khẩu mới"}
      description={
        <>
          Chào {data.display_name}. Tên đăng nhập của bạn là <span className="font-mono font-medium text-fg">{data.username}</span>.
        </>
      }
    >
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        {/* trường ẩn giúp trình quản lý mật khẩu lưu đúng tài khoản */}
        <input type="text" name="username" autoComplete="username" value={data.username} readOnly hidden />
        <Field label="Mật khẩu mới" hint={PASSWORD_HINT}>
          {(p) => <Input {...p} type="password" autoComplete="new-password" required value={pw} onChange={(e) => setPw(e.target.value)} />}
        </Field>
        <Field label="Nhập lại mật khẩu mới">
          {(p) => (
            <Input {...p} type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          )}
        </Field>
        {formError && (
          <p role="alert" className="rounded-lg bg-danger-subtle px-3 py-2 text-danger-fg">
            {formError}
          </p>
        )}
        <Button type="submit" variant="primary" loading={busy} className="h-10 w-full">
          {activation ? "Kích hoạt" : "Đặt mật khẩu"}
        </Button>
      </form>
    </AuthCard>
  );
}

export default function SetPasswordPage() {
  return (
    <Suspense>
      <SetPassword />
    </Suspense>
  );
}
