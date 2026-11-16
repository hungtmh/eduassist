"use client";

import { BookOpen, KeyRound, LogOut, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Copilot } from "@/components/copilot";
import { homeFor, useAuth } from "@/components/providers";
import { Avatar, IconButton, Spinner, SunMark, cx } from "@/components/ui";

/** Khung cổng học viên: gọn, ưu tiên điện thoại, không có menu nghiệp vụ của nhân viên. */
export function PortalShell({ children }: { children: ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const [chat, setChat] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
    else if (user.must_change_password) router.replace("/doi-mat-khau");
    else if (user.role !== "student") router.replace(homeFor(user));
  }, [user, loading, router]);

  if (loading || !user || user.role !== "student" || user.must_change_password) return <Spinner />;

  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="sr-only z-50 rounded-lg bg-surface px-3 py-2 shadow-pop focus:not-sr-only focus:fixed focus:start-4 focus:top-4">
        Bỏ qua tới nội dung
      </a>
      <header className="sticky top-0 z-30 border-b border-line bg-canvas/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-3 px-4 sm:px-6">
          <Link href="/portal" className="flex items-center gap-2.5">
            <SunMark className="size-8" />
            <span className="leading-tight">
              <span className="font-display block font-semibold">Ánh Dương</span>
              <span className="block text-[0.6875rem] text-fg-tertiary">Cổng học viên</span>
            </span>
          </Link>
          <nav aria-label="Cổng học viên" className="ms-auto flex items-center gap-1">
            <Link href="/khoa-hoc" className="hidden items-center gap-1.5 rounded-lg px-3 py-2 font-medium text-fg-secondary hover:bg-surface-hover hover:text-fg sm:inline-flex">
              <BookOpen className="size-4" aria-hidden />
              Khoá học khác
            </Link>
            <button
              onClick={() => setChat((v) => !v)}
              aria-expanded={chat}
              aria-controls="copilot"
              className={cx(
                "pressable inline-flex h-9 items-center gap-2 rounded-lg px-3 font-medium",
                chat ? "bg-agent-subtle text-agent-fg" : "bg-surface shadow-card hover:bg-surface-hover",
              )}
            >
              <Sparkles className="size-4 text-agent-fg" aria-hidden />
              <span className="hidden sm:inline">Hỏi trợ lý</span>
              <span className="sr-only sm:hidden">Hỏi trợ lý</span>
            </button>
            <Link href="/doi-mat-khau" aria-label="Đổi mật khẩu" title="Đổi mật khẩu" className="inline-flex size-9 items-center justify-center rounded-lg text-fg-secondary hover:bg-surface-hover hover:text-fg">
              <KeyRound className="size-4" aria-hidden />
            </Link>
            <span className="ms-1 hidden sm:block">
              <Avatar name={user.display_name} size="sm" />
            </span>
            <IconButton label="Đăng xuất" onClick={logout}>
              <LogOut className="size-4" aria-hidden />
            </IconButton>
          </nav>
        </div>
      </header>
      <div className="flex min-h-0 flex-1">
        <main id="main" className="min-w-0 flex-1 px-4 py-6 sm:px-6">
          <div className="mx-auto max-w-5xl">{children}</div>
        </main>
        {chat && <Copilot onClose={() => setChat(false)} />}
      </div>
    </div>
  );
}
