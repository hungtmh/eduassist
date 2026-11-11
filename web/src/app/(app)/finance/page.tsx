"use client";

import { Search } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import useSWR from "swr";
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
  Segmented,
  Select,
  Spinner,
  Stat,
  StatusBadge,
  Table,
  td,
  th,
  useToast,
} from "@/components/ui";
import { api } from "@/lib/api";
import { daysFrom, fmtDate, vnd } from "@/lib/format";
import { ENROLL_STATUS, INSTALLMENT_STATUS, INVOICE_STATUS, PAY_METHOD } from "@/lib/labels";

type Invoice = {
  id: number;
  hoc_vien_id: number;
  ho_ten: string;
  ma_lop: string;
  khoa_hoc: string;
  thanh_tien: number;
  da_dong: number;
  con_no: number;
  trang_thai: string;
  trang_thai_hoc: string;
  tra_gop: boolean;
  han_gan_nhat: string | null;
  so_dot_qua_han: number;
};
type InvoiceDetail = Invoice & {
  hoc_phi_goc: number;
  giam_gia: number;
  dot: { id: number; so_thu_tu: number; so_tien: number; han_thanh_toan: string; trang_thai: string }[];
  thanh_toan: { id: number; ngay_thanh_toan: string; so_tien: number; phuong_thuc: string; ghi_chu: string | null; created_by: string | null }[];
};
type Refund = { id: number; ho_ten: string; ma_lop: string; da_dong: number; ty_le: number; so_tien: number; can_cu: string; created_by: string; trang_thai: string };

function InvoiceDialog({ id, onClose, onChanged }: { id: number | null; onClose: () => void; onChanged: () => void }) {
  const { can } = useAuth();
  const toast = useToast();
  const { data: inv, mutate } = useSWR<InvoiceDetail>(id ? `/invoices/${id}` : null);
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("chuyen_khoan");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function pay() {
    if (!inv) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await api<InvoiceDetail>(`/invoices/${inv.id}/payments`, { body: { so_tien: Number(amount.replace(/\D/g, "")), phuong_thuc: method, ghi_chu: note || null } });
      toast(`Đã ghi nhận ${vnd(Number(amount.replace(/\D/g, "")))} cho ${inv.ho_ten}.`);
      setAmount("");
      setNote("");
      await mutate(r, { revalidate: false });
      onChanged();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Không ghi nhận được.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog open={!!id} onClose={onClose} title={inv ? `Hoá đơn #${inv.id} · ${inv.ho_ten}` : "Hoá đơn"} description={inv ? `${inv.khoa_hoc} · lớp ${inv.ma_lop}` : undefined} wide>
      {!inv ? (
        <Spinner />
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap gap-2">
            <StatusBadge map={INVOICE_STATUS} value={inv.trang_thai} />
            <StatusBadge map={ENROLL_STATUS} value={inv.trang_thai_hoc} />
            {inv.tra_gop && <Badge>Trả góp 2 đợt</Badge>}
          </div>
          <dl className="num grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Học phí", vnd(inv.hoc_phi_goc)],
              ["Giảm", vnd(inv.giam_gia)],
              ["Đã đóng", vnd(inv.da_dong)],
              ["Còn nợ", vnd(inv.con_no)],
            ].map(([k, v]) => (
              <div key={k} className="rounded-lg bg-surface-muted p-3">
                <dt className="text-fg-secondary">{k}</dt>
                <dd className="text-base font-semibold">{v}</dd>
              </div>
            ))}
          </dl>
          <section>
            <h3 className="mb-2 font-medium">Các đợt</h3>
            <ul className="rounded-lg border border-line">
              {inv.dot.map((d) => (
                <li key={d.id} className="num flex flex-wrap items-center gap-3 border-b border-line px-3 py-2 last:border-0">
                  <span className="w-14 text-fg-secondary">Đợt {d.so_thu_tu}</span>
                  <span className="flex-1">Hạn {fmtDate(d.han_thanh_toan)}</span>
                  <span>{vnd(d.so_tien)}</span>
                  <StatusBadge map={INSTALLMENT_STATUS} value={d.trang_thai} />
                </li>
              ))}
            </ul>
          </section>
          {inv.thanh_toan.length > 0 && (
            <section>
              <h3 className="mb-2 font-medium">Lịch sử thu</h3>
              <ul className="num flex flex-col gap-1 text-fg-secondary">
                {inv.thanh_toan.map((t) => (
                  <li key={t.id} className="flex flex-wrap justify-between gap-2">
                    <span>
                      {fmtDate(t.ngay_thanh_toan)} · {PAY_METHOD[t.phuong_thuc]}
                      {t.ghi_chu ? ` · ${t.ghi_chu}` : ""}
                    </span>
                    <span className={t.so_tien < 0 ? "text-danger-fg" : "text-fg"}>{vnd(t.so_tien)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {can("payment.record") && inv.con_no > 0 && inv.trang_thai_hoc !== "da_huy" && (
            <section className="rounded-xl bg-surface-muted p-4">
              <h3 className="font-medium">Ghi nhận thanh toán</h3>
              <p className="mt-0.5 text-fg-secondary">Chỉ con người ghi nhận được việc đã thu tiền; agent bị cấm thao tác này.</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <Field label="Số tiền (đ)" hint={`Tối đa ${vnd(inv.con_no)}`}>
                  {(p) => <Input {...p} inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder={String(inv.dot.find((d) => d.trang_thai !== "da_thanh_toan")?.so_tien ?? inv.con_no)} />}
                </Field>
                <Field label="Phương thức">
                  {(p) => (
                    <Select {...p} value={method} onChange={(e) => setMethod(e.target.value)}>
                      {Object.entries(PAY_METHOD).map(([k, v]) => (
                        <option key={k} value={k}>
                          {v}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
                <Field label="Ghi chú">{(p) => <Input {...p} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Mã giao dịch" />}</Field>
              </div>
              {err && (
                <p role="alert" className="mt-3 rounded-lg bg-danger-subtle px-3 py-2 text-danger-fg">
                  {err}
                </p>
              )}
              <div className="mt-3 flex justify-end">
                <Button variant="primary" loading={busy} disabled={!amount.trim()} onClick={pay}>
                  Ghi nhận thanh toán
                </Button>
              </div>
            </section>
          )}
          <Link href={`/students/${inv.hoc_vien_id}`} className="text-[0.8125rem] font-medium text-accent-fg hover:underline">
            Mở hồ sơ học viên
          </Link>
        </div>
      )}
    </Dialog>
  );
}

function Refunds() {
  const { can } = useAuth();
  const toast = useToast();
  const { data, mutate } = useSWR<Refund[]>("/refunds");
  async function decide(r: Refund, ok: boolean) {
    try {
      await api(`/refunds/${r.id}/decide`, { body: { duyet: ok } });
      toast(ok ? `Đã duyệt hoàn ${vnd(r.so_tien)} cho ${r.ho_ten}.` : "Đã từ chối yêu cầu hoàn phí.");
      mutate();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Không xử lý được.", "danger");
    }
  }
  if (!data?.length) return null;
  return (
    <Card className="mb-4">
      <CardHeader title={`Hoàn phí chờ duyệt (${data.length})`} description="Tỉ lệ hoàn do hệ thống tính theo chính sách. Người lập yêu cầu không tự duyệt được." />
      <ul>
        {data.map((r) => (
          <li key={r.id} className="flex flex-wrap items-start gap-3 border-t border-line px-4 py-3">
            <div className="min-w-0 flex-1">
              <p className="font-medium">
                {r.ho_ten} · lớp {r.ma_lop}
              </p>
              <p className="num text-fg-secondary">
                Đã đóng {vnd(r.da_dong)} · hoàn {r.ty_le}% = <span className="font-medium text-fg">{vnd(r.so_tien)}</span>
              </p>
              <p className="text-xs text-fg-tertiary text-pretty">{r.can_cu}</p>
            </div>
            {can("refund.handle") && (
              <div className="flex gap-2">
                <Button size="sm" variant="ghost" onClick={() => decide(r, false)}>
                  Từ chối
                </Button>
                <Button size="sm" variant="primary" onClick={() => decide(r, true)}>
                  Duyệt hoàn {vnd(r.so_tien)}
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Finance() {
  const params = useSearchParams();
  const router = useRouter();
  const [filter, setFilter] = useState<"con_no" | "qua_han" | "all">("con_no");
  const [q, setQ] = useState("");
  const qs = new URLSearchParams({
    ...(filter === "con_no" ? { trang_thai: "con_no" } : {}),
    ...(filter === "qua_han" ? { qua_han: "true" } : {}),
    ...(q ? { q } : {}),
  });
  const { data, error, mutate } = useSWR<Invoice[]>(`/invoices?${qs}`);
  const { data: sum } = useSWR<{ qua_han: number; hoc_vien_qua_han: number; sap_toi_han_7_ngay: number }>("/invoices/summary");
  const open = Number(params.get("id")) || null;
  return (
    <>
      <PageHeader title="Tài chính" description="Hoá đơn và các đợt thanh toán. Agent công nợ tự nhắc học phí theo bậc trước hạn 3 ngày, quá hạn 1 và 7 ngày; quá 14 ngày đề xuất tạm dừng học." />
      {sum && (
        <div className="mb-4 grid gap-4 sm:grid-cols-3">
          <Stat label="Nợ quá hạn" value={vnd(sum.qua_han)} tone={sum.qua_han ? "danger" : undefined} />
          <Stat label="Học viên có đợt quá hạn" value={sum.hoc_vien_qua_han} />
          <Stat label="Tới hạn trong 7 ngày" value={vnd(sum.sap_toi_han_7_ngay)} />
        </div>
      )}
      <Refunds />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Segmented
          label="Lọc hoá đơn"
          value={filter}
          onChange={setFilter}
          options={[
            { value: "con_no", label: "Còn nợ" },
            { value: "qua_han", label: "Có đợt quá hạn" },
            { value: "all", label: "Tất cả" },
          ]}
        />
        <div className="relative min-w-56 flex-1 sm:max-w-xs">
          <Search className="pointer-events-none absolute start-3 top-2.5 size-4 text-fg-tertiary" aria-hidden />
          <label htmlFor="inv-q" className="sr-only">
            Tìm hoá đơn
          </label>
          <Input id="inv-q" type="search" className="ps-9" placeholder="Tên học viên hoặc mã lớp" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      {error && <ErrorBox error={error} onRetry={() => mutate()} />}
      <Card>
        {!data ? (
          <Spinner />
        ) : data.length === 0 ? (
          <EmptyState title="Không có hoá đơn nào khớp bộ lọc" />
        ) : (
          <Table label="Hoá đơn">
            <thead>
              <tr>
                <th className={th}>Học viên</th>
                <th className={th}>Thanh toán</th>
                <th className={th}>Hạn gần nhất</th>
                <th className={`${th} text-end`}>Phải trả</th>
                <th className={`${th} text-end`}>Còn nợ</th>
              </tr>
            </thead>
            <tbody>
              {data.map((i) => {
                const d = i.han_gan_nhat ? daysFrom(i.han_gan_nhat) : null;
                return (
                  <tr key={i.id} className="hover:bg-surface-hover">
                    <td className={td}>
                      <button className="text-start font-medium hover:underline" onClick={() => router.replace(`/finance?id=${i.id}`, { scroll: false })}>
                        {i.ho_ten}
                      </button>
                      <p className="text-fg-tertiary">
                        #{i.id} · {i.ma_lop}
                      </p>
                    </td>
                    <td className={td}>
                      <div className="flex flex-col items-start gap-1">
                        <StatusBadge map={INVOICE_STATUS} value={i.trang_thai} />
                        {i.trang_thai_hoc === "tam_dung" && <StatusBadge map={ENROLL_STATUS} value="tam_dung" />}
                      </div>
                    </td>
                    <td className={`${td} num`}>
                      {i.han_gan_nhat ? fmtDate(i.han_gan_nhat) : "–"}
                      {d != null && d < 0 && <p className="text-xs text-danger-fg">Quá hạn {-d} ngày</p>}
                      {d != null && d >= 0 && d <= 3 && <p className="text-xs text-warning-fg">Còn {d} ngày</p>}
                    </td>
                    <td className={`${td} num text-end`}>{vnd(i.thanh_tien)}</td>
                    <td className={`${td} num text-end font-medium`}>{vnd(i.con_no)}</td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        )}
      </Card>
      <InvoiceDialog id={open} onClose={() => router.replace("/finance", { scroll: false })} onChanged={() => mutate()} />
    </>
  );
}

export default function FinancePage() {
  return (
    <Suspense fallback={<Spinner />}>
      <Finance />
    </Suspense>
  );
}
