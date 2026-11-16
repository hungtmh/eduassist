import { CalendarDays, Check, Clock, MapPin, Monitor, Users, Wallet } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CourseCard, CourseCover, SHIFT_LABEL, dateVN, vndFull, weekdayVN } from "@/components/public/course-visual";
import { LeadForm } from "@/components/public/lead-form";
import { type CourseDetail, PublicNotFound, SITE_URL, pub } from "@/lib/public-api";

export const dynamic = "force-dynamic";
const SHIFT_TIME: Record<string, string> = { sang: "8h00–10h00", chieu: "14h00–16h00", toi: "18h30–20h30" };

async function load(slug: string): Promise<CourseDetail | null> {
  try {
    return await pub<CourseDetail>(`/public/courses/${encodeURIComponent(slug)}`);
  } catch (e) {
    if (e instanceof PublicNotFound) notFound();
    throw e;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const c = await load((await params).slug);
  if (!c) return { title: "Khoá học" };
  const description = `${c.mo_ta_ngan} ${c.so_buoi} buổi, học phí ${vndFull(c.hoc_phi)}.`;
  return {
    title: c.ten,
    description,
    alternates: { canonical: `/khoa-hoc/${c.slug}` },
    openGraph: { title: c.ten, description, type: "website", url: `/khoa-hoc/${c.slug}` },
  };
}

export default async function CoursePage({ params }: { params: Promise<{ slug: string }> }) {
  const c = await load((await params).slug);
  if (!c) return <p className="mx-auto max-w-6xl px-4 py-20 text-center">Không tải được thông tin khoá học. Bạn thử tải lại trang.</p>;

  // Dữ liệu có cấu trúc schema.org/Course: Google hiểu đây là trang khoá học (tên, mô tả, đơn vị, học phí, lịch)
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Course",
    name: c.ten,
    description: c.mo_ta,
    courseCode: c.ma,
    url: `${SITE_URL}/khoa-hoc/${c.slug}`,
    provider: { "@type": "EducationalOrganization", name: "Trung tâm Đào tạo Ánh Dương", url: SITE_URL },
    offers: { "@type": "Offer", price: c.hoc_phi, priceCurrency: "VND", category: "Paid" },
    hasCourseInstance: c.lop_sap_mo.map((l) => ({
      "@type": "CourseInstance",
      courseMode: l.hinh_thuc === "online" ? "Online" : "Onsite",
      startDate: l.ngay_khai_giang,
      ...(l.giang_vien && { instructor: { "@type": "Person", name: l.giang_vien } }),
    })),
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }} />
      <section className="relative isolate overflow-hidden">
        <CourseCover danhMuc={c.danh_muc} big className="absolute inset-0 -z-10" />
        <div className="mx-auto max-w-6xl px-4 pt-10 pb-14 text-white sm:px-6 sm:pt-14">
          <nav aria-label="Đường dẫn" className="text-sm text-white/80">
            <Link href="/khoa-hoc" className="hover:underline">Khoá học</Link>
            {" / "}
            <Link href={`/khoa-hoc?danh_muc=${encodeURIComponent(c.danh_muc)}`} className="hover:underline">{c.danh_muc}</Link>
          </nav>
          <h1 className="font-display mt-16 max-w-3xl text-4xl leading-tight font-medium text-balance sm:mt-20 sm:text-5xl">{c.ten}</h1>
          <p className="mt-3 max-w-2xl text-lg text-white/85 text-pretty">{c.mo_ta_ngan}</p>
          <ul className="mt-6 flex flex-wrap gap-2 text-sm">
            {[c.trinh_do, `${c.so_buoi} buổi`, vndFull(c.hoc_phi)].map((t) => (
              <li key={t} className="num rounded-full bg-white/15 px-3 py-1 font-medium backdrop-blur-sm">{t}</li>
            ))}
            {c.tra_gop && <li className="rounded-full bg-brand px-3 py-1 font-semibold text-fg">Trả góp 2 đợt</li>}
          </ul>
        </div>
      </section>

      <div className="mx-auto grid max-w-6xl gap-10 px-4 pt-12 sm:px-6 lg:grid-cols-[1fr_22rem]">
        <div className="min-w-0">
          <section aria-labelledby="gioi-thieu">
            <h2 id="gioi-thieu" className="font-display text-2xl font-medium">Khoá học này dành cho ai</h2>
            <p className="mt-3 text-lg text-pretty">{c.mo_ta}</p>
            <dl className="mt-6 grid gap-4 sm:grid-cols-2">
              {c.doi_tuong && (
                <div className="rounded-2xl bg-surface p-5 shadow-card">
                  <dt className="flex items-center gap-2 font-semibold"><Users className="size-4 text-accent-fg" aria-hidden />Phù hợp với</dt>
                  <dd className="mt-2 text-fg-secondary text-pretty">{c.doi_tuong}</dd>
                </div>
              )}
              {c.ket_qua && (
                <div className="rounded-2xl bg-surface p-5 shadow-card">
                  <dt className="flex items-center gap-2 font-semibold"><Check className="size-4 text-success-fg" aria-hidden />Sau khoá học</dt>
                  <dd className="mt-2 text-fg-secondary text-pretty">{c.ket_qua}</dd>
                </div>
              )}
            </dl>
          </section>

          {c.lo_trinh.length > 0 && (
            <section className="mt-12" aria-labelledby="lo-trinh">
              <h2 id="lo-trinh" className="font-display text-2xl font-medium">Lộ trình học</h2>
              <ol className="mt-5 flex flex-col">
                {c.lo_trinh.map((p, i) => (
                  <li key={p.ten} className="relative flex gap-4 pb-6 last:pb-0">
                    {i < c.lo_trinh.length - 1 && <span className="absolute start-[1.125rem] top-10 bottom-0 w-px bg-line-strong" aria-hidden />}
                    <span className="num grid size-9 shrink-0 place-items-center rounded-full bg-fg font-semibold text-surface">{i + 1}</span>
                    <div className="pt-1.5">
                      <p className="font-semibold">{p.ten}</p>
                      {p.noi_dung && <p className="mt-1 text-fg-secondary text-pretty">{p.noi_dung}</p>}
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          )}

          <section className="mt-12" aria-labelledby="lop">
            <h2 id="lop" className="font-display text-2xl font-medium">Lớp sắp khai giảng</h2>
            {c.lop_sap_mo.length === 0 ? (
              <p className="mt-3 text-fg-secondary">Trung tâm đang xếp lịch lớp mới. Đăng ký tư vấn để được báo khi có lịch.</p>
            ) : (
              <ul className="mt-5 grid gap-3">
                {c.lop_sap_mo.map((l) => (
                  <li key={l.id} className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-2xl bg-surface p-4 shadow-card">
                    <span className="flex min-w-40 items-center gap-2 font-semibold">
                      <CalendarDays className="size-4 text-fg-tertiary" aria-hidden />
                      <span>
                        <span className="num">{dateVN(l.ngay_khai_giang)}</span>
                        <span className="block text-xs font-normal text-fg-tertiary first-letter:uppercase">{weekdayVN(l.ngay_khai_giang)}</span>
                      </span>
                    </span>
                    <span className="flex items-center gap-2 text-fg-secondary">
                      <Clock className="size-4" aria-hidden />
                      {SHIFT_LABEL[l.ca_hoc]} {SHIFT_TIME[l.ca_hoc]} · {l.lich_hoc}
                    </span>
                    <span className="flex items-center gap-2 text-fg-secondary">
                      {l.hinh_thuc === "online" ? <Monitor className="size-4" aria-hidden /> : <MapPin className="size-4" aria-hidden />}
                      {l.hinh_thuc === "online" ? "Online qua Zoom" : (l.co_so ?? "Tại trung tâm")}
                    </span>
                    {l.giang_vien && <span className="text-fg-secondary">{l.giang_vien}</span>}
                    <span className={l.cho_trong <= 3 ? "ms-auto rounded-full bg-warning-subtle px-2.5 py-1 text-xs font-medium text-warning-fg" : "ms-auto text-xs text-fg-tertiary"}>
                      {l.cho_trong > 0 ? `Còn ${l.cho_trong} chỗ` : "Đã đủ chỗ"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {c.giang_vien.length > 0 && (
            <section className="mt-12" aria-labelledby="giang-vien">
              <h2 id="giang-vien" className="font-display text-2xl font-medium">Giảng viên</h2>
              <ul className="mt-5 grid gap-4 sm:grid-cols-2">
                {c.giang_vien.map((g) => (
                  <li key={g.ho_ten} className="rounded-2xl bg-surface p-5 shadow-card">
                    <p className="font-semibold">{g.ho_ten}</p>
                    <p className="text-xs text-fg-tertiary">{g.chuyen_mon}</p>
                    {g.tieu_su && <p className="mt-2 text-fg-secondary text-pretty">{g.tieu_su}</p>}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        <aside className="lg:sticky lg:top-24 lg:self-start" aria-labelledby="dang-ky-khoa">
          <div className="rounded-2xl bg-surface p-5 shadow-lift">
            <p className="num font-display text-3xl font-medium">{vndFull(c.hoc_phi)}</p>
            <p className="text-fg-secondary">Trọn khoá {c.so_buoi} buổi, gồm giáo trình</p>
            {c.tra_gop && (
              <p className="mt-3 flex gap-2 rounded-lg bg-brand-subtle px-3 py-2 text-[0.8125rem] text-pretty">
                <Wallet className="mt-0.5 size-4 shrink-0" aria-hidden />
                Chia 2 đợt: 50% khi đăng ký, 50% trước buổi 10. Không mất phí.
              </p>
            )}
            <h2 id="dang-ky-khoa" className="mt-5 font-semibold">Đăng ký tư vấn &amp; học thử</h2>
            <div className="mt-3">
              <LeadForm courses={[{ slug: c.slug, ten: c.ten }]} defaultSlug={c.slug} compact />
            </div>
          </div>
          <p className="mt-3 px-1 text-xs text-fg-tertiary">
            Ưu đãi và hoàn phí theo <Link href="/chinh-sach/hoc-phi-va-uu-dai" className="underline">chính sách học phí</Link>.
          </p>
        </aside>
      </div>

      {c.lien_quan.length > 0 && (
        <section className="mx-auto max-w-6xl px-4 pt-16 sm:px-6" aria-labelledby="lien-quan">
          <h2 id="lien-quan" className="font-display text-2xl font-medium">Khoá học cùng lĩnh vực</h2>
          <ul className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {c.lien_quan.map((x) => (
              <li key={x.slug}><CourseCard c={x} /></li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
