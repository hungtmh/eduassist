"use client";

import { Loader2, X } from "lucide-react";
import {
  createContext,
  forwardRef,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import type { Tone } from "@/lib/labels";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

// ---------------------------------------------------------------- nút
type Variant = "primary" | "secondary" | "ghost" | "danger";
const VARIANT: Record<Variant, string> = {
  primary: "bg-accent-solid text-white hover:bg-accent-solid-hover shadow-card",
  secondary: "bg-surface text-fg shadow-card border border-transparent hover:bg-surface-hover",
  ghost: "text-fg-secondary hover:bg-surface-hover hover:text-fg",
  danger: "bg-danger-solid text-white hover:bg-danger-solid-hover shadow-card",
};

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md"; loading?: boolean }
>(function Button({ variant = "secondary", size = "md", loading, className, children, disabled, ...rest }, ref) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(
        "pressable inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg font-medium whitespace-nowrap",
        "disabled:cursor-not-allowed disabled:opacity-50 [-webkit-tap-highlight-color:transparent]",
        size === "sm" ? "h-8 px-2.5 text-[0.8125rem]" : "h-9 px-3.5 text-sm",
        VARIANT[variant],
        className,
      )}
      {...rest}
    >
      {loading && <Loader2 className="size-4 animate-spin motion-reduce:animate-none" aria-hidden />}
      {children}
    </button>
  );
});

export function IconButton({
  label,
  children,
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      aria-label={label}
      title={label}
      className={cx(
        "pressable inline-flex size-9 items-center justify-center rounded-lg text-fg-secondary hover:bg-surface-hover hover:text-fg",
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------- nhãn
const TONE: Record<Tone, string> = {
  neutral: "bg-surface-hover text-fg-secondary",
  accent: "bg-accent-subtle text-accent-fg",
  success: "bg-success-subtle text-success-fg",
  warning: "bg-warning-subtle text-warning-fg",
  danger: "bg-danger-subtle text-danger-fg",
  agent: "bg-agent-subtle text-agent-fg",
};

/** Nhãn luôn có chữ -> màu không bao giờ là cách duy nhất truyền nghĩa. */
export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium whitespace-nowrap",
        TONE[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function StatusBadge({ map, value }: { map: Record<string, [string, Tone]>; value: string }) {
  const [text, tone] = map[value] ?? [value, "neutral"];
  return <Badge tone={tone}>{text}</Badge>;
}

// ---------------------------------------------------------------- bề mặt
export function Card({ children, className, as: As = "section" }: { children: ReactNode; className?: string; as?: "section" | "div" | "article" }) {
  return <As className={cx("rounded-xl bg-surface shadow-card", className)}>{children}</As>;
}

export function CardHeader({ title, action, description }: { title: ReactNode; action?: ReactNode; description?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 px-4 pt-4 pb-3">
      <div className="min-w-0">
        <h2 className="text-base font-semibold text-balance">{title}</h2>
        {description && <p className="mt-0.5 text-fg-secondary text-pretty">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
  back,
  eyebrow,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  back?: ReactNode;
  eyebrow?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {back}
        {eyebrow && <p className="mb-1 text-xs font-medium tracking-[0.05em] text-fg-tertiary uppercase">{eyebrow}</p>}
        <h1
          tabIndex={-1}
          className="font-display text-[1.75rem] leading-tight font-medium text-balance outline-none sm:text-[2rem]"
          data-page-title
        >
          {title}
        </h1>
        {description && <p className="mt-1.5 max-w-[70ch] text-fg-secondary text-pretty">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </header>
  );
}

/** Logo: mặt trời mọc trên trang sách. Trang trí -> aria-hidden. */
export function SunMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden>
      <rect width="40" height="40" rx="10" fill="var(--color-brand)" />
      <circle cx="20" cy="23" r="7" fill="var(--color-side)" />
      {[-60, -30, 0, 30, 60].map((a) => (
        <line
          key={a}
          x1={20 + 10 * Math.sin((a * Math.PI) / 180)}
          y1={23 - 10 * Math.cos((a * Math.PI) / 180)}
          x2={20 + 14 * Math.sin((a * Math.PI) / 180)}
          y2={23 - 14 * Math.cos((a * Math.PI) / 180)}
          stroke="var(--color-side)"
          strokeWidth="2.25"
          strokeLinecap="round"
        />
      ))}
      <rect x="6" y="27" width="28" height="7" fill="var(--color-brand)" />
      <path d="M7 28.5h11.5q1.5 0 2.5 1.2q1-1.2 2.5-1.2H33" fill="none" stroke="var(--color-side)" strokeWidth="2.25" strokeLinecap="round" />
    </svg>
  );
}

export function initials(name: string) {
  const parts = name.replace(/^agent:/, "").replace(/\(.*?\)/g, "").trim().split(/\s+/);
  const a = parts.length > 1 ? parts[parts.length - 2][0] + parts[parts.length - 1][0] : parts[0]?.slice(0, 2) ?? "?";
  return a.toUpperCase();
}

/** Chữ viết tắt tên. Agent luôn tím (nghĩa "do AI làm"), người luôn mực chàm. */
export function Avatar({ name, agent, size = "md", className }: { name: string; agent?: boolean; size?: "sm" | "md" | "lg"; className?: string }) {
  return (
    <span
      aria-hidden
      className={cx(
        "inline-grid shrink-0 place-items-center rounded-full font-semibold",
        size === "sm" ? "size-7 text-[0.6875rem]" : size === "lg" ? "size-14 text-lg" : "size-9 text-xs",
        agent ? "bg-agent-subtle text-agent-fg" : "bg-accent-subtle text-accent-fg",
        className,
      )}
    >
      {initials(name)}
    </span>
  );
}

/** Thanh lấp đầy (sĩ số, tiến độ). Luôn kèm số bằng chữ ở cạnh -> không chỉ dựa vào hình. */
export function Meter({ value, max, mark, tone = "accent", className }: { value: number; max: number; mark?: number; tone?: "accent" | "warning" | "success" | "danger"; className?: string }) {
  const w = max ? Math.min(100, (value / max) * 100) : 0;
  const bar = { accent: "bg-accent-solid", warning: "bg-warning-fg", success: "bg-success-fg", danger: "bg-danger-fg" }[tone];
  return (
    <span className={cx("relative block h-1.5 overflow-hidden rounded-full bg-surface-hover", className)} aria-hidden>
      <span className={cx("absolute inset-y-0 start-0 rounded-full", bar)} style={{ width: `${w}%` }} />
      {mark != null && max > 0 && <span className="absolute inset-y-0 w-0.5 bg-fg" style={{ insetInlineStart: `${Math.min(100, (mark / max) * 100)}%` }} />}
    </span>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: ReactNode; tone?: Tone }) {
  return (
    <Card as="div" className="p-4">
      <p className="text-fg-secondary">{label}</p>
      <p className={cx("num mt-1 text-2xl font-semibold tracking-[-0.01em]", tone === "danger" && "text-danger-fg")}>
        {value}
      </p>
      {hint && <p className="mt-1 text-xs text-fg-tertiary">{hint}</p>}
    </Card>
  );
}

// ---------------------------------------------------------------- form
const CONTROL =
  "w-full rounded-lg border border-control-border bg-surface px-3 text-base sm:text-sm text-fg placeholder:text-fg-tertiary " +
  "disabled:bg-surface-muted disabled:text-fg-tertiary aria-[invalid=true]:border-danger-solid";

export function Field({
  label,
  hint,
  error,
  children,
  className,
}: {
  label: string;
  hint?: string;
  error?: string | null;
  children: (props: { id: string; "aria-describedby"?: string; "aria-invalid"?: boolean }) => ReactNode;
  className?: string;
}) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errId = `${id}-err`;
  const describedBy = [hint && hintId, error && errId].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="font-medium">
        {label}
      </label>
      {children({ id, "aria-describedby": describedBy, "aria-invalid": error ? true : undefined })}
      {hint && !error && (
        <p id={hintId} className="text-xs text-fg-tertiary">
          {hint}
        </p>
      )}
      {error && (
        <p id={errId} className="text-xs text-danger-fg">
          {error}
        </p>
      )}
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...rest },
  ref,
) {
  return <input ref={ref} className={cx(CONTROL, "h-9", className)} {...rest} />;
});

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cx(CONTROL, "h-9 pe-8", className)} {...rest}>
      {children}
    </select>
  );
}

export function Textarea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cx(CONTROL, "min-h-24 py-2 leading-normal", className)} {...rest} />;
}

// ---------------------------------------------------------------- lọc dạng phân đoạn
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string; count?: number; icon?: ReactNode }[];
  label: string;
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-1 rounded-lg bg-surface-hover p-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={cx(
            "pressable inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 text-[0.8125rem] font-medium",
            value === o.value ? "bg-surface text-fg shadow-card" : "text-fg-secondary hover:text-fg",
          )}
        >
          {o.icon}
          {o.label}
          {o.count != null && <span className="num text-fg-tertiary">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- trạng thái
export function Spinner({ label = "Đang tải…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-fg-secondary" role="status">
      <Loader2 className="size-4 animate-spin motion-reduce:animate-none" aria-hidden />
      {label}
    </div>
  );
}

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <p className="font-medium">{title}</p>
      {description && <p className="mt-1 max-w-[50ch] text-fg-secondary text-pretty">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof Error ? error.message : "Không tải được dữ liệu.";
  return (
    <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-danger-subtle px-4 py-3 text-danger-fg">
      <span>{msg}</span>
      {onRetry && (
        <Button size="sm" onClick={onRetry}>
          Thử lại
        </Button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- dialog
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const opener = useRef<Element | null>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      opener.current = document.activeElement;
      d.showModal(); // nền trở thành inert, Escape đóng, focus vào trong
    } else if (!open && d.open) {
      d.close();
      (opener.current as HTMLElement | null)?.focus?.();
    }
  }, [open]);
  const titleId = useId();
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      className={cx(
        "m-auto max-h-[90dvh] w-[calc(100%-2rem)] overflow-y-auto rounded-2xl bg-surface p-0 text-fg shadow-pop",
        wide ? "max-w-3xl" : "max-w-lg",
      )}
    >
      {open && (
        <div className="fade-in">
          <div className="flex items-start justify-between gap-4 px-5 pt-5">
            <div className="min-w-0">
              <h2 id={titleId} className="text-base font-semibold text-balance">
                {title}
              </h2>
              {description && <div className="mt-1 text-fg-secondary text-pretty">{description}</div>}
            </div>
            <IconButton label="Đóng hộp thoại" onClick={onClose} className="-me-2 -mt-1">
              <X className="size-4" aria-hidden />
            </IconButton>
          </div>
          <div className="px-5 py-4">{children}</div>
          {footer && <div className="flex flex-wrap justify-end gap-3 border-t border-line px-5 py-4">{footer}</div>}
        </div>
      )}
    </dialog>
  );
}

// ---------------------------------------------------------------- toast (vùng thông báo dựng sẵn, rỗng)
type ToastItem = { id: number; text: string; tone: "success" | "danger" };
const ToastCtx = createContext<(text: string, tone?: "success" | "danger") => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((text: string, tone: "success" | "danger" = "success") => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, text, tone }]);
    // Lỗi ở lại tới khi người dùng đóng; thông báo thành công tự ẩn
    if (tone === "success") setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 5000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div
        role="status"
        aria-live="polite"
        className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-center gap-2 sm:inset-x-auto sm:end-4 sm:items-end"
      >
        {items.map((t) => (
          <div
            key={t.id}
            className={cx(
              "fade-in pointer-events-auto flex max-w-sm items-start gap-3 rounded-xl px-4 py-3 shadow-pop",
              t.tone === "success" ? "bg-fg text-white" : "bg-danger-solid text-white",
            )}
          >
            <span className="text-pretty">{t.text}</span>
            <button
              className="-me-1 shrink-0 rounded opacity-80 hover:opacity-100"
              aria-label="Đóng thông báo"
              onClick={() => setItems((x) => x.filter((i) => i.id !== t.id))}
            >
              <X className="size-4" aria-hidden />
            </button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

// ---------------------------------------------------------------- bảng
export function Table({ children, label }: { children: ReactNode; label: string }) {
  return (
    <div className="relative overflow-x-auto" role="region" aria-label={label} tabIndex={0}>
      <table className="w-full min-w-[40rem] border-collapse text-start">{children}</table>
    </div>
  );
}
export const th = "border-b border-line px-4 py-2.5 text-start text-xs font-medium text-fg-secondary whitespace-nowrap";
export const td = "border-b border-line px-4 py-3 align-top";

// ---------------------------------------------------------------- phân trang "Tải thêm"
export function LoadMore({
  shown,
  total,
  noun,
  hasMore,
  loading,
  onMore,
}: {
  shown: number;
  total: number;
  noun: string;
  hasMore: boolean;
  loading?: boolean;
  onMore: () => void;
}) {
  if (!total) return null;
  return (
    <div className="mt-4 flex flex-wrap items-center justify-center gap-3 text-fg-secondary">
      <span className="num" aria-live="polite">
        Đang hiện {shown.toLocaleString("vi-VN")} / {total.toLocaleString("vi-VN")} {noun}
      </span>
      {hasMore && (
        <Button size="sm" loading={loading} onClick={onMore}>
          Tải thêm
        </Button>
      )}
    </div>
  );
}
