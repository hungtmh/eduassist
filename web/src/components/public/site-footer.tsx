import { MapPin, Phone } from "lucide-react";
import Link from "next/link";
import { SunMark } from "@/components/ui";
import type { Center } from "@/lib/public-api";
import { CATEGORY } from "./course-visual";

export function SiteFooter({ center }: { center: Center | null }) {
  return (
    <footer className="mt-24 bg-side text-side-fg">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
        <div>
          <div className="flex items-center gap-2.5">
            <SunMark className="size-9" />
            <span className="font-display text-lg font-semibold">Trung tâm Đào tạo Ánh Dương</span>
          </div>
          <p className="mt-3 max-w-sm text-side-fg-secondary text-pretty">
            Khoá học ngoại ngữ, tin học, lập trình, dữ liệu và kỹ năng cho học sinh, sinh viên và người đi làm.
          </p>
          <p className="mt-4 inline-flex items-center gap-2 font-medium">
            <Phone className="size-4 text-brand" aria-hidden />
            Hotline <a href="tel:19000000" className="num hover:underline">1900 0000</a>
          </p>
        </div>
        <div>
          <h2 className="text-xs font-medium tracking-[0.05em] text-side-fg-secondary uppercase">Khoá học</h2>
          <ul className="mt-3 flex flex-col gap-2">
            {Object.keys(CATEGORY).map((c) => (
              <li key={c}>
                <Link href={`/khoa-hoc?danh_muc=${encodeURIComponent(c)}`} className="hover:underline">
                  {c}
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h2 className="text-xs font-medium tracking-[0.05em] text-side-fg-secondary uppercase">Thông tin</h2>
          <ul className="mt-3 flex flex-col gap-2">
            <li><Link href="/lich-khai-giang" className="hover:underline">Lịch khai giảng</Link></li>
            <li><Link href="/gioi-thieu" className="hover:underline">Về trung tâm</Link></li>
            <li><Link href="/chinh-sach" className="hover:underline">Chính sách học phí, hoàn phí</Link></li>
            <li><Link href="/quyen-rieng-tu" className="hover:underline">Quyền riêng tư</Link></li>
            <li><Link href="/dieu-khoan" className="hover:underline">Điều khoản sử dụng</Link></li>
            <li><Link href="/login" className="hover:underline">Cổng học viên</Link></li>
          </ul>
        </div>
        <div>
          <h2 className="text-xs font-medium tracking-[0.05em] text-side-fg-secondary uppercase">Cơ sở</h2>
          <ul className="mt-3 flex flex-col gap-3">
            {(center?.co_so ?? []).map((c) => (
              <li key={c.ten} className="flex gap-2">
                <MapPin className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />
                <span>
                  <span className="block font-medium">{c.ten}</span>
                  <span className="block text-side-fg-secondary">{c.dia_chi}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="border-t border-white/10">
        <p className="mx-auto max-w-6xl px-4 py-5 text-xs text-side-fg-secondary sm:px-6">
          © {new Date().getFullYear()} Trung tâm Đào tạo Ánh Dương · Dự án demo EduAssist: trung tâm, địa chỉ, giảng viên và số liên hệ là hư cấu.
        </p>
      </div>
    </footer>
  );
}
