"use client";

import { ArrowUpRight, Moon, Sun, Sunrise } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import useSWR from "swr";
import { BarChart } from "@/components/bar-chart";
import { ErrorBox, Meter, Spinner, cx } from "@/components/ui";
import { daysFrom, fmtDate, num, pct, vnd } from "@/lib/format";
import { SHIFT } from "@/lib/labels";

type Session = {
  id: number;
  so_thu_tu: number;
  lop_hoc_id: number;
  ma_lop: string;
  khoa_hoc: string;
  so_buoi: number;
  ca_hoc: string;
  hinh_thuc: string;
  giang_vien: string;
  phong: string | null;
  co_so: string | null;
  si_so: number;
};

type Dash = {
  ngay: string;
  lich_hom_nay: Session[];
  doanh_thu_thang: number;
  doanh_thu_cung_ky_thang_truoc: number;
  doanh_thu_theo_thang: { thang: string; doanh_thu: number }[];
  cong_no: { qua_han: number; hv_qua_han: number; tong_con_no: number };
  hoc_vien_dang_hoc: number;
  tuyen_sinh: { moi_30_ngay: number; ghi_danh: number; cham_lien_he: number };
  lop_sap_khai_giang: {
    id: number;
    ma_lop: string;
    khoa_hoc: string;
    ngay_khai_giang: string;
    si_so: number;
    si_so_toi_da: number;
    si_so_toi_thieu: number;
  }[];
  chuyen_can_4_tuan: number | null;
  agent: { cho_duyet: number; tu_dong_7_ngay: number; duyet_7_ngay: number };
};

const SHIFT_ICON = { sang: Sunrise, chieu: Sun, toi: Moon } as const;

function Section({ title, children, className, action }: { title: string; children: ReactNode; className?: string; action?: ReactNode }) {
  return (
    <section className={cx("min-w-0", className)}>
      <div className="mb-3 flex items-baseline justify-between gap-3 border-b-2 border-fg pb-1.5">
        <h2 className="text-xs font-semibold tracking-[0.05em] uppercase">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function MoreLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className="inline-flex items-center gap-0.5 text-[0.8125rem] font-medium text-accent-fg hover:underline">
      {children}
      <ArrowUpRight className="size-3.5" aria-hidden />
    </Link>
  );
}

/** Một dòng "việc cần bạn": số to kiểu báo, câu giải thích, đường dẫn tới nơi xử lý. */
function Need({ value, text, href, cta, urgent }: { value: ReactNode; text: ReactNode; href: string; cta: string; urgent?: boolean }) {
  return (
    <li className="flex items-start gap-4 border-b border-line py-3 last:border-0">
      <span className={cx("font-display num w-16 shrink-0 text-end text-3xl leading-none font-medium", urgent && "text-danger-fg")}>{value}</span>
      <span className="min-w-0 flex-1">
        <span className="block text-pretty">{text}</span>
        <span className="mt-1 block">
          <MoreLink href={href}>{cta}</MoreLink>
        </span>
      </span>
    </li>
  );
}

function Headline({ d }: { d: Dash }) {
  const parts: ReactNode[] = [];
  parts.push(
    d.lich_hom_nay.length ? (
      <span key="s">
        Hôm nay có <span className="marker">{d.lich_hom_nay.length} buổi học</span>
      </span>
    ) : (
      <span key="s">Hôm nay không có buổi học nào</span>
    ),
  );
  const tail: ReactNode[] = [];
  if (d.agent.cho_duyet)
    tail.push(
      <span key="a">
        <span className="marker">{d.agent.cho_duyet} đề xuất</span> của agent chờ bạn duyệt
      </span>,
    );
  if (d.cong_no.hv_qua_han)
    tail.push(
      <span key="n">
        <span className="marker">{d.cong_no.hv_qua_han} học viên</span> đang nợ quá hạn
      </span>,
    );
  return (
    <h1
      tabIndex={-1}
      data-page-title
      className="font-display max-w-[30ch] text-[1.625rem] leading-snug font-normal text-balance outline-none sm:text-[2.125rem]"
    >
      {parts}
      {tail.length > 0 && ", "}
      {tail.map((t, i) => (
        <span key={i}>
          {i > 0 && " và "}
          {t}
        </span>
      ))}
      .
    </h1>
  );
}

export default function DashboardPage() {
  const { data: d, error, mutate } = useSWR<Dash>("/dashboard");
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!d) return <Spinner />;
  const change = d.doanh_thu_cung_ky_thang_truoc ? d.doanh_thu_thang / d.doanh_thu_cung_ky_thang_truoc - 1 : null;
  const conv = d.tuyen_sinh.moi_30_ngay ? d.tuyen_sinh.ghi_danh / d.tuyen_sinh.moi_30_ngay : null;
  const short = d.lop_sap_khai_giang.filter((c) => c.si_so < c.si_so_toi_thieu);
  const byShift = (["sang", "chieu", "toi"] as const).map((s) => ({ s, rows: d.lich_hom_nay.filter((x) => x.ca_hoc === s) }));

  return (
    <article>
      <div className="mb-8 border-b border-line pb-8">
        <p className="mb-2 text-xs font-medium tracking-[0.05em] text-fg-tertiary uppercase">Bản tin vận hành · {fmtDate(d.ngay)}</p>
        <Headline d={d} />
        <p className="mt-3 max-w-[70ch] text-fg-secondary text-pretty">
          {num(d.hoc_vien_dang_hoc)} học viên đang theo học
          {d.chuyen_can_4_tuan != null && `, chuyên cần 4 tuần qua ${pct(d.chuyen_can_4_tuan)}`}. Số liệu lấy từ cùng nguồn với agent phân tích.
        </p>
      </div>

      <div className="grid gap-x-10 gap-y-10 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_minmax(0,1fr)]">
        <Section title="Lịch học hôm nay" action={<MoreLink href="/classes">Thời khoá biểu</MoreLink>}>
          {d.lich_hom_nay.length === 0 ? (
            <p className="py-6 text-fg-secondary">Không có buổi nào. Lịch tuần đầy đủ ở trang Lớp học.</p>
          ) : (
            <ol className="flex flex-col gap-5">
              {byShift
                .filter((g) => g.rows.length)
                .map(({ s, rows }) => {
                  const Icon = SHIFT_ICON[s];
                  return (
                    <li key={s} className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-3">
                      <p className="flex items-center gap-1.5 pt-2.5 font-medium text-fg-secondary">
                        <Icon className="size-4" strokeWidth={1.75} aria-hidden />
                        {SHIFT[s]}
                      </p>
                      <ul className="flex flex-col gap-2">
                        {rows.map((r) => (
                          <li key={r.id}>
                            <Link
                              href={`/classes/${r.lop_hoc_id}`}
                              className="block rounded-xl border-s-4 border-accent-solid bg-surface px-3 py-2.5 shadow-card transition-[box-shadow] duration-150 hover:shadow-lift"
                            >
                              <span className="flex items-baseline justify-between gap-2">
                                <span className="font-mono text-[0.8125rem] font-medium">{r.ma_lop}</span>
                                <span className="num text-xs text-fg-tertiary">
                                  Buổi {r.so_thu_tu}/{r.so_buoi}
                                </span>
                              </span>
                              <span className="mt-0.5 block truncate font-medium">{r.khoa_hoc}</span>
                              <span className="mt-0.5 block truncate text-xs text-fg-secondary">
                                {r.hinh_thuc === "online" ? "Trực tuyến" : `${r.co_so ?? ""} · ${r.phong ?? ""}`} · {r.giang_vien} · {r.si_so} học viên
                              </span>
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </li>
                  );
                })}
            </ol>
          )}
        </Section>

        <Section title="Cần bạn xử lý">
          <ul>
            <Need
              value={d.agent.cho_duyet}
              text={
                <>
                  đề xuất của agent đang chờ duyệt. Tuần này agent đã tự làm {d.agent.tu_dong_7_ngay} việc trong hạn mức, {d.agent.duyet_7_ngay} việc
                  được duyệt rồi mới làm.
                </>
              }
              href="/inbox"
              cta="Mở hộp duyệt"
            />
            <Need
              value={d.cong_no.hv_qua_han}
              urgent={d.cong_no.hv_qua_han > 0}
              text={
                <>
                  học viên có đợt quá hạn, tổng <span className="num font-medium">{vnd(d.cong_no.qua_han)}</span>. Còn phải thu tất cả{" "}
                  <span className="num">{vnd(d.cong_no.tong_con_no)}</span>.
                </>
              }
              href="/finance"
              cta="Xem thang nhắc nợ"
            />
            <Need
              value={d.tuyen_sinh.cham_lien_he}
              urgent={d.tuyen_sinh.cham_lien_he > 0}
              text={
                <>
                  khách mới quá 3 ngày chưa ai gọi. 30 ngày qua có {d.tuyen_sinh.moi_30_ngay} khách, {conv == null ? "–" : pct(conv)} đã ghi danh.
                </>
              }
              href="/leads"
              cta="Mở bảng tuyển sinh"
            />
            {short.length > 0 && (
              <Need
                value={short.length}
                text={<>lớp sắp khai giảng chưa đủ sĩ số tối thiểu. Agent giáo vụ sẽ đề xuất gộp hoặc huỷ khi còn 7 ngày.</>}
                href="/classes"
                cta="Xem các lớp"
              />
            )}
          </ul>
        </Section>

        <Section title="Tiền vào" className="lg:col-span-2 xl:col-span-1">
          <p className="text-fg-secondary">Đã thu trong tháng, trừ hoàn phí</p>
          <p className="font-display num mt-1 text-4xl font-medium">{vnd(d.doanh_thu_thang)}</p>
          {change != null && (
            <p className={cx("mt-1 font-medium", change >= 0 ? "text-success-fg" : "text-danger-fg")}>
              {change >= 0 ? "▲ Tăng" : "▼ Giảm"} {pct(Math.abs(change))}
              <span className="font-normal text-fg-secondary"> so với cùng kỳ tháng trước</span>
            </p>
          )}
          <div className="mt-5">
            <BarChart
              label="Doanh thu theo tháng"
              format={vnd}
              height={140}
              data={d.doanh_thu_theo_thang.map((r) => ({ key: r.thang, label: `T${Number(r.thang.slice(5))}`, value: r.doanh_thu }))}
            />
          </div>
        </Section>
      </div>

      <Section title="Sắp khai giảng · 30 ngày tới" className="mt-12" action={<MoreLink href="/classes">Tất cả lớp</MoreLink>}>
        {d.lop_sap_khai_giang.length === 0 ? (
          <p className="py-6 text-fg-secondary">Chưa có lớp nào khai giảng trong 30 ngày tới.</p>
        ) : (
          <ul className="relative -mx-4 flex snap-x gap-4 overflow-x-auto px-4 pt-1 pb-3 sm:mx-0 sm:px-0" aria-label="Lớp sắp khai giảng">
            {d.lop_sap_khai_giang.map((c) => {
              const left = daysFrom(c.ngay_khai_giang);
              const ok = c.si_so >= c.si_so_toi_thieu;
              return (
                <li key={c.id} className="w-64 shrink-0 snap-start">
                  <Link href={`/classes/${c.id}`} className="flex h-full overflow-hidden rounded-xl bg-surface shadow-card transition-[box-shadow] duration-150 hover:shadow-lift">
                    <span className="flex w-16 shrink-0 flex-col items-center justify-center border-e border-dashed border-line-strong bg-brand-subtle px-1 text-center">
                      {left <= 0 ? (
                        <span className="font-display text-lg leading-tight font-semibold">Hôm nay</span>
                      ) : (
                        <>
                          <span className="font-display num text-2xl leading-none font-semibold">{left}</span>
                          <span className="mt-1 text-[0.6875rem] text-fg-secondary">ngày nữa</span>
                        </>
                      )}
                    </span>
                    <span className="min-w-0 flex-1 px-3 py-3">
                      <span className="block font-mono text-[0.8125rem] font-medium">{c.ma_lop}</span>
                      <span className="block truncate text-fg-secondary">{c.khoa_hoc}</span>
                      <Meter className="mt-3" value={c.si_so} max={c.si_so_toi_da} mark={c.si_so_toi_thieu} tone={ok ? "success" : "warning"} />
                      <span className={cx("num mt-1.5 block text-xs", ok ? "text-fg-secondary" : "font-medium text-warning-fg")}>
                        {c.si_so}/{c.si_so_toi_da} chỗ · {ok ? "đủ để mở lớp" : `thiếu ${c.si_so_toi_thieu - c.si_so} để mở lớp`}
                      </span>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </Section>
    </article>
  );
}
