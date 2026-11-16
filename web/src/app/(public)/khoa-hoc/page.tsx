import type { Metadata } from "next";
import Link from "next/link";
import { CATEGORY, CourseCard } from "@/components/public/course-visual";
import { type PublicCourse, pub } from "@/lib/public-api";

export const dynamic = "force-dynamic";

const LEVELS = ["Cơ bản", "Trung cấp", "Nâng cao"];

export async function generateMetadata({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }): Promise<Metadata> {
  const { danh_muc } = await searchParams;
  return {
    title: danh_muc && CATEGORY[danh_muc] ? `Khoá học ${danh_muc}` : "Tất cả khoá học",
    description: danh_muc && CATEGORY[danh_muc] ? `Khoá học ${danh_muc}: ${CATEGORY[danh_muc].blurb}.` : "Danh sách khoá học Tiếng Anh, Tin học văn phòng, Lập trình, Phân tích dữ liệu và Kỹ năng mềm.",
    alternates: { canonical: danh_muc ? `/khoa-hoc?danh_muc=${encodeURIComponent(danh_muc)}` : "/khoa-hoc" },
  };
}

function chip(active: boolean) {
  return active
    ? "rounded-full bg-fg px-3.5 py-1.5 font-medium text-surface"
    : "rounded-full bg-surface px-3.5 py-1.5 font-medium text-fg-secondary shadow-card hover:text-fg";
}

export default async function CoursesPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const { danh_muc, trinh_do } = await searchParams;
  const all = (await pub<PublicCourse[]>("/public/courses")) ?? [];
  const list = all.filter((c) => (!danh_muc || c.danh_muc === danh_muc) && (!trinh_do || c.trinh_do === trinh_do));
  const href = (dm?: string, td?: string) => {
    const q = new URLSearchParams({ ...(dm && { danh_muc: dm }), ...(td && { trinh_do: td }) }).toString();
    return q ? `/khoa-hoc?${q}` : "/khoa-hoc";
  };

  return (
    <div className="mx-auto max-w-6xl px-4 pt-12 sm:px-6">
      <p className="text-xs font-medium tracking-[0.05em] text-fg-tertiary uppercase">Khoá học</p>
      <h1 className="font-display mt-1 text-4xl font-medium text-balance sm:text-5xl">{danh_muc ?? "Tất cả khoá học"}</h1>
      <p className="mt-3 max-w-2xl text-lg text-fg-secondary text-pretty">
        {danh_muc && CATEGORY[danh_muc] ? CATEGORY[danh_muc].blurb + "." : "Chọn lĩnh vực và trình độ để xem khoá phù hợp. Mỗi khoá đều có lịch sáng, chiều hoặc tối."}
      </p>

      <nav aria-label="Lọc khoá học" className="mt-8 flex flex-col gap-3">
        <ul className="flex flex-wrap gap-2">
          <li>
            <Link href={href(undefined, trinh_do)} className={chip(!danh_muc)} aria-current={!danh_muc ? "page" : undefined}>
              Tất cả lĩnh vực
            </Link>
          </li>
          {Object.keys(CATEGORY).map((c) => (
            <li key={c}>
              <Link href={href(c, trinh_do)} className={chip(danh_muc === c)} aria-current={danh_muc === c ? "page" : undefined}>
                {c}
              </Link>
            </li>
          ))}
        </ul>
        <ul className="flex flex-wrap gap-2 text-[0.8125rem]">
          <li>
            <Link href={href(danh_muc)} className={chip(!trinh_do)}>
              Mọi trình độ
            </Link>
          </li>
          {LEVELS.map((l) => (
            <li key={l}>
              <Link href={href(danh_muc, l)} className={chip(trinh_do === l)}>
                {l}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      {list.length === 0 ? (
        <div className="mt-10 rounded-2xl bg-surface p-10 text-center shadow-card">
          <p className="font-medium">{all.length ? "Chưa có khoá học khớp bộ lọc." : "Không tải được danh sách khoá học. Bạn thử tải lại trang."}</p>
          <Link href="/khoa-hoc" className="mt-3 inline-block font-medium text-accent-fg hover:underline">
            Xem tất cả khoá học
          </Link>
        </div>
      ) : (
        <>
          <p className="mt-8 text-fg-secondary">{list.length} khoá học</p>
          <ul className="mt-3 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {list.map((c) => (
              <li key={c.slug}>
                <CourseCard c={c} headingLevel={2} />
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
