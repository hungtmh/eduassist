"use client";

import { CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Button, Field, Input, Select, Textarea } from "@/components/ui";
import { api } from "@/lib/api";

type Option = { slug: string; ten: string };

/** Form đăng ký tư vấn: tạo khách tiềm năng nguồn website -> agent tuyển sinh tự chấm điểm và soạn tin tư vấn. */
export function LeadForm({ courses, defaultSlug, compact }: { courses: Option[]; defaultSlug?: string; compact?: boolean }) {
  const path = usePathname();
  const [f, setF] = useState({ ho_ten: "", so_dien_thoai: "", email: "", khoa_slug: defaultSlug ?? "", nhu_cau: "", dong_y: false, website: "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setF((v) => ({ ...v, [k]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (f.ho_ten.trim().length < 2) return setErr("Bạn cho trung tâm biết họ tên nhé.");
    if (f.so_dien_thoai.replace(/\D/g, "").length < 10) return setErr("Số điện thoại cần đủ 10 số.");
    if (!f.dong_y) return setErr("Bạn cần đồng ý để trung tâm liên hệ tư vấn.");
    setBusy(true);
    setErr(null);
    try {
      await api("/public/leads", {
        body: { ...f, email: f.email.trim() || null, khoa_slug: f.khoa_slug || null, nhu_cau: f.nhu_cau.trim() || null, trang: path },
      });
      setDone(true);
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Chưa gửi được, bạn thử lại hoặc gọi 1900 0000.");
    } finally {
      setBusy(false);
    }
  }

  if (done)
    return (
      <div role="status" className="flex flex-col items-start gap-3 rounded-2xl bg-success-subtle p-6 text-success-fg">
        <CheckCircle2 className="size-8" aria-hidden />
        <p className="text-lg font-semibold">Trung tâm đã nhận thông tin của bạn</p>
        <p className="text-pretty">
          Tư vấn viên sẽ gọi cho bạn trong giờ làm việc. Nếu cần gấp, gọi hotline{" "}
          <a href="tel:19000000" className="num font-semibold underline">1900 0000</a>.
        </p>
      </div>
    );

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      <div className={compact ? "grid gap-4" : "grid gap-4 sm:grid-cols-2"}>
        <Field label="Họ và tên">
          {(p) => <Input {...p} name="name" autoComplete="name" required value={f.ho_ten} onChange={set("ho_ten")} />}
        </Field>
        <Field label="Số điện thoại">
          {(p) => <Input {...p} name="tel" type="tel" inputMode="tel" autoComplete="tel" required value={f.so_dien_thoai} onChange={set("so_dien_thoai")} placeholder="0901 234 567" />}
        </Field>
        <Field label="Email (không bắt buộc)">
          {(p) => <Input {...p} name="email" type="email" autoComplete="email" value={f.email} onChange={set("email")} />}
        </Field>
        <Field label="Khoá học quan tâm">
          {(p) => (
            <Select {...p} value={f.khoa_slug} onChange={set("khoa_slug")}>
              <option value="">Chưa chọn, cần tư vấn</option>
              {courses.map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.ten}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      <Field label="Bạn muốn học để làm gì? Rảnh vào buổi nào?">
        {(p) => <Textarea {...p} value={f.nhu_cau} onChange={set("nhu_cau")} maxLength={1000} placeholder="VD: cần IELTS 6.5 trong 6 tháng, học được tối 2-4-6" />}
      </Field>
      {/* Bẫy bot: ẩn với người dùng và trình đọc màn hình; bot điền vào sẽ bị bỏ qua */}
      <div aria-hidden className="absolute -start-[9999px] size-px overflow-hidden">
        <label>
          Website
          <input tabIndex={-1} autoComplete="off" value={f.website} onChange={set("website")} />
        </label>
      </div>
      <label className="flex items-start gap-2.5 text-fg-secondary">
        <input type="checkbox" checked={f.dong_y} onChange={set("dong_y")} className="mt-1 size-4 shrink-0 accent-accent-solid" />
        <span className="text-pretty">
          Tôi đồng ý để Trung tâm Ánh Dương lưu thông tin trên và liên hệ tư vấn qua điện thoại / email, theo{" "}
          <Link href="/quyen-rieng-tu" className="font-medium text-accent-fg underline">
            chính sách quyền riêng tư
          </Link>
          .
        </span>
      </label>
      {err && (
        <p role="alert" className="rounded-lg bg-danger-subtle px-3 py-2 text-danger-fg">
          {err}
        </p>
      )}
      <Button type="submit" variant="primary" loading={busy} className="h-11 text-base">
        Gửi đăng ký tư vấn
      </Button>
    </form>
  );
}
