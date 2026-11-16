"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { homeFor, useAuth } from "@/components/providers";
import { SunMark, cx } from "@/components/ui";

const LINKS = [
  { href: "/khoa-hoc", label: "Khoá học" },
  { href: "/lich-khai-giang", label: "Lịch khai giảng" },
  { href: "/gioi-thieu", label: "Về trung tâm" },
  { href: "/chinh-sach", label: "Chính sách" },
];

export function SiteHeader() {
  const path = usePathname();
  const { user, loading } = useAuth();
  const [open, setOpen] = useState(false);
  useEffect(() => {
    setOpen(false);
  }, [path]);

  const account = loading ? null : user ? (
    <Link href={homeFor(user)} className="font-medium text-fg-secondary hover:text-fg">
      {user.role === "student" ? "Cổng học viên" : "Vào bàn làm việc"}
    </Link>
  ) : (
    <Link href="/login" className="font-medium text-fg-secondary hover:text-fg">
      Đăng nhập
    </Link>
  );

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-canvas/90 backdrop-blur">
      <a href="#noi-dung" className="sr-only z-50 rounded-lg bg-surface px-3 py-2 shadow-pop focus:not-sr-only focus:fixed focus:start-4 focus:top-4">
        Bỏ qua tới nội dung
      </a>
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2.5">
          <SunMark className="size-9" />
          <span className="leading-tight">
            <span className="font-display block text-lg font-semibold">Ánh Dương</span>
            <span className="block text-[0.6875rem] text-fg-tertiary">Trung tâm Đào tạo</span>
          </span>
        </Link>
        <nav aria-label="Điều hướng chính" className="hidden flex-1 md:block">
          <ul className="flex items-center gap-1">
            {LINKS.map((l) => {
              const active = path === l.href || path.startsWith(`${l.href}/`);
              return (
                <li key={l.href}>
                  <Link
                    href={l.href}
                    aria-current={active ? "page" : undefined}
                    className={cx(
                      "rounded-lg px-3 py-2 font-medium transition-colors",
                      active ? "bg-surface-hover text-fg" : "text-fg-secondary hover:bg-surface-hover hover:text-fg",
                    )}
                  >
                    {l.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="ms-auto hidden items-center gap-5 md:flex">
          {account}
          <Link
            href="/dang-ky-tu-van"
            className="pressable inline-flex h-10 items-center rounded-lg bg-accent-solid px-4 font-medium text-white shadow-card hover:bg-accent-solid-hover"
          >
            Đăng ký tư vấn
          </Link>
        </div>
        <button
          className="ms-auto inline-flex size-10 items-center justify-center rounded-lg hover:bg-surface-hover md:hidden"
          aria-expanded={open}
          aria-controls="menu-di-dong"
          aria-label={open ? "Đóng menu" : "Mở menu"}
          onClick={() => setOpen((o) => !o)}
        >
          {open ? <X className="size-5" aria-hidden /> : <Menu className="size-5" aria-hidden />}
        </button>
      </div>
      {open && (
        <nav id="menu-di-dong" aria-label="Điều hướng" className="fade-in border-t border-line bg-surface px-4 pb-4 md:hidden">
          <ul className="flex flex-col py-2">
            {LINKS.map((l) => (
              <li key={l.href}>
                <Link href={l.href} className="block rounded-lg px-3 py-3 font-medium hover:bg-surface-hover">
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
          <div className="flex items-center justify-between gap-4 border-t border-line pt-4">
            {account}
            <Link href="/dang-ky-tu-van" className="inline-flex h-10 items-center rounded-lg bg-accent-solid px-4 font-medium text-white">
              Đăng ký tư vấn
            </Link>
          </div>
        </nav>
      )}
    </header>
  );
}
