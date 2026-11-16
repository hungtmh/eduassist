"use client";

import { Layers, List, Search } from "lucide-react";
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
  LoadMore,
  Field,
  Input,
  PageHeader,
  Segmented,
  Select,
  Spinner,

  StatusBadge,
  Table,
  td,
  th,
  cx,
  useToast,
} from "@/components/ui";
import { api } from "@/lib/api";
import { usePaged } from "@/lib/use-paged";
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
          <div className="receipt-edge rounded-t-xl bg-brand-subtle px-4 pt-4 pb-6">
            <p className="text-center text-xs font-medium tracking-[0.05em] text-fg-secondary uppercase">Phiếu học phí · Trung tâm Ánh Dương</p>
            <dl className="num mt-3 flex flex-col gap-1.5">
              {[
                ["Học phí gốc", vnd(inv.hoc_phi_goc)],
                ["Giảm giá", inv.giam_gia ? `− ${vnd(inv.giam_gia)}` : vnd(0)],
                ["Đã đóng", inv.da_dong ? `− ${vnd(inv.da_dong)}` : vnd(0)],
              ].map(([k, v]) => (
                <div key={k} className="flex items-baseline gap-2">
                  <dt className="text-fg-secondary">{k}</dt>
                  <span className="flex-1 border-b border-dotted border-line-strong" aria-hidden />
                  <dd>{v}</dd>
                </div>
              ))}
              <div className="mt-2 flex items-baseline justify-between gap-2 border-t border-dashed border-control-border pt-2">
                <dt className="font-semibold">Còn phải đóng</dt>
                <dd className="font-display text-2xl font-semibold">{vnd(inv.con_no)}</dd>
              </div>
            </dl>
          </div>
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

/** Bậc nhắc nợ trùng với ngưỡng agent công nợ dùng (rules.DEBT_TIERS: -3, 1, 7, 14). */
const RUNGS = [
  { key: "tam_dung", title: "Quá hạn từ 14 ngày", agent: "Agent đề xuất tạm dừng học, cần kế toán duyệt", tone: "danger", test: (d: number) => d <= -14 },
  { key: "qua_han_7", title: "Quá hạn 7–13 ngày", agent: "Nhắc lần 2, kèm số hotline kế toán", tone: "danger", test: (d: number) => d <= -7 && d > -14 },
  { key: "qua_han_1", title: "Quá hạn 1–6 ngày", agent: "Nhắc lần 1, tự gửi trong hạn mức L2", tone: "warning", test: (d: number) => d < 0 && d > -7 },
  { key: "truoc_han", title: "Tới hạn trong 3 ngày", agent: "Nhắc trước hạn, tự gửi trong hạn mức L2", tone: "warning", test: (d: number) => d >= 0 && d <= 3 },
  { key: "chua_toi", title: "Chưa tới hạn", agent: "Chưa cần nhắc", tone: "neutral", test: (d: number) => d > 3 },
] as const;

const RUNG_STYLE = {
  danger: { bar: "bg-danger-fg", head: "text-danger-fg" },
  warning: { bar: "bg-warning-fg", head: "text-warning-fg" },
  neutral: { bar: "bg-line-strong", head: "text-fg-secondary" },
} as const;

function Ladder({ invoices, onOpen }: { invoices: Invoice[]; onOpen: (id: number) => void }) {
  const withDue = invoices.filter((i) => i.han_gan_nhat && i.con_no > 0 && i.trang_thai_hoc !== "da_huy");
  const total = withDue.reduce((s, i) => s + i.con_no, 0) || 1;
  return (
    <ol className="flex flex-col gap-3">
      {RUNGS.map((r, idx) => {
        const rows = withDue.filter((i) => r.test(daysFrom(i.han_gan_nhat!))).sort((a, b) => a.han_gan_nhat!.localeCompare(b.han_gan_nhat!));
        const sum = rows.reduce((s, i) => s + i.con_no, 0);
        const st = RUNG_STYLE[r.tone];
        return (
          <li key={r.key} className="grid gap-3 rounded-2xl bg-surface p-3 shadow-card md:grid-cols-[15rem_minmax(0,1fr)]">
            <div className="flex gap-3 md:flex-col md:gap-1 md:border-e md:border-dashed md:border-line-strong md:pe-3">
              <span className="font-display num text-3xl leading-none font-medium text-fg-tertiary" aria-hidden>
                {RUNGS.length - idx}
              </span>
              <div className="min-w-0">
                <h2 className={cx("font-semibold", st.head)}>{r.title}</h2>
                <p className="text-xs text-fg-secondary text-pretty">{r.agent}</p>
                <p className="num mt-2 font-medium">
                  {vnd(sum)} <span className="font-normal text-fg-tertiary">· {rows.length} hoá đơn</span>
                </p>
                <span className="mt-1.5 block h-1 overflow-hidden rounded-full bg-surface-hover" aria-hidden>
                  <span className={cx("block h-full rounded-full", st.bar)} style={{ width: `${(sum / total) * 100}%` }} />
                </span>
              </div>
            </div>
            {rows.length === 0 ? (
              <p className="self-center text-fg-tertiary">Không có hoá đơn ở bậc này.</p>
            ) : (
              <ul className="relative flex snap-x gap-2 overflow-x-auto pb-1" aria-label={r.title}>
                {rows.map((i) => {
                  const d = daysFrom(i.han_gan_nhat!);
                  return (
                    <li key={i.id} className="w-52 shrink-0 snap-start">
                      <button
                        onClick={() => onOpen(i.id)}
                        className="pressable block h-full w-full rounded-xl bg-surface-muted px-3 py-2.5 text-start hover:bg-surface-hover"
                      >
                        <span className="block truncate font-medium">{i.ho_ten}</span>
                        <span className="block truncate font-mono text-xs text-fg-tertiary">
                          #{i.id} · {i.ma_lop}
                        </span>
                        <span className="num mt-2 block text-base font-semibold">{vnd(i.con_no)}</span>
                        <span className={cx("num block text-xs", d < 0 ? "font-medium text-danger-fg" : "text-fg-secondary")}>
                          {d < 0 ? `Quá hạn ${-d} ngày` : d === 0 ? "Tới hạn hôm nay" : `Hạn ${fmtDate(i.han_gan_nhat)}`}
                          {i.trang_thai_hoc === "tam_dung" && " · đang tạm dừng"}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </li>
        );
      })}
    </ol>
  );
}

function Finance() {
  const params = useSearchParams();
  const router = useRouter();
  const [view, setView] = useState<"ladder" | "list">("ladder");
  const [filter, setFilter] = useState<"con_no" | "qua_han" | "all">("con_no");
  const [q, setQ] = useState("");
  const qs = new URLSearchParams({
    ...(view === "ladder" || filter === "con_no" ? { trang_thai: "con_no" } : {}),
    ...(view === "list" && filter === "qua_han" ? { qua_han: "true" } : {}),
    ...(q ? { q } : {}),
  });
  // Thang nhắc nợ cần thấy nhiều hoá đơn một lúc để chia bậc -> trang lớn hơn sổ hoá đơn
  const list = usePaged<Invoice>(`/invoices?${qs}`, view === "ladder" ? 500 : 100);
  const { items: data, error, mutate } = list;
  const { data: sum } = useSWR<{ qua_han: number; hoc_vien_qua_han: number; sap_toi_han_7_ngay: number }>("/invoices/summary");
  const open = Number(params.get("id")) || null;
  const openInvoice = (id: number) => router.replace(`/finance?id=${id}`, { scroll: false });
  return (
    <>
      <PageHeader
        eyebrow="Tài chính"
        title="Thang nhắc nợ"
        description={
          sum ? (
            <>
              <span className="num font-medium text-danger-fg">{vnd(sum.qua_han)}</span> quá hạn ở {sum.hoc_vien_qua_han} học viên,{" "}
              <span className="num font-medium text-fg">{vnd(sum.sap_toi_han_7_ngay)}</span> tới hạn trong 7 ngày. Agent công nợ leo từng bậc; chỉ kế toán
              ghi nhận được tiền đã thu.
            </>
          ) : undefined
        }
      />
      <Refunds />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Segmented
          label="Kiểu xem"
          value={view}
          onChange={setView}
          options={[
            { value: "ladder", label: "Theo bậc nhắc", icon: <Layers className="size-3.5" aria-hidden /> },
            { value: "list", label: "Sổ hoá đơn", icon: <List className="size-3.5" aria-hidden /> },
          ]}
        />
        {view === "list" && (
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
        )}
        <div className="relative min-w-56 flex-1 sm:max-w-xs">
          <Search className="pointer-events-none absolute start-3 top-2.5 size-4 text-fg-tertiary" aria-hidden />
          <label htmlFor="inv-q" className="sr-only">
            Tìm hoá đơn
          </label>
          <Input id="inv-q" type="search" className="ps-9" placeholder="Tên học viên hoặc mã lớp" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      {error && <ErrorBox error={error} onRetry={() => mutate()} />}
      {!data ? (
        <Spinner />
      ) : view === "ladder" ? (
        <Ladder invoices={data} onOpen={openInvoice} />
      ) : (
        <Card>
          {data.length === 0 ? (
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
                        <button className="text-start font-medium hover:underline" onClick={() => openInvoice(i.id)}>
                          {i.ho_ten}
                        </button>
                        <p className="font-mono text-xs text-fg-tertiary">
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
      )}
      {data && (
        <LoadMore shown={data.length} total={list.total} noun="hoá đơn" hasMore={list.hasMore} loading={list.loadingMore} onMore={list.loadMore} />
      )}
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
