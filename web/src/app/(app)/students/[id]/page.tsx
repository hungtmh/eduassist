"use client";

import { ArrowLeft, MoreHorizontal } from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import useSWR from "swr";
import { EnrollDialog } from "@/components/enroll-dialog";
import { useAuth } from "@/components/providers";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Dialog,
  EmptyState,
  ErrorBox,
  Field,
  Input,
  PageHeader,
  Select,
  Spinner,
  StatusBadge,
  Table,
  td,
  th,
  useToast,
} from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, fmtDateTime, vnd } from "@/lib/format";
import { ENROLL_STATUS, INVOICE_STATUS, REQUEST_KIND, REQUEST_STATUS, SHIFT } from "@/lib/labels";

type Enr = {
  don_hang_id: number;
  lop_hoc_id: number;
  ma_lop: string;
  khoa_hoc: string;
  ngay_khai_giang: string;
  ca_hoc: string;
  lich_hoc: string;
  trang_thai: string;
  trang_thai_hoc: string;
  thanh_tien: number;
  con_no: number;
  so_buoi_diem_danh: number;
  so_buoi_vang: number;
  diem_cuoi_khoa: number | null;
};
type Student = {
  id: number;
  ho_ten: string;
  email: string;
  so_dien_thoai: string;
  nam_sinh: number;
  thanh_pho: string;
  ghi_danh: Enr[];
  yeu_cau: { id: number; loai: string; trang_thai: string; noi_dung: string; created_at: string }[];
  voucher: { ma: string; phan_tram: number; ly_do: string; han_su_dung: string }[];
  email_da_gui?: { subject: string; sent_by: string; sent_at: string }[];
};

type Action = { kind: "transfer" | "reserve" | "cancel"; enr: Enr } | null;

function StudentDetail() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const { can, user } = useAuth();
  const toast = useToast();
  const { data: s, error, mutate } = useSWR<Student>(`/students/${id}`);
  const [enroll, setEnroll] = useState(false);
  const [action, setAction] = useState<Action>(null);
  const [voucher, setVoucher] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const { data: siblings } = useSWR<{ id: number; ma_lop: string; si_so: number; si_so_toi_da: number; trang_thai: string; khoa_hoc: string; lich_hoc: string; ca_hoc: string }[]>(
    action?.kind === "transfer" ? `/classes` : null,
  );

  useEffect(() => {
    if (params.get("enroll")) setEnroll(true);
  }, [params]);

  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!s) return <Spinner />;

  async function submit(path: string, body: unknown, ok: string) {
    setBusy(true);
    try {
      await api(path, { body });
      toast(ok);
      setAction(null);
      setVoucher(false);
      setForm({});
      mutate();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Không thực hiện được.", "danger");
    } finally {
      setBusy(false);
    }
  }

  const sameCourse = action?.kind === "transfer"
    ? siblings?.filter(
        (c) =>
          c.id !== action.enr.lop_hoc_id &&
          c.khoa_hoc === action.enr.khoa_hoc &&
          (c.trang_thai === "sap_khai_giang" || c.trang_thai === "dang_hoc"),
      )
    : [];
  const maxVoucher = user?.role === "manager" ? 30 : 15;

  return (
    <>
      <PageHeader
        back={
          <Link href="/students" className="mb-2 inline-flex items-center gap-1 text-[0.8125rem] text-fg-secondary hover:text-fg">
            <ArrowLeft className="size-3.5" aria-hidden />
            Học viên
          </Link>
        }
        title={s.ho_ten}
        description={
          <span className="num">
            #{s.id} · {s.email} · {s.so_dien_thoai} · sinh năm {s.nam_sinh} · {s.thanh_pho}
          </span>
        }
        actions={
          <>
            {can("voucher.issue") && <Button onClick={() => setVoucher(true)}>Cấp voucher</Button>}
            {can("enroll.create") && (
              <Button variant="primary" onClick={() => setEnroll(true)}>
                Ghi danh vào lớp
              </Button>
            )}
          </>
        }
      />

      <Card>
        <CardHeader title="Ghi danh" />
        {s.ghi_danh.length === 0 ? (
          <EmptyState title="Chưa ghi danh lớp nào" />
        ) : (
          <Table label="Các lớp đã ghi danh">
            <thead>
              <tr>
                <th className={th}>Lớp</th>
                <th className={th}>Học</th>
                <th className={th}>Thanh toán</th>
                <th className={`${th} text-end`}>Chuyên cần</th>
                <th className={`${th} text-end`}>Còn nợ</th>
                <th className={th}>
                  <span className="sr-only">Thao tác</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {s.ghi_danh.map((g) => {
                const active = ["dang_hoc", "cho_thanh_toan", "bao_luu"].includes(g.trang_thai_hoc);
                return (
                  <tr key={g.don_hang_id} className="hover:bg-surface-hover">
                    <td className={td}>
                      <Link href={`/classes/${g.lop_hoc_id}`} className="font-medium hover:underline">
                        {g.ma_lop}
                      </Link>
                      <p className="text-fg-tertiary">
                        {g.khoa_hoc} · {SHIFT[g.ca_hoc]} {g.lich_hoc}
                      </p>
                    </td>
                    <td className={td}>
                      <StatusBadge map={ENROLL_STATUS} value={g.trang_thai_hoc} />
                    </td>
                    <td className={td}>
                      {can("invoice.read") ? (
                        <Link href={`/finance?id=${g.don_hang_id}`} className="hover:underline">
                          <StatusBadge map={INVOICE_STATUS} value={g.trang_thai} />
                        </Link>
                      ) : (
                        <StatusBadge map={INVOICE_STATUS} value={g.trang_thai} />
                      )}
                    </td>
                    <td className={`${td} num text-end`}>
                      {g.so_buoi_diem_danh ? `${Math.round((1 - g.so_buoi_vang / g.so_buoi_diem_danh) * 100)}%` : "–"}
                    </td>
                    <td className={`${td} num text-end`}>{vnd(g.con_no)}</td>
                    <td className={`${td} text-end`}>
                      {can("enroll.change") && active && (
                        <details className="relative inline-block text-start">
                          <summary className="inline-flex size-8 cursor-pointer list-none items-center justify-center rounded-lg hover:bg-surface-hover" aria-label={`Thao tác với lớp ${g.ma_lop}`}>
                            <MoreHorizontal className="size-4" aria-hidden />
                          </summary>
                          <div className="absolute end-0 z-20 mt-1 flex w-48 flex-col rounded-xl bg-surface p-1 shadow-pop">
                            {[
                              ["transfer", "Chuyển lớp"],
                              ["reserve", "Bảo lưu"],
                              ["cancel", "Huỷ ghi danh"],
                            ].map(([k, l]) => (
                              <button key={k} className="rounded-lg px-3 py-2 text-start hover:bg-surface-hover" onClick={() => setAction({ kind: k as "transfer", enr: g })}>
                                {l}
                              </button>
                            ))}
                          </div>
                        </details>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        )}
      </Card>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title="Yêu cầu đã gửi" />
          <ul className="px-4 pb-4">
            {s.yeu_cau.length === 0 && <li className="text-fg-secondary">Chưa có yêu cầu.</li>}
            {s.yeu_cau.map((y) => (
              <li key={y.id} className="border-b border-line py-2 last:border-0">
                <p className="flex flex-wrap items-center gap-2 font-medium">
                  {REQUEST_KIND[y.loai]} <StatusBadge map={REQUEST_STATUS} value={y.trang_thai} />
                </p>
                <p className="line-clamp-2 text-fg-secondary">{y.noi_dung}</p>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <CardHeader title="Voucher" />
          <ul className="px-4 pb-4">
            {s.voucher.length === 0 && <li className="text-fg-secondary">Chưa có voucher.</li>}
            {s.voucher.map((v) => (
              <li key={v.ma} className="flex items-center justify-between gap-2 border-b border-line py-2 last:border-0">
                <span>
                  <span className="font-medium">{v.ma}</span> <Badge tone="accent">{v.phan_tram}%</Badge>
                  <span className="block text-fg-tertiary">{v.ly_do}</span>
                </span>
                <span className="num text-fg-secondary">đến {fmtDate(v.han_su_dung)}</span>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <CardHeader title="Email đã gửi" />
          <ul className="px-4 pb-4">
            {!s.email_da_gui?.length && <li className="text-fg-secondary">Chưa gửi email nào.</li>}
            {s.email_da_gui?.map((e, i) => (
              <li key={i} className="border-b border-line py-2 last:border-0">
                <p className="text-pretty">{e.subject}</p>
                <p className="text-xs text-fg-tertiary">
                  {e.sent_by.startsWith("agent:") ? `agent ${e.sent_by.slice(6)}` : e.sent_by} · {fmtDateTime(e.sent_at)}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <EnrollDialog
        open={enroll}
        onClose={() => setEnroll(false)}
        onDone={() => mutate()}
        studentId={s.id}
        leadId={params.get("lead") ? Number(params.get("lead")) : undefined}
      />

      <Dialog
        open={action?.kind === "transfer"}
        onClose={() => setAction(null)}
        title={`Chuyển ${s.ho_ten} khỏi lớp ${action?.enr.ma_lop ?? ""}`}
        description="Miễn phí 1 lần, chỉ sang lớp cùng khoá còn chỗ."
        footer={
          <>
            <Button variant="ghost" onClick={() => setAction(null)}>
              Huỷ
            </Button>
            <Button variant="primary" loading={busy} disabled={!form.lop}
              onClick={() => submit(`/enrollments/${action!.enr.don_hang_id}/transfer`, { lop_moi_id: Number(form.lop), ly_do: form.ly_do ?? "" }, "Đã chuyển lớp.")}>
              Chuyển lớp
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Field label="Lớp mới" hint="Hệ thống từ chối nếu khác khoá hoặc hết chỗ">
            {(p) => (
              <Select {...p} value={form.lop ?? ""} onChange={(e) => setForm({ ...form, lop: e.target.value })}>
                <option value="">Chọn lớp</option>
                {sameCourse?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.ma_lop} · {SHIFT[c.ca_hoc]} {c.lich_hoc} · {c.si_so}/{c.si_so_toi_da}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Lý do">{(p) => <Input {...p} value={form.ly_do ?? ""} onChange={(e) => setForm({ ...form, ly_do: e.target.value })} placeholder="Đổi sang ca tối" />}</Field>
        </div>
      </Dialog>

      <Dialog
        open={action?.kind === "reserve"}
        onClose={() => setAction(null)}
        title={`Bảo lưu lớp ${action?.enr.ma_lop ?? ""}`}
        description="Tối đa 1 lần, tối đa 6 tháng, phí 300.000đ (miễn nếu có giấy xác nhận y tế)."
        footer={
          <>
            <Button variant="ghost" onClick={() => setAction(null)}>
              Huỷ
            </Button>
            <Button variant="primary" loading={busy} disabled={(form.ly_do ?? "").length < 3}
              onClick={() => submit(`/enrollments/${action!.enr.don_hang_id}/reserve`, { so_thang: Number(form.thang ?? 3), ly_do: form.ly_do, mien_phi: form.y_te === "1" }, "Đã bảo lưu.")}>
              Bảo lưu
            </Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Số tháng">
            {(p) => (
              <Select {...p} value={form.thang ?? "3"} onChange={(e) => setForm({ ...form, thang: e.target.value })}>
                {[1, 2, 3, 4, 5, 6].map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Lý do">{(p) => <Input {...p} value={form.ly_do ?? ""} onChange={(e) => setForm({ ...form, ly_do: e.target.value })} placeholder="Đi công tác 2 tháng" />}</Field>
          <label className="flex items-center gap-3 sm:col-span-2">
            <input type="checkbox" className="size-4 accent-[var(--color-accent-solid)]" checked={form.y_te === "1"} onChange={(e) => setForm({ ...form, y_te: e.target.checked ? "1" : "0" })} />
            Có giấy xác nhận y tế (miễn phí bảo lưu)
          </label>
        </div>
      </Dialog>

      <Dialog
        open={action?.kind === "cancel"}
        onClose={() => setAction(null)}
        title={`Huỷ ghi danh lớp ${action?.enr.ma_lop ?? ""}?`}
        description="Tỉ lệ hoàn phí do hệ thống tính theo thời điểm huỷ (100% nếu trước khai giảng 7 ngày, 70% trước buổi 3, sau đó không hoàn). Khoản hoàn cần kế toán duyệt. Không khôi phục được ghi danh."
        footer={
          <>
            <Button variant="ghost" onClick={() => setAction(null)}>
              Giữ ghi danh
            </Button>
            <Button variant="danger" loading={busy} disabled={(form.ly_do ?? "").length < 3}
              onClick={() => submit(`/enrollments/${action!.enr.don_hang_id}/cancel`, { ly_do: form.ly_do }, "Đã huỷ ghi danh và lập yêu cầu hoàn phí.")}>
              Huỷ ghi danh
            </Button>
          </>
        }
      >
        <Field label="Lý do">{(p) => <Input {...p} value={form.ly_do ?? ""} onChange={(e) => setForm({ ...form, ly_do: e.target.value })} placeholder="Học viên chuyển công tác" />}</Field>
      </Dialog>

      <Dialog
        open={voucher}
        onClose={() => setVoucher(false)}
        title={`Cấp voucher cho ${s.ho_ten}`}
        description={`Vai trò của bạn được cấp tối đa ${maxVoucher}%.`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setVoucher(false)}>
              Huỷ
            </Button>
            <Button variant="primary" loading={busy} disabled={!form.pct || (form.ly_do ?? "").length < 3}
              onClick={() => submit("/vouchers", { hoc_vien_id: s.id, phan_tram: Number(form.pct), ly_do: form.ly_do, so_ngay: Number(form.ngay ?? 30) }, "Đã cấp voucher.")}>
              Cấp voucher
            </Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Mức giảm (%)">{(p) => <Input {...p} inputMode="numeric" value={form.pct ?? ""} onChange={(e) => setForm({ ...form, pct: e.target.value })} placeholder="10" />}</Field>
          <Field label="Hiệu lực (ngày)">{(p) => <Input {...p} inputMode="numeric" value={form.ngay ?? "30"} onChange={(e) => setForm({ ...form, ngay: e.target.value })} />}</Field>
          <Field label="Lý do" className="sm:col-span-2">{(p) => <Input {...p} value={form.ly_do ?? ""} onChange={(e) => setForm({ ...form, ly_do: e.target.value })} placeholder="Học viên giới thiệu bạn bè" />}</Field>
        </div>
      </Dialog>
    </>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<Spinner />}>
      <StudentDetail />
    </Suspense>
  );
}
