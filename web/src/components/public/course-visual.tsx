import { BarChart3, Code2, FileSpreadsheet, Languages, Mic } from "lucide-react";
import Link from "next/link";
import type { PublicCourse } from "@/lib/public-api";

// ui.tsx là module client: server component không gọi được hàm trong đó -> cx riêng
const cx = (...c: (string | false | undefined)[]) => c.filter(Boolean).join(" ");

export const CATEGORY: Record<string, { color: string; icon: typeof Languages; slug: string; blurb: string }> = {
  "Tiếng Anh": { color: "var(--cat-eng)", icon: Languages, slug: "tieng-anh", blurb: "IELTS, TOEIC, giao tiếp, luyện thi lớp 10" },
  "Tin học văn phòng": { color: "var(--cat-off)", icon: FileSpreadsheet, slug: "tin-hoc", blurb: "Excel, Word, PowerPoint, chứng chỉ MOS" },
  "Lập trình": { color: "var(--cat-dev)", icon: Code2, slug: "lap-trinh", blurb: "Python, web Front-end, Java, lập trình cho thiếu niên" },
  "Phân tích dữ liệu": { color: "var(--cat-da)", icon: BarChart3, slug: "du-lieu", blurb: "SQL, Power BI, Python, lộ trình Data Analyst" },
  "Kỹ năng mềm": { color: "var(--cat-sk)", icon: Mic, slug: "ky-nang", blurb: "Thuyết trình, phỏng vấn, quản lý thời gian" },
};
const FALLBACK = CATEGORY["Tiếng Anh"];
export const cat = (name: string) => CATEGORY[name] ?? FALLBACK;

const money = new Intl.NumberFormat("vi-VN");
export const vndShort = (n: number) => (n >= 1_000_000 ? `${(n / 1_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} triệu` : `${money.format(n)}đ`);
export const vndFull = (n: number) => `${money.format(n)}đ`;
export const SHIFT_LABEL: Record<string, string> = { sang: "Sáng", chieu: "Chiều", toi: "Tối" };
export const dateVN = (v: string) =>
  new Intl.DateTimeFormat("vi-VN", { day: "numeric", month: "numeric", year: "numeric" }).format(new Date(`${v}T00:00:00`));
export const weekdayVN = (v: string) => new Intl.DateTimeFormat("vi-VN", { weekday: "long" }).format(new Date(`${v}T00:00:00`));

/** Bìa khoá học: vòng nắng đồng tâm trên nền màu danh mục, biểu tượng danh mục. Thuần trang trí. */
export function CourseCover({ danhMuc, className, big }: { danhMuc: string; className?: string; big?: boolean }) {
  const c = cat(danhMuc);
  const Icon = c.icon;
  return (
    <div className={cx("isolate overflow-hidden", className)} style={{ background: c.color }} aria-hidden>
      <svg viewBox="0 0 400 240" className="absolute inset-0 size-full" preserveAspectRatio="xMidYMid slice">
        {[210, 165, 120, 78].map((r, i) => (
          <circle key={r} cx="340" cy="230" r={r} fill="none" stroke="white" strokeOpacity={0.08 + i * 0.05} strokeWidth="1.5" />
        ))}
        <circle cx="340" cy="230" r="44" fill="var(--color-brand)" fillOpacity="0.95" />
        <path d="M0 200 Q 120 170 240 196 T 400 186 V 240 H 0 Z" fill="white" fillOpacity="0.06" />
      </svg>
      {!big && <Icon className="absolute start-5 top-5 size-8 text-white/90" strokeWidth={1.5} />}
    </div>
  );
}

export function CourseCard({ c, headingLevel = 3 }: { c: PublicCourse; headingLevel?: 2 | 3 }) {
  const H = `h${headingLevel}` as "h2" | "h3";
  return (
    <article className="group relative flex h-full flex-col overflow-hidden rounded-2xl bg-surface shadow-card transition-[box-shadow,translate] duration-200 hover:-translate-y-0.5 hover:shadow-lift motion-reduce:hover:translate-y-0">
      <CourseCover danhMuc={c.danh_muc} className="relative h-32" />
      <div className="flex flex-1 flex-col gap-2 p-5">
        <p className="text-xs font-medium tracking-[0.05em] text-fg-tertiary uppercase">
          {c.danh_muc} · {c.trinh_do}
        </p>
        <H className="font-display text-xl leading-snug font-medium text-balance">
          <Link href={`/khoa-hoc/${c.slug}`} className="after:absolute after:inset-0 focus-visible:outline-none">
            {c.ten}
          </Link>
        </H>
        <p className="line-clamp-2 text-fg-secondary text-pretty">{c.mo_ta_ngan}</p>
        <div className="mt-auto flex flex-wrap items-end justify-between gap-2 border-t border-dashed border-line-strong pt-3">
          <div>
            <p className="num text-lg font-semibold">{vndFull(c.hoc_phi)}</p>
            <p className="text-xs text-fg-tertiary">{c.so_buoi} buổi</p>
          </div>
          <p className="text-end text-xs text-fg-secondary">
            {c.khai_giang_gan_nhat ? (
              <>
                Khai giảng gần nhất
                <span className="num block font-medium text-fg">{dateVN(c.khai_giang_gan_nhat)}</span>
              </>
            ) : (
              "Đang xếp lịch lớp mới"
            )}
          </p>
        </div>
      </div>
    </article>
  );
}
