import Link from "next/link";
import type { ReactNode } from "react";
import { SunMark } from "@/components/ui";

/** Khung chung cho các trang tài khoản ngoài bàn làm việc: quên / đặt / đổi mật khẩu. */
export function AuthCard({ title, description, children }: { title: string; description?: ReactNode; children: ReactNode }) {
  return (
    <main className="flex min-h-dvh items-center justify-center bg-canvas px-4 py-10">
      <div className="w-full max-w-md">
        <Link href="/login" className="mb-6 flex items-center gap-3">
          <SunMark className="size-10" />
          <span className="font-display text-xl font-semibold">Ánh Dương</span>
        </Link>
        <div className="rounded-2xl bg-surface p-6 shadow-card sm:p-8">
          <h1 tabIndex={-1} data-page-title className="font-display text-2xl font-medium text-balance outline-none">
            {title}
          </h1>
          {description && <div className="mt-1.5 text-fg-secondary text-pretty">{description}</div>}
          <div className="mt-6">{children}</div>
        </div>
      </div>
    </main>
  );
}

export const PASSWORD_HINT = "Ít nhất 8 ký tự, có cả chữ và số, không chứa tên đăng nhập.";

/** Kiểm tra nhanh phía trình duyệt (máy chủ vẫn kiểm tra đầy đủ). Trả lỗi hoặc null. */
export function checkNewPassword(pw: string, confirm: string): string | null {
  if (pw.length < 8) return "Mật khẩu cần ít nhất 8 ký tự.";
  if (!/\p{L}/u.test(pw) || !/\d/.test(pw)) return "Mật khẩu cần có cả chữ và số.";
  if (pw !== confirm) return "Hai lần nhập mật khẩu chưa khớp.";
  return null;
}
