import { Clock, Mail, MapPin, Phone } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { type Center, pub } from "@/lib/public-api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Về trung tâm",
  description: "Giới thiệu Trung tâm Đào tạo Ánh Dương: đội ngũ giảng viên, các cơ sở, giờ làm việc và thông tin liên hệ.",
  alternates: { canonical: "/gioi-thieu" },
};

function initials(name: string) {
  const parts = name.replace(/^(ThS\.|TS\.|Cô|Thầy)\s+/u, "").split(/\s+/);
  return (parts[0][0] + (parts.at(-1)?.[0] ?? "")).toUpperCase();
}

export default async function AboutPage() {
  const center = await pub<Center>("/public/center");
  return (
    <div className="mx-auto max-w-6xl px-4 pt-12 sm:px-6">
      <h1 className="font-display text-4xl font-medium text-balance sm:text-5xl">Về Trung tâm Đào tạo Ánh Dương</h1>
      <p className="mt-4 max-w-3xl text-lg text-fg-secondary text-pretty">
        Ánh Dương dạy ngoại ngữ, tin học văn phòng, lập trình, phân tích dữ liệu và kỹ năng mềm cho học sinh, sinh viên và người đi làm.
        Mỗi khoá có lộ trình rõ ràng, lớp nhỏ và lịch học sáng, chiều, tối để bạn sắp xếp được việc học.
      </p>

      {center && (
        <dl className="mt-10 grid gap-3 sm:grid-cols-4">
          {[
            [center.so_khoa, "khoá học"],
            [center.so_giang_vien, "giảng viên"],
            [center.so_lop, "lớp đã mở"],
            [center.so_hoc_vien, "học viên"],
          ].map(([n, l]) => (
            <div key={l} className="rounded-2xl bg-surface p-5 shadow-card">
              <dt className="sr-only">{l}</dt>
              <dd>
                <span className="num font-display block text-4xl font-medium">{Number(n).toLocaleString("vi-VN")}</span>
                <span className="text-fg-secondary">{l}</span>
              </dd>
            </div>
          ))}
        </dl>
      )}

      {center && center.giang_vien.length > 0 && (
        <section className="mt-16" aria-labelledby="doi-ngu">
          <h2 id="doi-ngu" className="font-display text-3xl font-medium">Đội ngũ giảng viên</h2>
          <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {center.giang_vien.map((g) => (
              <li key={g.ho_ten} className="flex gap-4 rounded-2xl bg-surface p-5 shadow-card">
                <span className="grid size-12 shrink-0 place-items-center rounded-full bg-brand font-semibold text-fg" aria-hidden>
                  {initials(g.ho_ten)}
                </span>
                <div className="min-w-0">
                  <p className="font-semibold">{g.ho_ten}</p>
                  <p className="text-xs text-fg-tertiary">{g.chuyen_mon}</p>
                  {g.tieu_su && <p className="mt-2 text-fg-secondary text-pretty">{g.tieu_su}</p>}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="mt-16 grid gap-6 lg:grid-cols-2" aria-labelledby="lien-he">
        <div>
          <h2 id="lien-he" className="font-display text-3xl font-medium">Cơ sở &amp; liên hệ</h2>
          <ul className="mt-6 flex flex-col gap-3">
            {(center?.co_so ?? []).map((c) => (
              <li key={c.ten} className="flex gap-3 rounded-2xl bg-surface p-5 shadow-card">
                <MapPin className="mt-0.5 size-5 shrink-0 text-accent-fg" aria-hidden />
                <span>
                  <span className="block font-semibold">{c.ten}</span>
                  <span className="text-fg-secondary">{c.dia_chi}</span>
                </span>
              </li>
            ))}
            <li className="flex gap-3 rounded-2xl bg-surface p-5 shadow-card">
              <MapPin className="mt-0.5 size-5 shrink-0 text-accent-fg" aria-hidden />
              <span>
                <span className="block font-semibold">Lớp trực tuyến</span>
                <span className="text-fg-secondary">Học qua Zoom cho học viên ở tỉnh khác.</span>
              </span>
            </li>
          </ul>
        </div>
        <div className="flex flex-col gap-4 rounded-2xl bg-side p-6 text-side-fg sm:p-8">
          <p className="flex items-center gap-3 text-lg">
            <Phone className="size-5 text-brand" aria-hidden />
            Hotline <a href="tel:19000000" className="num font-semibold hover:underline">1900 0000</a>
          </p>
          <p className="flex items-center gap-3">
            <Mail className="size-5 text-brand" aria-hidden />
            <a href="mailto:tuvan@anhduong.example" className="hover:underline">tuvan@anhduong.example</a>
          </p>
          <p className="flex items-start gap-3">
            <Clock className="mt-0.5 size-5 shrink-0 text-brand" aria-hidden />
            <span>
              Thứ Hai – thứ Bảy: 8h00–21h00
              <span className="block">Chủ nhật: 8h00–17h00</span>
            </span>
          </p>
          <Link
            href="/dang-ky-tu-van"
            className="mt-auto inline-flex h-11 w-fit items-center rounded-xl bg-brand px-5 font-semibold text-fg hover:brightness-95"
          >
            Đăng ký tư vấn
          </Link>
        </div>
      </section>
    </div>
  );
}
