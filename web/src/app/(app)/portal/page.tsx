"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  Button,
  Card,
  CardHeader,
  Dialog,
  EmptyState,
  ErrorBox,
  Field,
  PageHeader,
  Select,
  Spinner,
  StatusBadge,
  Textarea,
  useToast,
} from "@/components/ui";
import { api } from "@/lib/api";
import { daysFrom, fmtDate, fmtDateTime, fmtWeekday, pct, vnd } from "@/lib/format";
import { ENROLL_STATUS, INSTALLMENT_STATUS, REQUEST_KIND, REQUEST_STATUS, SHIFT } from "@/lib/labels";

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

  return (
    <>
      <PageHeader
        title={`Chào ${data.hoc_vien.ho_ten}`}
        description="Lịch học, học phí và các yêu cầu của bạn. Có câu hỏi về chính sách? Mở Copilot ở góc trên."
        actions={
          <Button variant="primary" onClick={() => setOpen(true)}>
            Gửi yêu cầu
          </Button>
        }
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Lịch học sắp tới" />
          {data.lich_sap_toi.length === 0 ? (
            <EmptyState title="Chưa có buổi học nào sắp tới" />
          ) : (
            <ul className="px-4 pb-4">
              {data.lich_sap_toi.map((b, i) => (
                <li key={i} className="flex items-start gap-4 border-b border-line py-2.5 last:border-0">
                  <span className="num w-24 shrink-0 font-medium">{fmtWeekday(b.ngay)}</span>
                  <span className="min-w-0">
                    <span className="block">
                      {b.khoa_hoc} · buổi {b.so_thu_tu}
                    </span>
                    <span className="block text-fg-tertiary">
                      Ca {SHIFT[b.ca_hoc].toLowerCase()} · {b.hinh_thuc === "online" ? "trực tuyến" : `${b.co_so} · ${b.phong}`}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <CardHeader title="Học phí cần đóng" description={owed ? `Tổng ${vnd(owed)}` : undefined} />
          {data.cong_no.length === 0 ? (
            <EmptyState title="Bạn đã đóng đủ học phí" />
          ) : (
            <ul className="px-4 pb-4">
              {data.cong_no.map((d) => {
                const left = daysFrom(d.han_thanh_toan);
                return (
                  <li key={d.id} className="num flex flex-wrap items-center gap-3 border-b border-line py-2.5 last:border-0">
                    <span className="min-w-0 flex-1">
                      <span className="block">
                        {d.khoa_hoc} · đợt {d.so_thu_tu}
                      </span>
                      <span className={`block text-xs ${left < 0 ? "text-danger-fg" : "text-fg-tertiary"}`}>
                        Hạn {fmtDate(d.han_thanh_toan)}
                        {left < 0 ? ` · quá hạn ${-left} ngày` : left <= 3 ? ` · còn ${left} ngày` : ""}
                      </span>
                    </span>
                    <span className="font-medium">{vnd(d.so_tien)}</span>
                    <StatusBadge map={INSTALLMENT_STATUS} value={d.trang_thai} />
                  </li>
                );
              })}
              <li className="pt-3 text-xs text-fg-secondary">Chuyển khoản hoặc đóng tại quầy; kế toán xác nhận trong ngày làm việc.</li>
            </ul>
          )}
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title="Lớp của bạn" />
          <ul className="grid gap-3 px-4 pb-4 sm:grid-cols-2">
            {data.ghi_danh.map((g) => (
              <li key={g.don_hang_id} className="rounded-xl border border-line p-3">
                <p className="flex flex-wrap items-center gap-2 font-medium">
                  {g.khoa_hoc} <StatusBadge map={ENROLL_STATUS} value={g.trang_thai_hoc} />
                </p>
                <p className="text-fg-tertiary">
                  Lớp {g.ma_lop} · {SHIFT[g.ca_hoc]} {g.lich_hoc} · {g.giang_vien}
                </p>
                <p className="num mt-2 text-fg-secondary">
                  Chuyên cần {g.chuyen_can == null ? "chưa có" : pct(g.chuyen_can)}
                  {g.chuyen_can != null && g.chuyen_can < 0.8 && " (cần từ 80% để được cấp chứng nhận)"}
                  {g.diem_cuoi_khoa != null && ` · điểm cuối khoá ${g.diem_cuoi_khoa}`}
                </p>
              </li>
            ))}
          </ul>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title="Yêu cầu đã gửi" />
          {data.yeu_cau.length === 0 ? (
            <EmptyState title="Bạn chưa gửi yêu cầu nào" description="Gửi yêu cầu bảo lưu, hoàn phí hoặc chuyển lớp ngay tại đây." />
          ) : (
            <ul className="px-4 pb-4">
              {data.yeu_cau.map((y) => (
                <li key={y.id} className="border-b border-line py-2.5 last:border-0">
                  <p className="flex flex-wrap items-center gap-2 font-medium">
                    {REQUEST_KIND[y.loai]} <StatusBadge map={REQUEST_STATUS} value={y.trang_thai} />
                    <span className="text-xs font-normal text-fg-tertiary">{fmtDateTime(y.created_at)}</span>
                  </p>
                  <p className="text-fg-secondary text-pretty">{y.noi_dung}</p>
                  {y.phan_hoi && <p className="mt-1 text-pretty">Trung tâm: {y.phan_hoi}</p>}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

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
