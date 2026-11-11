"use client";

import { Plus, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { useAuth } from "@/components/providers";
import {
  Badge,
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorBox,
  Field,
  Input,
  PageHeader,
  Segmented,
  Select,
  Spinner,
  StatusBadge,
  Table,
  Textarea,
  td,
  th,
  useToast,
} from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { LEAD_STATUS, SOURCE } from "@/lib/labels";

export type Lead = {
  id: number;
  ho_ten: string;
  so_dien_thoai: string;
  email: string | null;
  nguon: string;
  nhu_cau: string;
  khoa_quan_tam: string | null;
  trang_thai: string;
  phu_trach: string | null;
  ten_phu_trach: string | null;
  diem: number | null;
  so_ngay: number;
  lien_he_cuoi: string | null;
  created_at: string;
};

type Course = { id: number; ten: string };

function NewLeadDialog({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const { data: courses } = useSWR<Course[]>(open ? "/courses" : null);
  const toast = useToast();
  const [f, setF] = useState({ ho_ten: "", so_dien_thoai: "", email: "", nguon: "website", nhu_cau: "", khoa_quan_tam_id: "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api("/leads", {
        body: { ...f, email: f.email || null, khoa_quan_tam_id: f.khoa_quan_tam_id ? Number(f.khoa_quan_tam_id) : null },
      });
      toast(`Đã thêm khách ${f.ho_ten}. Agent tuyển sinh sẽ chấm điểm và gợi ý lớp.`);
      setF({ ho_ten: "", so_dien_thoai: "", email: "", nguon: "website", nhu_cau: "", khoa_quan_tam_id: "" });
      onCreated();
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Không thêm được khách.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog open={open} onClose={onClose} title="Thêm khách tiềm năng" description="Khách được tự phân cho tư vấn viên đang ít khách nhất nếu bạn không phải tư vấn viên.">
      <form id="new-lead" onSubmit={submit} className="grid gap-4 sm:grid-cols-2" noValidate>
        <Field label="Họ tên" className="sm:col-span-2">
          {(p) => <Input {...p} required autoComplete="off" value={f.ho_ten} onChange={set("ho_ten")} placeholder="Nguyễn Thị Lan" />}
        </Field>
        <Field label="Số điện thoại">
          {(p) => <Input {...p} type="tel" inputMode="tel" required value={f.so_dien_thoai} onChange={set("so_dien_thoai")} placeholder="0901234567" />}
        </Field>
        <Field label="Email" hint="Cần có để agent gửi tin tư vấn">
          {(p) => <Input {...p} type="email" value={f.email} onChange={set("email")} placeholder="lan@example.com" />}
        </Field>
        <Field label="Nguồn">
          {(p) => (
            <Select {...p} value={f.nguon} onChange={set("nguon")}>
              {Object.entries(SOURCE).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Khoá quan tâm">
          {(p) => (
            <Select {...p} value={f.khoa_quan_tam_id} onChange={set("khoa_quan_tam_id")}>
              <option value="">Chưa rõ</option>
              {courses?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.ten}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Nhu cầu" className="sm:col-span-2" hint="Càng cụ thể, agent gợi ý lớp càng đúng">
          {(p) => <Textarea {...p} rows={3} value={f.nhu_cau} onChange={set("nhu_cau")} placeholder="Muốn học IELTS buổi tối, hiện khoảng 5.0" />}
        </Field>
        {err && (
          <p role="alert" className="rounded-lg bg-danger-subtle px-3 py-2 text-danger-fg sm:col-span-2">
            {err}
          </p>
        )}
      </form>
      <div className="mt-5 flex justify-end gap-3">
        <Button variant="ghost" onClick={onClose}>
          Huỷ
        </Button>
        <Button variant="primary" type="submit" form="new-lead" loading={busy}>
          Thêm khách
        </Button>
      </div>
    </Dialog>
  );
}

export default function LeadsPage() {
  const { can } = useAuth();
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const params = new URLSearchParams({ ...(status ? { trang_thai: status } : {}), ...(q ? { q } : {}) });
  const { data, error, mutate } = useSWR<Lead[]>(`/leads?${params}`);
  const { data: all } = useSWR<Lead[]>("/leads");
  const count = (s: string) => all?.filter((l) => l.trang_thai === s).length;

  return (
    <>
      <PageHeader
        title="Tuyển sinh"
        description="Khách tiềm năng, sắp theo điểm tiềm năng do agent tuyển sinh chấm."
        actions={
          can("lead.write") && (
            <Button variant="primary" onClick={() => setOpen(true)}>
              <Plus className="size-4" aria-hidden />
              Thêm khách
            </Button>
          )
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Segmented
          label="Lọc theo trạng thái"
          value={status}
          onChange={setStatus}
          options={[
            { value: "", label: "Tất cả", count: all?.length },
            ...Object.entries(LEAD_STATUS).map(([k, [v]]) => ({ value: k, label: v, count: count(k) })),
          ]}
        />
        <div className="relative min-w-56 flex-1 sm:max-w-xs">
          <Search className="pointer-events-none absolute start-3 top-2.5 size-4 text-fg-tertiary" aria-hidden />
          <label htmlFor="lead-q" className="sr-only">
            Tìm khách
          </label>
          <Input id="lead-q" type="search" className="ps-9" placeholder="Tên, số điện thoại, email" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      {error && <ErrorBox error={error} onRetry={() => mutate()} />}
      <Card>
        {!data ? (
          <Spinner />
        ) : data.length === 0 ? (
          <EmptyState
            title={q ? `Không có khách khớp “${q}”` : "Chưa có khách nào"}
            action={q ? <Button onClick={() => setQ("")}>Xoá tìm kiếm</Button> : undefined}
          />
        ) : (
          <Table label="Danh sách khách tiềm năng">
            <thead>
              <tr>
                <th className={th}>Khách</th>
                <th className={th}>Trạng thái</th>
                <th className={`${th} text-end`}>Điểm</th>
                <th className={th}>Quan tâm</th>
                <th className={th}>Phụ trách</th>
                <th className={th}>Ngày tạo</th>
              </tr>
            </thead>
            <tbody>
              {data.map((l) => (
                <tr key={l.id} className="hover:bg-surface-hover">
                  <td className={td}>
                    <Link href={`/leads/${l.id}`} className="font-medium hover:underline">
                      {l.ho_ten}
                    </Link>
                    <p className="num text-fg-tertiary">
                      {l.so_dien_thoai} · {SOURCE[l.nguon] ?? l.nguon}
                    </p>
                  </td>
                  <td className={td}>
                    <div className="flex flex-col items-start gap-1">
                      <StatusBadge map={LEAD_STATUS} value={l.trang_thai} />
                      {l.trang_thai === "moi" && !l.lien_he_cuoi && l.so_ngay > 3 && (
                        <Badge tone="danger">Quá {l.so_ngay} ngày chưa liên hệ</Badge>
                      )}
                    </div>
                  </td>
                  <td className={`${td} num text-end font-medium`}>{l.diem ?? "–"}</td>
                  <td className={`${td} max-w-64`}>
                    <p className="line-clamp-2 text-fg-secondary" title={l.nhu_cau}>
                      {l.khoa_quan_tam ?? l.nhu_cau ?? "–"}
                    </p>
                  </td>
                  <td className={td}>{l.ten_phu_trach ?? "Chưa phân"}</td>
                  <td className={`${td} num`}>{fmtDate(l.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
      <NewLeadDialog open={open} onClose={() => setOpen(false)} onCreated={() => mutate()} />
    </>
  );
}
