"use client";

import { useState } from "react";
import useSWR from "swr";
import { MapPin } from "lucide-react";
import {
  Button,
  Dialog,
  EmptyState,
  ErrorBox,
  Field,
  Select,
  Spinner,
  StatusBadge,
  SunMark,
  Textarea,
  useToast,
} from "@/components/ui";
import { api } from "@/lib/api";
import { daysFrom, fmtDate, fmtDateTime, fmtWeekday, pct, relDay, vnd } from "@/lib/format";
import { ENROLL_STATUS, REQUEST_KIND, REQUEST_STATUS, SHIFT } from "@/lib/labels";

type Portal = {
  hoc_vien: { ho_ten: string; email: string };
  ghi_danh: {
    don_hang_id: number;
    ma_lop: string;
    khoa_hoc: string;
    ca_hoc: string;
    lich_hoc: string;
    giang_vien: string;
    trang_thai_hoc: string;
    con_no: number;
    chuyen_can: number | null;
    diem_cuoi_khoa: number | null;
  }[];
  lich_sap_toi: { ngay: string; so_thu_tu: number; ma_lop: string; khoa_hoc: string; ca_hoc: string; phong: string | null; co_so: string | null; hinh_thuc: string }[];
  cong_no: { id: number; so_thu_tu: number; so_tien: number; han_thanh_toan: string; trang_thai: string; ma_lop: string; khoa_hoc: string }[];
  yeu_cau: { id: number; loai: string; noi_dung: string; trang_thai: string; phan_hoi: string | null; created_at: string }[];
};

export default function PortalPage() {
  const { data, error, mutate } = useSWR<Portal>("/portal");
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState("bao_luu");
  const [enr, setEnr] = useState("");
  const [content, setContent] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return <Spinner />;
  const active = data.ghi_danh.filter((g) => !["da_huy", "hoan_thanh"].includes(g.trang_thai_hoc));
  const owed = data.cong_no.reduce((s, d) => s + d.so_tien, 0);

  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      await api("/portal/requests", { body: { loai: kind, noi_dung: content, don_hang_id: kind === "khac" ? null : Number(enr) || null } });
      toast("Đã gửi yêu cầu. Trung tâm phản hồi trong 2 ngày làm việc.");
      setOpen(false);
      setContent("");
      mutate();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Không gửi được yêu cầu.");
    } finally {
      setBusy(false);
    }
  }

  const [next, ...later] = data.lich_sap_toi;
  return (
    <>
      <h1 tabIndex={-1} data-page-title className="sr-only">
        Cổng học viên
      </h1>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        {/* thẻ học viên */}
        <section aria-label="Thẻ học viên" className="relative isolate self-start overflow-hidden rounded-3xl bg-side p-6 text-side-fg shadow-pop">
          <svg viewBox="0 0 200 200" className="pointer-events-none absolute -end-20 -bottom-24 -z-10 w-72" aria-hidden>
            {[95, 75, 55].map((r, i) => (
              <circle key={r} cx="100" cy="100" r={r} fill="none" stroke="var(--color-brand)" strokeOpacity={0.15 + i * 0.12} strokeWidth="1.5" />
            ))}
            <circle cx="100" cy="100" r="34" fill="var(--color-brand)" fillOpacity="0.9" />
          </svg>
          <p className="text-[0.6875rem] font-medium tracking-[0.05em] text-side-fg-secondary uppercase">Thẻ học viên · Trung tâm Ánh Dương</p>
          <p className="font-display relative mt-6 text-3xl leading-tight font-medium text-balance">Chào {data.hoc_vien.ho_ten}</p>
          <p className="mt-1 text-side-fg-secondary">{data.hoc_vien.email}</p>
          <div className="mt-6 flex flex-wrap gap-x-8 gap-y-3">
            <div>
              <p className="text-xs text-side-fg-secondary">Lớp đang theo</p>
              <p className="font-display num text-2xl">{active.length}</p>
            </div>
            <div>
              <p className="text-xs text-side-fg-secondary">Học phí cần đóng</p>
              <p className="font-display num text-2xl">{owed ? vnd(owed) : "Đã đủ"}</p>
            </div>
          </div>
          <Button variant="secondary" className="mt-6" onClick={() => setOpen(true)}>
            Gửi yêu cầu cho trung tâm
          </Button>
        </section>

        {/* vé buổi học kế tiếp */}
        <section aria-labelledby="next-title" className="flex flex-col">
          <h2 id="next-title" className="mb-2 text-xs font-semibold tracking-[0.05em] text-fg-secondary uppercase">
            Buổi học kế tiếp
          </h2>
          {!next ? (
            <div className="rounded-2xl bg-surface p-6 text-fg-secondary shadow-card">Chưa có buổi học nào sắp tới.</div>
          ) : (
            <div className="flex overflow-hidden rounded-2xl bg-surface shadow-card">
              <div className="flex w-28 shrink-0 flex-col items-center justify-center border-e-2 border-dashed border-line-strong bg-brand-subtle px-2 py-4 text-center">
                <span className="text-xs font-medium text-fg-secondary">{fmtWeekday(next.ngay).split(",")[0]}</span>
                <span className="font-display num text-4xl leading-none font-semibold">{next.ngay.slice(8, 10)}</span>
                <span className="num text-xs text-fg-secondary">tháng {Number(next.ngay.slice(5, 7))}</span>
              </div>
              <div className="min-w-0 flex-1 p-4">
                <p className="text-xs text-fg-tertiary">{relDay(next.ngay)}</p>
                <p className="font-display text-xl leading-snug font-medium">{next.khoa_hoc}</p>
                <p className="mt-1 text-fg-secondary">
                  Buổi {next.so_thu_tu} · ca {SHIFT[next.ca_hoc].toLowerCase()}
                </p>
                <p className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-surface-hover px-2.5 py-1 text-[0.8125rem]">
                  <MapPin className="size-3.5" aria-hidden />
                  {next.hinh_thuc === "online" ? "Học trực tuyến" : `${next.co_so} · ${next.phong}`}
                </p>
              </div>
            </div>
          )}
          {later.length > 0 && (
            <ul className="mt-3 flex flex-col">
              {later.slice(0, 4).map((b, i) => (
                <li key={i} className="flex items-center gap-3 border-b border-line py-2 last:border-0">
                  <span className="num w-24 shrink-0 font-medium">{fmtWeekday(b.ngay)}</span>
                  <span className="min-w-0 flex-1 truncate">
                    {b.khoa_hoc} · buổi {b.so_thu_tu}
                  </span>
                  <span className="shrink-0 text-xs text-fg-tertiary">{SHIFT[b.ca_hoc]}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <section aria-labelledby="my-classes">
          <h2 id="my-classes" className="font-display mb-3 text-xl font-medium">
            Lớp của bạn
          </h2>
          <ul className="flex flex-col gap-3">
            {data.ghi_danh.map((g) => {
              const rate = g.chuyen_can ?? 0;
              const ok = g.chuyen_can == null || g.chuyen_can >= 0.8;
              return (
                <li key={g.don_hang_id} className="flex items-center gap-4 rounded-2xl bg-surface p-4 shadow-card">
                  <span className="relative grid size-16 shrink-0 place-items-center">
                    <svg viewBox="0 0 36 36" className="absolute inset-0 -rotate-90" aria-hidden>
                      <circle cx="18" cy="18" r="15" fill="none" stroke="var(--color-surface-hover)" strokeWidth="3.5" />
                      {g.chuyen_can != null && (
                        <circle
                          cx="18"
                          cy="18"
                          r="15"
                          fill="none"
                          stroke={ok ? "var(--color-success-fg)" : "var(--color-warning-fg)"}
                          strokeWidth="3.5"
                          strokeLinecap="round"
                          strokeDasharray={`${rate * 94.25} 94.25`}
                        />
                      )}
                      {/* vạch 80% - ngưỡng cấp chứng nhận */}
                      <line x1="30.5" y1="18" x2="34.5" y2="18" stroke="var(--color-fg)" strokeWidth="1.25" transform="rotate(288 18 18)" />
                    </svg>
                    <span className="num text-[0.8125rem] font-semibold">{g.chuyen_can == null ? "–" : pct(g.chuyen_can)}</span>
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-2 font-semibold">
                      {g.khoa_hoc} <StatusBadge map={ENROLL_STATUS} value={g.trang_thai_hoc} />
                    </span>
                    <span className="block text-fg-secondary">
                      <span className="font-mono text-xs">{g.ma_lop}</span> · {SHIFT[g.ca_hoc]} {g.lich_hoc} · {g.giang_vien}
                    </span>
                    <span className={`mt-1 block text-xs ${ok ? "text-fg-tertiary" : "font-medium text-warning-fg"}`}>
                      {g.chuyen_can == null
                        ? "Chưa có buổi điểm danh"
                        : ok
                          ? "Chuyên cần đạt ngưỡng 80% để nhận chứng nhận"
                          : "Chuyên cần dưới 80%, cần đi học đều hơn để được cấp chứng nhận"}
                      {g.diem_cuoi_khoa != null && ` · điểm cuối khoá ${g.diem_cuoi_khoa}`}
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        </section>

        <section aria-labelledby="my-fees">
          <h2 id="my-fees" className="font-display mb-3 text-xl font-medium">
            Học phí
          </h2>
          <div className="receipt-edge rounded-t-2xl bg-surface px-5 pt-5 pb-8 shadow-card">
            <p className="text-center text-xs font-medium tracking-[0.05em] text-fg-secondary uppercase">Phiếu báo học phí</p>
            {data.cong_no.length === 0 ? (
              <p className="font-display mt-4 text-center text-xl">Bạn đã đóng đủ học phí.</p>
            ) : (
              <>
                <ul className="mt-4 flex flex-col gap-3">
                  {data.cong_no.map((d) => {
                    const left = daysFrom(d.han_thanh_toan);
                    return (
                      <li key={d.id} className="num">
                        <span className="flex items-baseline gap-2">
                          <span className="min-w-0 truncate">
                            {d.khoa_hoc} · đợt {d.so_thu_tu}
                          </span>
                          <span className="flex-1 border-b border-dotted border-line-strong" aria-hidden />
                          <span className="font-medium">{vnd(d.so_tien)}</span>
                        </span>
                        <span className={`block text-xs ${left < 0 ? "font-medium text-danger-fg" : "text-fg-tertiary"}`}>
                          Hạn {fmtDate(d.han_thanh_toan)}
                          {left < 0 ? ` · quá hạn ${-left} ngày` : left <= 3 ? ` · còn ${left} ngày` : ""}
                        </span>
                      </li>
                    );
                  })}
                </ul>
                <p className="mt-4 flex items-baseline justify-between border-t border-dashed border-control-border pt-3">
                  <span className="font-semibold">Tổng cần đóng</span>
                  <span className="font-display num text-2xl font-semibold">{vnd(owed)}</span>
                </p>
                <p className="mt-2 text-xs text-fg-secondary">Chuyển khoản hoặc đóng tại quầy. Kế toán xác nhận trong ngày làm việc.</p>
              </>
            )}
          </div>
        </section>
      </div>

      <section aria-labelledby="my-requests" className="mt-8">
        <h2 id="my-requests" className="font-display mb-3 text-xl font-medium">
          Trao đổi với trung tâm
        </h2>
        {data.yeu_cau.length === 0 ? (
          <EmptyState
            title="Bạn chưa gửi yêu cầu nào"
            description="Gửi yêu cầu bảo lưu, hoàn phí hoặc chuyển lớp ngay tại đây."
            action={<Button onClick={() => setOpen(true)}>Gửi yêu cầu</Button>}
          />
        ) : (
          <ul className="flex max-w-3xl flex-col gap-5">
            {data.yeu_cau.map((y) => (
              <li key={y.id} className="flex flex-col gap-2">
                <div className="ms-auto max-w-[85%] rounded-2xl rounded-ee-md bg-accent-solid px-4 py-2.5 text-white">
                  <p className="text-xs font-medium opacity-80">
                    {REQUEST_KIND[y.loai]} · {fmtDateTime(y.created_at)}
                  </p>
                  <p className="text-pretty">{y.noi_dung}</p>
                </div>
                {y.phan_hoi ? (
                  <div className="flex max-w-[85%] items-end gap-2">
                    <SunMark className="size-7 shrink-0" />
                    <div className="rounded-2xl rounded-es-md bg-surface px-4 py-2.5 shadow-card">
                      <p className="flex flex-wrap items-center gap-2 text-xs text-fg-tertiary">
                        Trung tâm Ánh Dương <StatusBadge map={REQUEST_STATUS} value={y.trang_thai} />
                      </p>
                      <p className="text-pretty">{y.phan_hoi}</p>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-fg-tertiary">
                    <StatusBadge map={REQUEST_STATUS} value={y.trang_thai} /> · trung tâm phản hồi trong 2 ngày làm việc
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Gửi yêu cầu cho trung tâm"
        description="Bảo lưu tối đa 1 lần, tối đa 6 tháng. Mức hoàn phí phụ thuộc thời điểm huỷ theo chính sách của trung tâm."
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Huỷ
            </Button>
            <Button variant="primary" loading={busy} disabled={content.trim().length < 5 || (kind !== "khac" && !enr)} onClick={submit}>
              Gửi yêu cầu
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Field label="Loại yêu cầu">
            {(p) => (
              <Select {...p} value={kind} onChange={(e) => setKind(e.target.value)}>
                {Object.entries(REQUEST_KIND).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          {kind !== "khac" && (
            <Field label="Lớp liên quan">
              {(p) => (
                <Select {...p} value={enr} onChange={(e) => setEnr(e.target.value)}>
                  <option value="">Chọn lớp</option>
                  {active.map((g) => (
                    <option key={g.don_hang_id} value={g.don_hang_id}>
                      {g.khoa_hoc} · {g.ma_lop}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}
          <Field label="Nội dung" hint="Ghi rõ lý do và thời gian mong muốn">
            {(p) => <Textarea {...p} rows={4} value={content} onChange={(e) => setContent(e.target.value)} placeholder="Em xin bảo lưu 2 tháng vì đi công tác" />}
          </Field>
          {err && (
            <p role="alert" className="rounded-lg bg-danger-subtle px-3 py-2 text-danger-fg">
              {err}
            </p>
          )}
        </div>
      </Dialog>
    </>
  );
}
