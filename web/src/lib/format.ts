const money = new Intl.NumberFormat("vi-VN");
const date = new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
const dateShort = new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit" });
const dateTime = new Intl.DateTimeFormat("vi-VN", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});
const weekday = new Intl.DateTimeFormat("vi-VN", { weekday: "short", day: "2-digit", month: "2-digit" });
const percent = new Intl.NumberFormat("vi-VN", { style: "percent", maximumFractionDigits: 0 });
const relative = new Intl.RelativeTimeFormat("vi-VN", { numeric: "auto" });

function toDate(v: string | Date): Date {
  if (v instanceof Date) return v;
  // "2026-11-11" là ngày theo lịch, không phải mốc UTC -> dựng theo giờ địa phương để không lệch ngày
  return /^\d{4}-\d{2}-\d{2}$/.test(v) ? new Date(`${v}T00:00:00`) : new Date(v);
}

export const vnd = (n: number | null | undefined) => (n == null ? "–" : `${money.format(n)}đ`);
export const num = (n: number | null | undefined) => (n == null ? "–" : money.format(n));
export const pct = (n: number | null | undefined) => (n == null ? "–" : percent.format(n));
export const fmtDate = (v?: string | null) => (v ? date.format(toDate(v)) : "–");
export const fmtDay = (v?: string | null) => (v ? dateShort.format(toDate(v)) : "–");
export const fmtWeekday = (v?: string | null) => (v ? weekday.format(toDate(v)) : "–");
export const fmtDateTime = (v?: string | null) => (v ? dateTime.format(toDate(v)) : "–");

export function daysFrom(v: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((toDate(v).getTime() - today.getTime()) / 86_400_000);
}

export function relDay(v: string): string {
  return relative.format(daysFrom(v), "day");
}
