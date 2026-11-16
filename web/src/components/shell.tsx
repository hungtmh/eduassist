"use client";

import {
  Bell,
  Bot,
  BookOpen,
  CalendarDays,
  ClipboardCheck,
  Inbox,
  KeyRound,
  Library,
  ListChecks,
  LogOut,
  Menu,
  Newspaper,
  Receipt,
  Sparkles,
  ScrollText,
  Sun,
  UserCog,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import useSWR from "swr";
import { Copilot } from "@/components/copilot";
import { homeFor, useAuth } from "@/components/providers";
import { Avatar, IconButton, Spinner, SunMark, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

type NavItem = { href: string; label: string; icon: typeof Inbox; perm: string | string[]; badge?: "inbox" };
const NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "Vận hành",
    items: [
      { href: "/dashboard", label: "Bản tin hôm nay", icon: Newspaper, perm: "report.read" },
      { href: "/hom-nay", label: "Việc hôm nay", icon: Sun, perm: ["task.read", "class.read_own"] },
      { href: "/inbox", label: "Hộp duyệt", icon: Inbox, perm: "chat.data", badge: "inbox" },
      { href: "/tasks", label: "Sổ việc", icon: ListChecks, perm: "task.read" },
    ],
  },
  {
    group: "Nghiệp vụ",
    items: [
      { href: "/leads", label: "Tuyển sinh", icon: UserPlus, perm: "lead.read" },
      { href: "/classes", label: "Lớp học", icon: BookOpen, perm: ["class.read", "class.read_own"] },
      { href: "/lich", label: "Thời khoá biểu", icon: CalendarDays, perm: ["class.read", "class.read_own"] },
      { href: "/students", label: "Học viên", icon: Users, perm: "student.read" },
      { href: "/finance", label: "Tài chính", icon: Receipt, perm: "invoice.read" },
      { href: "/requests", label: "Yêu cầu học viên", icon: ClipboardCheck, perm: "request.handle" },
    ],
  },
  {
    group: "Agent & quản trị",
    items: [
      { href: "/agents", label: "Agent & mức tự chủ", icon: Bot, perm: "chat.data" },
      { href: "/catalog", label: "Danh mục đào tạo", icon: Library, perm: ["course.write", "class.write"] },
      { href: "/users", label: "Người dùng", icon: UserCog, perm: "user.admin" },
      { href: "/audit", label: "Nhật ký kiểm toán", icon: ScrollText, perm: "audit.read" },
    ],
  },
];

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  const { can } = useAuth();
  const path = usePathname();
  const { data: counts } = useSWR<{ cho_duyet: number }>(can("chat.data") ? "/proposals/counts" : null, {
    refreshInterval: 30_000,
  });
  return (
    <nav aria-label="Điều hướng chính" className="flex flex-col gap-5">
      {NAV.map((g) => {
        const items = g.items.filter((i) => (Array.isArray(i.perm) ? i.perm.some(can) : can(i.perm)));
        if (!items.length) return null;
        return (
          <div key={g.group}>
            <p className="mb-1.5 px-3 text-[0.6875rem] font-medium tracking-[0.05em] text-side-fg-secondary uppercase">{g.group}</p>
            <ul className="flex flex-col gap-0.5">
              {items.map((i) => {
                const active = path === i.href || path.startsWith(`${i.href}/`);
                return (
                  <li key={i.href}>
                    <Link
                      href={i.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cx(
                        "relative flex h-9 items-center gap-2.5 rounded-lg px-3 font-medium transition-[background-color,color] duration-150",
                        active
                          ? "bg-side-active text-side-fg before:absolute before:inset-y-2 before:start-0 before:w-[3px] before:rounded-full before:bg-brand"
                          : "text-side-fg-secondary hover:bg-side-active/60 hover:text-side-fg",
                      )}
                    >
                      <i.icon className="size-4 shrink-0" strokeWidth={2} aria-hidden />
                      <span className="min-w-0 flex-1 truncate">{i.label}</span>
                      {i.badge === "inbox" && !!counts?.cho_duyet && (
                        <span className="num rounded-full bg-brand px-1.5 py-0.5 text-[0.6875rem] leading-none font-semibold text-fg">
                          {counts.cho_duyet}
                          <span className="sr-only"> đề xuất chờ duyệt</span>
                        </span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

function splitToday() {
  const d = new Date();
  const weekday = new Intl.DateTimeFormat("vi-VN", { weekday: "long" }).format(d);
  const date = new Intl.DateTimeFormat("vi-VN", { day: "numeric", month: "long", year: "numeric" }).format(d);
  return { weekday: weekday.charAt(0).toUpperCase() + weekday.slice(1), date };
}

type Notice = { id: number; tieu_de: string; noi_dung: string; lien_ket: string | null; da_doc: boolean; created_at: string };

function Notifications() {
  const [open, setOpen] = useState(false);
  const { data, mutate } = useSWR<Notice[]>("/notifications", { refreshInterval: 60_000 });
  const unread = data?.filter((n) => !n.da_doc) ?? [];
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);
  return (
    <div className="relative" ref={ref}>
      <IconButton
        label={unread.length ? `Thông báo, ${unread.length} chưa đọc` : "Thông báo"}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <Bell className="size-4" aria-hidden />
        {!!unread.length && <span className="absolute top-2 end-2 size-2 rounded-full bg-danger-solid" aria-hidden />}
      </IconButton>
      {open && (
        <div className="fade-in absolute end-0 top-11 z-40 w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-xl bg-surface shadow-pop">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <h2 className="font-semibold">Thông báo</h2>
            {!!unread.length && (
              <button
                className="text-[0.8125rem] font-medium text-accent-fg hover:underline"
                onClick={async () => {
                  await api("/notifications/read", { body: { ids: unread.map((n) => n.id) } });
                  mutate();
                }}
              >
                Đánh dấu đã đọc
              </button>
            )}
          </div>
          <ul className="max-h-96 overflow-y-auto overscroll-contain">
            {!data && <Spinner />}
            {data?.length === 0 && <li className="px-4 py-8 text-center text-fg-secondary">Chưa có thông báo nào.</li>}
            {data?.map((n) => (
              <li key={n.id} className="border-b border-line last:border-0">
                <Link
                  href={n.lien_ket ?? "#"}
                  onClick={() => setOpen(false)}
                  className="block px-4 py-3 hover:bg-surface-hover"
                >
                  <p className={cx("text-pretty", !n.da_doc && "font-semibold")}>{n.tieu_de}</p>
                  <p className="mt-0.5 line-clamp-3 text-fg-secondary whitespace-pre-line">{n.noi_dung}</p>
                  <p className="mt-1 text-xs text-fg-tertiary">{fmtDateTime(n.created_at)}</p>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const path = usePathname();
  const [drawer, setDrawer] = useState(false);
  const [copilot, setCopilot] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
    else if (user?.must_change_password) router.replace("/doi-mat-khau");
    else if (user?.role === "student") router.replace("/portal"); // học viên có khung riêng
  }, [user, loading, router]);

  // Đổi trang phía client: đưa focus về tiêu đề trang mới cho người dùng bàn phím / trình đọc màn hình
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    const t = setTimeout(() => (document.querySelector("[data-page-title]") as HTMLElement | null)?.focus(), 50);
    return () => clearTimeout(t);
  }, [path]);

  useEffect(() => {
    try {
      setCopilot(localStorage.getItem("eduassist.copilot") === "1");
    } catch {}
  }, []);
  const toggleCopilot = () =>
    setCopilot((v) => {
      try {
        localStorage.setItem("eduassist.copilot", v ? "0" : "1");
      } catch {}
      return !v;
    });

  if (loading || !user || user.must_change_password || user.role === "student") return <Spinner />;
  const todayLabel = splitToday();

  const sidebar = (
    <div className="flex h-full flex-col gap-6 px-3 py-4">
      <Link href={homeFor(user)} className="flex items-center gap-3 px-3">
        <SunMark className="size-9 shrink-0" />
        <span className="min-w-0">
          <span className="font-display block truncate text-lg leading-tight font-semibold text-side-fg">Ánh Dương</span>
          <span className="block truncate text-xs text-side-fg-secondary">EduAssist Platform</span>
        </span>
      </Link>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <Nav onNavigate={() => setDrawer(false)} />
      </div>
      <div className="flex items-center gap-2.5 rounded-xl bg-side-active/70 p-2">
        <Avatar name={user.display_name} className="bg-brand text-fg" />
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-side-fg">{user.display_name}</p>
          <p className="truncate text-xs text-side-fg-secondary">{user.role_label}</p>
        </div>
        <Link
          href="/doi-mat-khau"
          aria-label="Đổi mật khẩu"
          title="Đổi mật khẩu"
          className="inline-flex size-9 items-center justify-center rounded-lg text-side-fg-secondary hover:bg-side-active hover:text-side-fg"
        >
          <KeyRound className="size-4" aria-hidden />
        </Link>
        <IconButton label="Đăng xuất" onClick={logout} className="text-side-fg-secondary hover:bg-side-active hover:text-side-fg">
          <LogOut className="size-4" aria-hidden />
        </IconButton>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-dvh">
      <a
        href="#main"
        className="sr-only z-50 rounded-lg bg-surface px-3 py-2 shadow-pop focus:not-sr-only focus:fixed focus:start-4 focus:top-4"
      >
        Bỏ qua tới nội dung
      </a>
      <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 bg-side lg:block">{sidebar}</aside>

      {drawer && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-fg/40" onClick={() => setDrawer(false)} aria-hidden />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Điều hướng"
            className="fade-in absolute inset-y-0 start-0 w-72 bg-side shadow-pop"
          >
            <IconButton label="Đóng điều hướng" className="absolute end-2 top-4 text-side-fg-secondary hover:bg-side-active hover:text-side-fg" onClick={() => setDrawer(false)}>
              <X className="size-4" aria-hidden />
            </IconButton>
            {sidebar}
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-canvas/90 px-4 backdrop-blur sm:px-6">
          <IconButton label="Mở điều hướng" className="lg:hidden" onClick={() => setDrawer(true)}>
            <Menu className="size-4" aria-hidden />
          </IconButton>
          <p className="num min-w-0 flex-1 truncate text-fg-secondary">
            <span className="font-medium text-fg">{todayLabel.weekday}</span>, {todayLabel.date}
          </p>
          <Notifications />
          <button
            onClick={toggleCopilot}
            aria-expanded={copilot}
            aria-controls="copilot"
            className={cx(
              "pressable inline-flex h-9 items-center gap-2 rounded-lg px-3 font-medium",
              copilot ? "bg-agent-subtle text-agent-fg" : "bg-surface shadow-card hover:bg-surface-hover",
            )}
          >
            <Sparkles className="size-4 text-agent-fg" aria-hidden />
            Copilot
          </button>
        </header>
        <div className="flex min-h-0 flex-1">
          <main id="main" className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8">
            <div className="mx-auto max-w-6xl">{children}</div>
          </main>
          {copilot && <Copilot onClose={toggleCopilot} />}
        </div>
      </div>
    </div>
  );
}
