"use client";

import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import {
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorBox,
  Field,
  PageHeader,
  Segmented,
  Select,
  Spinner,
  StatusBadge,
  Textarea,
  useToast,
} from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { REQUEST_KIND, REQUEST_STATUS } from "@/lib/labels";

type Req = {
  id: number;
  hoc_vien_id: number;
  ho_ten: string;
  ma_lop: string | null;
  don_hang_id: number | null;
  loai: string;
  noi_dung: string;
  trang_thai: string;
  phan_hoi: string | null;
  xu_ly_boi: string | null;
  created_at: string;
};

const APPROVE_TEXT: Record<string, string> = {
  bao_luu: "Duyệt và bảo lưu",
  hoan_phi: "Duyệt, huỷ ghi danh và lập hoàn phí",
  chuyen_lop: "Duyệt và chuyển lớp",
  khac: "Đánh dấu đã xử lý",
};

export default function RequestsPage() {
  const [status, setStatus] = useState("moi");
  const { data, error, mutate } = useSWR<Req[]>(`/requests${status ? `?trang_thai=${status}` : ""}`);
  const toast = useToast();
  const [cur, setCur] = useState<{ r: Req; ok: boolean } | null>(null);
  const [reply, setReply] = useState("");
  const [months, setMonths] = useState("3");
  const [medical, setMedical] = useState(false);
  const [newClass, setNewClass] = useState("");
  const [busy, setBusy] = useState(false);
  const { data: classes } = useSWR<{ id: number; ma_lop: string; khoa_hoc: string; trang_thai: string }[]>(
    cur?.r.loai === "chuyen_lop" && cur.ok ? "/classes" : null,
  );

  async function handle() {
    if (!cur) return;
    setBusy(true);
    try {
      await api(`/requests/${cur.r.id}/handle`, {
        body: { duyet: cur.ok, phan_hoi: reply, so_thang: Number(months), mien_phi: medical, lop_moi_id: newClass ? Number(newClass) : null },
      });
      toast(cur.ok ? "Đã duyệt yêu cầu và thực hiện nghiệp vụ tương ứng." : "Đã từ chối yêu cầu.");
      setCur(null);
      setReply("");
      mutate();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Không xử lý được.", "danger");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Yêu cầu học viên" description="Yêu cầu gửi từ cổng học viên. Duyệt yêu cầu sẽ chạy đúng nghiệp vụ, cùng luật như thao tác trực tiếp." />
      <div className="mb-4">
        <Segmented
          label="Lọc yêu cầu"
          value={status}
          onChange={setStatus}
          options={[{ value: "moi", label: "Mới" }, { value: "da_xu_ly", label: "Đã xử lý" }, { value: "tu_choi", label: "Từ chối" }, { value: "", label: "Tất cả" }]}
        />
      </div>
      {error && <ErrorBox error={error} onRetry={() => mutate()} />}
      <Card>
        {!data ? (
          <Spinner />
        ) : data.length === 0 ? (
          <EmptyState title="Không có yêu cầu nào" description="Học viên gửi yêu cầu bảo lưu, hoàn phí hoặc chuyển lớp từ cổng học viên." />
        ) : (
          <ul>
            {data.map((r) => (
              <li key={r.id} className="flex flex-wrap items-start gap-3 border-b border-line px-4 py-3 last:border-0">
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{REQUEST_KIND[r.loai]}</span>
                    <StatusBadge map={REQUEST_STATUS} value={r.trang_thai} />
                    <Link href={`/students/${r.hoc_vien_id}`} className="hover:underline">
                      {r.ho_ten}
                    </Link>
                    {r.ma_lop && <span className="text-fg-tertiary">· lớp {r.ma_lop}</span>}
                  </p>
                  <p className="mt-1 max-w-[70ch] text-pretty">{r.noi_dung}</p>
                  {r.phan_hoi && (
                    <p className="mt-1 text-fg-secondary">
                      Phản hồi ({r.xu_ly_boi}): {r.phan_hoi}
                    </p>
                  )}
                  <p className="mt-0.5 text-xs text-fg-tertiary">{fmtDateTime(r.created_at)}</p>
                </div>
                {r.trang_thai === "moi" && (
                  <div className="flex gap-2">
                    <Button size="sm" variant="ghost" onClick={() => setCur({ r, ok: false })}>
                      Từ chối
                    </Button>
                    <Button size="sm" variant="primary" onClick={() => setCur({ r, ok: true })}>
                      Xử lý
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Dialog
        open={!!cur}
        onClose={() => setCur(null)}
        title={cur ? `${cur.ok ? "Duyệt" : "Từ chối"} yêu cầu ${REQUEST_KIND[cur.r.loai].toLowerCase()} của ${cur.r.ho_ten}` : ""}
        description={cur?.ok && cur.r.loai === "hoan_phi" ? "Ghi danh bị huỷ; tỉ lệ hoàn do hệ thống tính theo thời điểm huỷ và chờ kế toán duyệt chi." : undefined}
        footer={
          <>
            <Button variant="ghost" onClick={() => setCur(null)}>
              Huỷ
            </Button>
            <Button variant={cur?.ok ? "primary" : "danger"} loading={busy} disabled={reply.trim().length < 2 || (cur?.r.loai === "chuyen_lop" && cur.ok && !newClass)} onClick={handle}>
              {cur?.ok ? APPROVE_TEXT[cur.r.loai] : "Từ chối yêu cầu"}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {cur?.ok && cur.r.loai === "bao_luu" && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Số tháng bảo lưu">
                {(p) => (
                  <Select {...p} value={months} onChange={(e) => setMonths(e.target.value)}>
                    {[1, 2, 3, 4, 5, 6].map((m) => (
                      <option key={m}>{m}</option>
                    ))}
                  </Select>
                )}
              </Field>
              <label className="flex items-center gap-3 self-end pb-2">
                <input type="checkbox" className="size-4 accent-[var(--color-accent-solid)]" checked={medical} onChange={(e) => setMedical(e.target.checked)} />
                Miễn phí (có giấy y tế)
              </label>
            </div>
          )}
          {cur?.ok && cur.r.loai === "chuyen_lop" && (
            <Field label="Lớp mới (cùng khoá)">
              {(p) => (
                <Select {...p} value={newClass} onChange={(e) => setNewClass(e.target.value)}>
                  <option value="">Chọn lớp</option>
                  {classes?.filter((c) => c.trang_thai === "sap_khai_giang" || c.trang_thai === "dang_hoc").map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.ma_lop} · {c.khoa_hoc}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}
          <Field label="Phản hồi cho học viên">
            {(p) => <Textarea {...p} rows={3} value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Trung tâm đã duyệt bảo lưu 3 tháng cho bạn." />}
          </Field>
        </div>
      </Dialog>
    </>
  );
}
