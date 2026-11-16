import { CalendarCheck, MessageSquareText, PhoneCall } from "lucide-react";
import type { Metadata } from "next";
import { LeadForm } from "@/components/public/lead-form";
import { type PublicCourse, pub } from "@/lib/public-api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Đăng ký tư vấn",
  description: "Để lại thông tin để được tư vấn lộ trình, kiểm tra đầu vào và học thử miễn phí tại Trung tâm Ánh Dương.",
  alternates: { canonical: "/dang-ky-tu-van" },
};

const STEPS = [
  { icon: PhoneCall, title: "Tư vấn viên gọi lại", text: "Hỏi mục tiêu, trình độ hiện tại và thời gian bạn rảnh." },
  { icon: MessageSquareText, title: "Gợi ý lộ trình", text: "Khoá tiếng Anh có bài kiểm tra đầu vào online miễn phí khoảng 45 phút." },
  { icon: CalendarCheck, title: "Học thử một buổi", text: "Vào lớp đang mở của khoá bạn quan tâm, miễn phí." },
];

export default async function RegisterPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const { khoa } = await searchParams;
  const courses = (await pub<PublicCourse[]>("/public/courses")) ?? [];
  const options = courses.map((c) => ({ slug: c.slug, ten: c.ten }));
  const preset = courses.some((c) => c.slug === khoa) ? khoa : undefined;
  return (
    <div className="mx-auto grid max-w-6xl gap-10 px-4 pt-12 sm:px-6 lg:grid-cols-[1fr_1.3fr]">
      <div>
        <h1 className="font-display text-4xl font-medium text-balance sm:text-5xl">Đăng ký tư vấn miễn phí</h1>
        <p className="mt-3 text-lg text-fg-secondary text-pretty">Không cần biết trước nên học khoá nào. Trung tâm giúp bạn chọn.</p>
        <ol className="mt-8 flex flex-col gap-5">
          {STEPS.map((s, i) => (
            <li key={s.title} className="flex gap-4">
              <span className="grid size-10 shrink-0 place-items-center rounded-full bg-brand text-fg">
                <s.icon className="size-5" aria-hidden />
              </span>
              <span>
                <span className="block font-semibold">
                  {i + 1}. {s.title}
                </span>
                <span className="text-fg-secondary text-pretty">{s.text}</span>
              </span>
            </li>
          ))}
        </ol>
        <p className="mt-8 text-fg-secondary">
          Gọi trực tiếp: <a href="tel:19000000" className="num font-semibold text-fg underline">1900 0000</a>
        </p>
      </div>
      <div className="rounded-3xl bg-surface p-6 shadow-card sm:p-8">
        <LeadForm courses={options} defaultSlug={preset} />
      </div>
    </div>
  );
}
