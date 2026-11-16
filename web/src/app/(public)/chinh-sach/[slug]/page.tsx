import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { type Policy, PublicNotFound, pub } from "@/lib/public-api";

export const dynamic = "force-dynamic";

async function load(slug: string) {
  try {
    return await pub<Policy>(`/public/policies/${encodeURIComponent(slug)}`);
  } catch (e) {
    if (e instanceof PublicNotFound) notFound();
    throw e;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const p = await load((await params).slug);
  return p
    ? { title: p.tieu_de, description: `${p.tieu_de}: ${p.muc.join(", ")}.`, alternates: { canonical: `/chinh-sach/${p.slug}` } }
    : { title: "Chính sách" };
}

const anchor = (s: string) =>
  s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/g, "d")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");

export default async function PolicyPage({ params }: { params: Promise<{ slug: string }> }) {
  const p = await load((await params).slug);
  if (!p) return <p className="mx-auto max-w-4xl px-4 py-20 text-center">Không tải được tài liệu. Bạn thử tải lại trang.</p>;
  return (
    <div className="mx-auto grid max-w-6xl gap-10 px-4 pt-12 sm:px-6 lg:grid-cols-[14rem_1fr]">
      <nav aria-label="Mục trong trang" className="hidden lg:sticky lg:top-24 lg:block lg:self-start">
        <Link href="/chinh-sach" className="text-[0.8125rem] font-medium text-accent-fg hover:underline">← Tất cả chính sách</Link>
        <ul className="mt-4 flex flex-col gap-2 border-s border-line ps-4 text-[0.8125rem]">
          {p.muc.map((m) => (
            <li key={m}><a href={`#${anchor(m)}`} className="text-fg-secondary hover:text-fg">{m}</a></li>
          ))}
        </ul>
      </nav>
      <article>
        <Link href="/chinh-sach" className="text-[0.8125rem] font-medium text-accent-fg hover:underline lg:hidden">← Tất cả chính sách</Link>
        <h1 className="font-display mt-2 text-4xl font-medium text-balance lg:mt-0">{p.tieu_de}</h1>
        <div className="prose-doc mt-6">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{ h2: ({ children }) => <h2 id={anchor(String(children))}>{children}</h2> }}
          >
            {p.noi_dung}
          </ReactMarkdown>
        </div>
        <p className="mt-10 rounded-2xl bg-brand-subtle p-5 text-pretty">
          Còn thắc mắc? Gọi <a href="tel:19000000" className="num font-semibold underline">1900 0000</a> hoặc{" "}
          <Link href="/dang-ky-tu-van" className="font-semibold underline">để lại thông tin</Link> để tư vấn viên giải thích cho trường hợp của bạn.
        </p>
      </article>
    </div>
  );
}
