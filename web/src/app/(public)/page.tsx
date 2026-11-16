import { ArrowRight, BadgeCheck, CalendarClock, Clock3, RotateCcw, Wallet } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { CATEGORY, CourseCard, SHIFT_LABEL, dateVN, vndShort } from "@/components/public/course-visual";
import { LeadForm } from "@/components/public/lead-form";
import { type Center, type PublicClass, type PublicCourse, pub } from "@/lib/public-api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: { absolute: "Trung tâm Đào tạo Ánh Dương · Ngoại ngữ, Tin học, Lập trình, Dữ liệu" },
  description:
    "Khoá IELTS, TOEIC, tiếng Anh giao tiếp, Excel, lập trình, phân tích dữ liệu và kỹ năng mềm. Học thử miễn phí, trả góp học phí, lớp sáng chiều tối.",
  alternates: { canonical: "/" },
};

const PROMISES = [
  { icon: BadgeCheck, title: "Học thử miễn phí", text: "Học thử 1 buổi trước khi đăng ký; khoá tiếng Anh có kiểm tra đầu vào miễn phí." },
  { icon: Wallet, title: "Trả góp học phí", text: "Khoá từ 5 triệu chia 2 đợt, không mất phí, không cần giấy tờ." },
  { icon: RotateCcw, title: "Hoàn phí rõ ràng", text: "Huỷ trước khai giảng ít nhất 7 ngày hoàn 100%; được bảo lưu một lần, tối đa 6 tháng." },
  { icon: Clock3, title: "Lớp sáng, chiều, tối", text: "Ca 8h00, 14h00, 18h30; lịch 2-4-6, 3-5-7 hoặc cuối tuần, tại cơ sở hoặc online." },
];

export default async function HomePage() {
  const [courses, schedule, center] = await Promise.all([
    pub<PublicCourse[]>("/public/courses"),
    pub<PublicClass[]>("/public/schedule"),
    pub<Center>("/public/center"),
  ]);
  const featured = (courses ?? [])
    .filter((c) => c.so_lop_sap_mo)
    .sort((a, b) => (a.khai_giang_gan_nhat ?? "").localeCompare(b.khai_giang_gan_nhat ?? ""))
    .slice(0, 6);
  const soon = (schedule ?? []).filter((c) => c.cho_trong > 0).slice(0, 6);
  const options = (courses ?? []).map((c) => ({ slug: c.slug, ten: c.ten }));

  return (
    <>
      {/* ------------------------------------------------ hero */}
      <section className="relative isolate overflow-hidden bg-side text-side-fg">
        <svg viewBox="0 0 600 600" className="pointer-events-none absolute -end-56 -bottom-[26rem] -z-10 w-[52rem] max-w-none opacity-90" aria-hidden>
          {[290, 240, 190, 140].map((r, i) => (
            <circle key={r} cx="300" cy="300" r={r} fill="none" stroke="var(--color-brand)" strokeOpacity={0.1 + i * 0.09} strokeWidth="1.5" />
          ))}
          <circle cx="300" cy="300" r="96" fill="var(--color-brand)" />
        </svg>
        <div className="mx-auto grid max-w-6xl gap-12 px-4 pt-16 pb-20 sm:px-6 lg:grid-cols-[1.15fr_1fr] lg:pt-24 lg:pb-28">
          <div>
            <p className="text-xs font-medium tracking-[0.08em] text-brand uppercase">Ngoại ngữ · Tin học · Lập trình · Dữ liệu · Kỹ năng</p>
            <h1 className="font-display mt-4 text-[2.5rem] leading-[1.05] font-medium text-balance sm:text-6xl">
              Học đúng thứ bạn cần, <span className="text-brand">tiến bộ</span> thấy rõ mỗi tuần.
            </h1>
            <p className="mt-5 max-w-xl text-lg text-side-fg-secondary text-pretty">
              {center ? `${center.so_khoa} khoá học, ${center.so_giang_vien} giảng viên, ` : ""}lớp nhỏ, lịch linh hoạt sáng chiều tối.
              Học thử miễn phí một buổi trước khi đăng ký.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/khoa-hoc"
                className="pressable inline-flex h-12 items-center gap-2 rounded-xl bg-brand px-5 text-base font-semibold text-fg hover:brightness-95"
              >
                Xem khoá học
                <ArrowRight className="size-4" aria-hidden />
              </Link>
              <Link
                href="/dang-ky-tu-van"
                className="pressable inline-flex h-12 items-center rounded-xl px-5 text-base font-semibold ring-1 ring-white/30 hover:bg-white/10"
              >
                Nhận tư vấn lộ trình
              </Link>
            </div>
          </div>
          {center && (
            <dl className="grid grid-cols-2 gap-3 self-end">
              {[
                [center.so_hoc_vien.toLocaleString("vi-VN"), "học viên đã ghi danh"],
                [center.so_lop.toLocaleString("vi-VN"), "lớp đã mở"],
                [String(center.so_khoa), "khoá học đang tuyển sinh"],
                [String(center.co_so.length), "cơ sở và lớp online"],
              ].map(([n, l]) => (
                <div key={l} className="rounded-2xl bg-side-active p-5 ring-1 ring-white/10">
                  <dt className="sr-only">{l}</dt>
                  <dd>
                    <span className="num font-display block text-4xl font-medium">{n}</span>
                    <span className="mt-1 block text-side-fg-secondary">{l}</span>
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      </section>

      {/* ------------------------------------------------ danh mục */}
      <section className="mx-auto max-w-6xl px-4 pt-16 sm:px-6" aria-labelledby="danh-muc">
        <h2 id="danh-muc" className="font-display text-3xl font-medium text-balance">Bạn muốn học gì?</h2>
        <ul className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {Object.entries(CATEGORY).map(([name, c]) => {
            const stat = center?.danh_muc.find((d) => d.danh_muc === name);
            const Icon = c.icon;
            return (
              <li key={name}>
                <Link
                  href={`/khoa-hoc?danh_muc=${encodeURIComponent(name)}`}
                  className="group flex h-full flex-col gap-3 rounded-2xl bg-surface p-5 shadow-card transition-shadow hover:shadow-lift"
                >
                  <span className="grid size-11 place-items-center rounded-xl text-white" style={{ background: c.color }}>
                    <Icon className="size-5" aria-hidden />
                  </span>
                  <span className="font-semibold">{name}</span>
                  <span className="text-fg-secondary text-pretty">{c.blurb}</span>
                  {stat && (
                    <span className="mt-auto text-xs text-fg-tertiary">
                      {stat.so_khoa} khoá · từ <span className="num">{vndShort(stat.hoc_phi_tu)}</span>
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </section>

      {/* ------------------------------------------------ khoá sắp khai giảng */}
      {featured.length > 0 && (
        <section className="mx-auto max-w-6xl px-4 pt-20 sm:px-6" aria-labelledby="noi-bat">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 id="noi-bat" className="font-display text-3xl font-medium text-balance">Khoá học sắp khai giảng</h2>
              <p className="mt-1 text-fg-secondary">Giữ chỗ sớm để chọn được ca học phù hợp.</p>
            </div>
            <Link href="/khoa-hoc" className="inline-flex items-center gap-1 font-medium text-accent-fg hover:underline">
              Tất cả {courses?.length} khoá học <ArrowRight className="size-4" aria-hidden />
            </Link>
          </div>
          <ul className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {featured.map((c) => (
              <li key={c.slug}>
                <CourseCard c={c} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ------------------------------------------------ cam kết */}
      <section className="mx-auto max-w-6xl px-4 pt-20 sm:px-6" aria-labelledby="cam-ket">
        <div className="rounded-3xl bg-brand-subtle px-6 py-10 sm:px-10">
          <h2 id="cam-ket" className="font-display text-3xl font-medium text-balance">
            Học yên tâm, <span className="marker">quy định rõ ràng</span>
          </h2>
          <ul className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {PROMISES.map((p) => (
              <li key={p.title}>
                <p.icon className="size-6 text-accent-fg" aria-hidden />
                <p className="mt-3 font-semibold">{p.title}</p>
                <p className="mt-1 text-fg-secondary text-pretty">{p.text}</p>
              </li>
            ))}
          </ul>
          <Link href="/chinh-sach" className="mt-8 inline-flex items-center gap-1 font-medium text-accent-fg hover:underline">
            Đọc đầy đủ chính sách <ArrowRight className="size-4" aria-hidden />
          </Link>
        </div>
      </section>

      {/* ------------------------------------------------ lịch khai giảng */}
      {soon.length > 0 && (
        <section className="mx-auto max-w-6xl px-4 pt-20 sm:px-6" aria-labelledby="lich">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <h2 id="lich" className="font-display text-3xl font-medium text-balance">Lớp còn chỗ</h2>
            <Link href="/lich-khai-giang" className="inline-flex items-center gap-1 font-medium text-accent-fg hover:underline">
              Xem lịch khai giảng <ArrowRight className="size-4" aria-hidden />
            </Link>
          </div>
          <ul className="mt-6 grid gap-3 md:grid-cols-2">
            {soon.map((l) => (
              <li key={l.id}>
                <Link href={`/khoa-hoc/${l.slug}`} className="flex items-center gap-4 rounded-2xl bg-surface p-4 shadow-card hover:shadow-lift">
                  <span className="grid w-16 shrink-0 place-items-center rounded-xl bg-surface-muted py-2 text-center">
                    <CalendarClock className="size-4 text-fg-tertiary" aria-hidden />
                    <span className="num mt-1 text-sm font-semibold">{dateVN(l.ngay_khai_giang).slice(0, -5)}</span>
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-semibold">{l.khoa_hoc}</span>
                    <span className="block text-fg-secondary">
                      Ca {SHIFT_LABEL[l.ca_hoc].toLowerCase()} · {l.lich_hoc} · {l.hinh_thuc === "online" ? "Online" : l.co_so ?? "Tại trung tâm"}
                    </span>
                  </span>
                  <span className={l.cho_trong <= 3 ? "shrink-0 rounded-full bg-warning-subtle px-2.5 py-1 text-xs font-medium text-warning-fg" : "shrink-0 text-xs text-fg-tertiary"}>
                    Còn {l.cho_trong} chỗ
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ------------------------------------------------ đăng ký */}
      <section className="mx-auto max-w-6xl px-4 pt-20 sm:px-6" aria-labelledby="dang-ky">
        <div className="grid gap-10 rounded-3xl bg-surface p-6 shadow-card sm:p-10 lg:grid-cols-[1fr_1.2fr]">
          <div>
            <h2 id="dang-ky" className="font-display text-3xl font-medium text-balance">Chưa biết bắt đầu từ đâu?</h2>
            <p className="mt-3 text-fg-secondary text-pretty">
              Để lại thông tin, tư vấn viên sẽ gọi lại trong giờ làm việc để hỏi mục tiêu, gợi ý lộ trình và lớp hợp lịch của bạn. Tư vấn miễn phí.
            </p>
            <p className="mt-6 text-fg-secondary">
              Hoặc gọi ngay <a href="tel:19000000" className="num font-semibold text-fg underline">1900 0000</a> (8:00–21:00 thứ Hai–thứ Bảy, Chủ nhật 8:00–17:00).
            </p>
          </div>
          <LeadForm courses={options} />
        </div>
      </section>
    </>
  );
}
