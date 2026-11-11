"use client";

import { useId, useState } from "react";
import { cx } from "@/components/ui";

/** Biểu đồ cột một chuỗi: một màu, không chú giải (tiêu đề đã gọi tên chuỗi), tooltip khi hover/focus,
 *  có bảng số liệu tương đương cho trình đọc màn hình và người cần số chính xác. */
export function BarChart({
  data,
  format,
  label,
  height = 180,
}: {
  data: { key: string; label: string; value: number }[];
  format: (n: number) => string;
  label: string;
  height?: number;
}) {
  const [active, setActive] = useState<number | null>(null);
  const tableId = useId();
  const max = Math.max(1, ...data.map((d) => d.value));
  const nice = niceMax(max);
  const ticks = [0, nice / 2, nice];
  return (
    <figure className="m-0">
      <div className="relative ps-14" style={{ height }} aria-describedby={tableId}>
        {/* lưới + trục: nhạt, lùi về sau */}
        {ticks.map((t) => (
          <div
            key={t}
            className="absolute inset-x-0 border-t border-[var(--color-chart-grid)]"
            style={{ bottom: `${(t / nice) * 100}%` }}
            aria-hidden
          >
            <span className="num absolute -top-2 start-0 w-12 text-end text-[0.6875rem] text-fg-tertiary">
              {compact(t)}
            </span>
          </div>
        ))}
        <div className="absolute inset-y-0 end-0 start-14 flex items-end gap-[2px]">
          {data.map((d, i) => (
            <button
              key={d.key}
              type="button"
              aria-label={`${d.label}: ${format(d.value)}`}
              onMouseEnter={() => setActive(i)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
              className="group relative flex h-full flex-1 items-end justify-center"
            >
              <span
                className={cx(
                  "block w-full max-w-10 rounded-t-[4px] bg-[var(--color-chart-1)]",
                  active != null && active !== i && "opacity-50",
                )}
                style={{ height: `${Math.max(0, (d.value / nice) * 100)}%` }}
              />
              {active === i && (
                <span
                  role="tooltip"
                  className="num pointer-events-none absolute bottom-full z-10 mb-2 rounded-lg bg-fg px-2.5 py-1.5 text-xs whitespace-nowrap text-white shadow-pop"
                >
                  {d.label}: {format(d.value)}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-2 flex gap-[2px] ps-14" aria-hidden>
        {data.map((d) => (
          <span key={d.key} className="flex-1 text-center text-[0.6875rem] text-fg-tertiary">
            {d.label}
          </span>
        ))}
      </div>
      <details className="mt-3">
        <summary className="cursor-pointer text-[0.8125rem] font-medium text-accent-fg">Xem dạng bảng</summary>
        <table id={tableId} className="num mt-2 w-full text-start">
          <caption className="sr-only">{label}</caption>
          <tbody>
            {data.map((d) => (
              <tr key={d.key} className="border-b border-line">
                <th scope="row" className="py-1.5 text-start font-normal text-fg-secondary">
                  {d.label}
                </th>
                <td className="py-1.5 text-end">{format(d.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}

function niceMax(v: number): number {
  const p = 10 ** Math.floor(Math.log10(v));
  return Math.ceil(v / p) * p;
}

function compact(n: number): string {
  if (n >= 1e9) return `${+(n / 1e9).toFixed(1)} tỷ`;
  if (n >= 1e6) return `${+(n / 1e6).toFixed(0)} tr`;
  return String(n);
}
