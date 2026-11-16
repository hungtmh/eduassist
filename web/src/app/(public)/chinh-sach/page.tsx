import { ArrowRight, FileText } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { type PolicyInfo, pub } from "@/lib/public-api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Chính sách",
  description: "Chính sách học phí, ưu đãi, trả góp, bảo lưu, chuyển lớp, hoàn tiền và quy chế học viên của Trung tâm Ánh Dương.",
  alternates: { canonical: "/chinh-sach" },
};

export default async function PoliciesPage() {
  const list = (await pub<PolicyInfo[]>("/public/policies")) ?? [];
  return (
    <div className="mx-auto max-w-4xl px-4 pt-12 sm:px-6">
      <h1 className="font-display text-4xl font-medium text-balance sm:text-5xl">Chính sách của trung tâm</h1>
      <p className="mt-3 text-lg text-fg-secondary text-pretty">
        Học phí, ưu đãi, trả góp, bảo lưu, hoàn tiền và quy chế học tập. Trợ lý tư vấn trên web cũng trả lời dựa trên đúng các tài liệu này.
      </p>
      <ul className="mt-10 flex flex-col gap-3">
        {list.map((p) => (
          <li key={p.slug}>
            <Link href={`/chinh-sach/${p.slug}`} className="group flex gap-4 rounded-2xl bg-surface p-5 shadow-card hover:shadow-lift">
              <FileText className="mt-0.5 size-5 shrink-0 text-accent-fg" aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block text-lg font-semibold">{p.tieu_de}</span>
                <span className="mt-1 block text-fg-secondary">{p.muc.join(" · ")}</span>
              </span>
              <ArrowRight className="mt-1 size-4 shrink-0 text-fg-tertiary transition-transform group-hover:translate-x-0.5" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
