import type { Metadata } from "next";
import Link from "next/link";
import { CATEGORY, SHIFT_LABEL, cat, dateVN, vndFull, weekdayVN } from "@/components/public/course-visual";
import { type PublicClass, pub } from "@/lib/public-api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Lịch khai giảng",
  description: "Lịch khai giảng các lớp sắp mở: ngày bắt đầu, ca học, lịch trong tuần, hình thức học và số chỗ còn trống.",
  alternates: { canonical: "/lich-khai-giang" },
};

const SHIFT_TIME: Record<string, string> = { sang: "8h00", chieu: "14h00", toi: "18h30" };

export default async function SchedulePage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const { danh_muc, ca } = await searchParams;
  const all = (await pub<PublicClass[]>("/public/schedule")) ?? [];
  const list = all.filter((l) => (!danh_muc || l.danh_muc === danh_muc) && (!ca || l.ca_hoc === ca));
  const byMonth = new Map<string, PublicClass[]>();
  for (const l of list) {
    const key = l.ngay_khai_giang.slice(0, 7);
    byMonth.set(key, [...(byMonth.get(key) ?? []), l]);
  }
  const href = (dm?: string, c?: string) => {
    const q = new URLSearchParams({ ...(dm && { danh_muc: dm }), ...(c && { ca: c }) }).toString();
    return q ? `/lich-khai-giang?${q}` : "/lich-khai-giang";
  };
  const chip = (on: boolean) =>
    on ? "rounded-full bg-fg px-3.5 py-1.5 font-medium text-surface" : "rounded-full bg-surface px-3.5 py-1.5 font-medium text-fg-secondary shadow-card hover:text-fg";

  return (
    <div className="mx-auto max-w-6xl px-4 pt-12 sm:px-6">
      <h1 className="font-display text-4xl font-medium text-balance sm:text-5xl">Lịch khai giảng</h1>
      <p className="mt-3 max-w-2xl text-lg text-fg-secondary text-pretty">
        Ca sáng 8h00–10h00, ca chiều 14h00–16h00, ca tối 18h30–20h30. Lớp online học qua Zoom.
      </p>
      <nav aria-label="Lọc lịch" className="mt-8 flex flex-col gap-3">
        <ul className="flex flex-wrap gap-2">
          <li><Link href={href(undefined, ca)} className={chip(!danh_muc)}>Tất cả lĩnh vực</Link></li>
          {Object.keys(CATEGORY).map((c) => (
            <li key={c}><Link href={href(c, ca)} className={chip(danh_muc === c)}>{c}</Link></li>
          ))}
        </ul>
        <ul className="flex flex-wrap gap-2 text-[0.8125rem]">
          <li><Link href={href(danh_muc)} className={chip(!ca)}>Mọi ca</Link></li>
          {Object.entries(SHIFT_LABEL).map(([k, v]) => (
            <li key={k}><Link href={href(danh_muc, k)} className={chip(ca === k)}>Ca {v.toLowerCase()}</Link></li>
          ))}
        </ul>
      </nav>

      {list.length === 0 ? (
        <p className="mt-10 rounded-2xl bg-surface p-10 text-center shadow-card">
          {all.length ? "Chưa có lớp khớp bộ lọc." : "Chưa có lớp nào sắp khai giảng, hoặc trang tạm thời không tải được."}{" "}
          <Link href="/dang-ky-tu-van" className="font-medium text-accent-fg underline">Đăng ký để được báo lịch mới</Link>
        </p>
      ) : (
        [...byMonth.entries()].map(([month, rows]) => (
          <section key={month} className="mt-10" aria-labelledby={`thang-${month}`}>
            <h2 id={`thang-${month}`} className="font-display text-2xl font-medium">
              Tháng {Number(month.slice(5))}/{month.slice(0, 4)}
            </h2>
            <div className="mt-4 overflow-x-auto rounded-2xl bg-surface shadow-card" role="region" aria-label={`Lớp khai giảng tháng ${Number(month.slice(5))}`} tabIndex={0}>
              <table className="w-full min-w-[44rem] border-collapse text-start">
                <thead>
                  <tr className="text-xs text-fg-secondary">
                    <th className="border-b border-line px-4 py-3 text-start font-medium">Khai giảng</th>
                    <th className="border-b border-line px-4 py-3 text-start font-medium">Khoá học</th>
                    <th className="border-b border-line px-4 py-3 text-start font-medium">Lịch học</th>
                    <th className="border-b border-line px-4 py-3 text-start font-medium">Hình thức</th>
                    <th className="border-b border-line px-4 py-3 text-end font-medium">Học phí</th>
                    <th className="border-b border-line px-4 py-3 text-end font-medium">Chỗ trống</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((l) => (
                    <tr key={l.id} className="hover:bg-surface-hover">
                      <td className="num border-b border-line px-4 py-3 align-top font-semibold">
                        {dateVN(l.ngay_khai_giang)}
                        <span className="block text-xs font-normal text-fg-tertiary first-letter:uppercase">{weekdayVN(l.ngay_khai_giang)}</span>
                      </td>
                      <td className="border-b border-line px-4 py-3 align-top">
                        <span className="flex items-start gap-2">
                          <span className="mt-1.5 size-2 shrink-0 rounded-full" style={{ background: cat(l.danh_muc).color }} aria-hidden />
                          <Link href={`/khoa-hoc/${l.slug}`} className="font-medium hover:underline">{l.khoa_hoc}</Link>
                        </span>
                      </td>
                      <td className="border-b border-line px-4 py-3 align-top text-fg-secondary">
                        {SHIFT_LABEL[l.ca_hoc]} {SHIFT_TIME[l.ca_hoc]} · {l.lich_hoc}
                      </td>
                      <td className="border-b border-line px-4 py-3 align-top text-fg-secondary">
                        {l.hinh_thuc === "online" ? "Online" : (l.co_so ?? "Tại trung tâm")}
                      </td>
                      <td className="num border-b border-line px-4 py-3 text-end align-top">{vndFull(l.hoc_phi)}</td>
                      <td className="num border-b border-line px-4 py-3 text-end align-top">
                        <span className={l.cho_trong <= 3 ? "font-semibold text-warning-fg" : ""}>{l.cho_trong > 0 ? l.cho_trong : "Đủ"}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ))
      )}
    </div>
  );
}
