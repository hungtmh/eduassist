"use client";

import { ArrowLeft, Phone } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { useAuth } from "@/components/providers";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Dialog,
  ErrorBox,
  Field,
  Input,
  PageHeader,
  Select,
  Spinner,
  StatusBadge,
  Textarea,
  useToast,
} from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, fmtDateTime } from "@/lib/format";
import { LEAD_STATUS, SOURCE } from "@/lib/labels";
import type { Lead } from "../page";

type Detail = Lead & {
  hoc_vien_id: number | null;
  ly_do_dung: string | null;
  lich_hen: { id: number; loai: string; thoi_gian: string; ma_lop: string | null }[];
  lich_su: { actor: string; hanh_dong: string; ly_do: string | null; created_at: string; sau: Record<string, unknown> | null }[];
};

// Hướng chuyển hợp lệ (khớp máy trạng thái ở backend; backend vẫn kiểm tra lại)
const NEXT: Record<string, string[]> = {
  moi: ["khong_tiep_tuc"],
  da_lien_he: ["khong_tiep_tuc"],
  hen_hoc_thu: ["da_lien_he", "khong_tiep_tuc"],
  khong_tiep_tuc: ["da_lien_he"],
  da_ghi_danh: [],
};
const ACTION_TEXT: Record<string, string> = {
  tao_khach: "Tạo khách",
  cham_diem_khach: "Chấm điểm",
  lien_he_khach: "Ghi nhận liên hệ",
  chuyen_trang_thai_khach: "Đổi trạng thái",
  dat_lich_hen: "Đặt lịch hẹn",
  khach_ghi_danh: "Ghi danh",
  tao_hoc_vien_tu_khach: "Tạo hồ sơ học viên",
};

export default function LeadDetail() {
  const { id } = useParams<{ id: string }>();
  const { can } = useAuth();
  const toast = useToast();
  const { data: l, error, mutate } = useSWR<Detail>(`/leads/${id}`);
  const { data: classes } = useSWR<{ id: number; ma_lop: string; khoa_hoc: string }[]>(
    can("class.read") ? "/classes?trang_thai=sap_khai_giang" : null,
  );
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [stopOpen, setStopOpen] = useState(false);
  const [apptOpen, setApptOpen] = useState(false);
  const [convertOpen, setConvertOpen] = useState(false);
  const [appt, setAppt] = useState({ loai: "hoc_thu", thoi_gian: "", lop_hoc_id: "" });
  const [conv, setConv] = useState({ nam_sinh: "2000", thanh_pho: "TP.HCM" });

  async function run(key: string, path: string, body: unknown, ok: string) {
    setBusy(key);
    try {
      await api(path, { body });
      toast(ok);
      setNote("");
      await mutate();
      return true;
    } catch (e) {
      toast(e instanceof Error ? e.message : "Không thực hiện được.", "danger");
      return false;
    } finally {
      setBusy(null);
    }
  }

  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!l) return <Spinner />;
  const writable = can("lead.write") && l.trang_thai !== "da_ghi_danh";

  return (
    <>
      <PageHeader
        back={
          <Link href="/leads" className="mb-2 inline-flex items-center gap-1 text-[0.8125rem] text-fg-secondary hover:text-fg">
            <ArrowLeft className="size-3.5" aria-hidden />
            Tuyển sinh
          </Link>
        }
        title={l.ho_ten}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <StatusBadge map={LEAD_STATUS} value={l.trang_thai} />
            <span>Điểm tiềm năng {l.diem ?? "chưa chấm"}</span>
            <span>· Phụ trách: {l.ten_phu_trach ?? "chưa phân"}</span>
          </span>
        }
        actions={
          writable && (
            <>
              {l.email && !l.hoc_vien_id && <Button onClick={() => setConvertOpen(true)}>Tạo hồ sơ học viên</Button>}
              {l.hoc_vien_id && (
                <Link href={`/students/${l.hoc_vien_id}?enroll=1&lead=${l.id}`}>
                  <Button variant="primary">Ghi danh vào lớp</Button>
                </Link>
              )}
            </>
          )
        }
      />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader title="Thông tin khách" />
            <dl className="grid gap-x-6 gap-y-3 px-4 pb-4 sm:grid-cols-2">
              <div>
                <dt className="text-fg-tertiary">Điện thoại</dt>
                <dd>
                  <a href={`tel:${l.so_dien_thoai}`} className="num inline-flex items-center gap-1.5 hover:underline">
                    <Phone className="size-3.5" aria-hidden />
                    {l.so_dien_thoai}
                  </a>
                </dd>
              </div>
              <div>
                <dt className="text-fg-tertiary">Email</dt>
                <dd className="break-words">{l.email ?? "Chưa có"}</dd>
              </div>
              <div>
                <dt className="text-fg-tertiary">Nguồn</dt>
                <dd>{SOURCE[l.nguon] ?? l.nguon}</dd>
              </div>
              <div>
                <dt className="text-fg-tertiary">Khoá quan tâm</dt>
                <dd>{l.khoa_quan_tam ?? "Chưa rõ"}</dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-fg-tertiary">Nhu cầu</dt>
                <dd className="text-pretty">{l.nhu_cau || "Chưa ghi"}</dd>
              </div>
              <div>
                <dt className="text-fg-tertiary">Liên hệ lần cuối</dt>
                <dd className="num">{l.lien_he_cuoi ? fmtDateTime(l.lien_he_cuoi) : "Chưa liên hệ"}</dd>
              </div>
              <div>
                <dt className="text-fg-tertiary">Ngày tạo</dt>
                <dd className="num">{fmtDate(l.created_at)}</dd>
              </div>
              {l.ly_do_dung && (
                <div className="sm:col-span-2">
                  <dt className="text-fg-tertiary">Lý do ngừng</dt>
                  <dd>{l.ly_do_dung}</dd>
                </div>
              )}
            </dl>
          </Card>

          {writable && (
            <Card>
              <CardHeader title="Ghi nhận liên hệ" description="Khách mới sẽ chuyển sang Đã liên hệ; việc nhắc liên hệ đang mở được đóng lại." />
              <form
                className="flex flex-col gap-3 px-4 pb-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  run("contact", `/leads/${l.id}/contact`, { ghi_chu: note }, "Đã ghi nhận lần liên hệ.");
                }}
              >
                <Field label="Nội dung trao đổi">
                  {(p) => <Textarea {...p} rows={3} required value={note} onChange={(e) => setNote(e.target.value)} placeholder="Đã gọi, khách muốn học thử thứ Bảy" />}
                </Field>
                <div className="flex flex-wrap justify-end gap-3">
                  {NEXT[l.trang_thai]?.includes("khong_tiep_tuc") && (
                    <Button type="button" variant="ghost" onClick={() => setStopOpen(true)}>
                      Ngừng theo đuổi
                    </Button>
                  )}
                  {NEXT[l.trang_thai]?.includes("da_lien_he") && (
                    <Button type="button" variant="ghost" loading={busy === "back"}
                      onClick={() => run("back", `/leads/${l.id}/transition`, { trang_thai: "da_lien_he", ghi_chu: note }, "Đã chuyển về Đã liên hệ.")}>
                      Chuyển về Đã liên hệ
                    </Button>
                  )}
                  <Button type="button" onClick={() => setApptOpen(true)}>
                    Đặt lịch hẹn
                  </Button>
                  <Button type="submit" variant="primary" disabled={!note.trim()} loading={busy === "contact"}>
                    Lưu lần liên hệ
                  </Button>
                </div>
              </form>
            </Card>
          )}
        </div>

        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader title="Lịch hẹn" />
            <ul className="px-4 pb-4">
              {l.lich_hen.length === 0 && <li className="text-fg-secondary">Chưa có lịch hẹn.</li>}
              {l.lich_hen.map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-2 border-b border-line py-2 last:border-0">
                  <span>{a.loai === "hoc_thu" ? `Học thử${a.ma_lop ? ` lớp ${a.ma_lop}` : ""}` : "Tư vấn"}</span>
                  <span className="num text-fg-secondary">{fmtDateTime(a.thoi_gian)}</span>
                </li>
              ))}
            </ul>
          </Card>
          <Card>
            <CardHeader title="Lịch sử" />
            <ol className="flex flex-col gap-3 px-4 pb-4">
              {l.lich_su.map((h, i) => (
                <li key={i}>
                  <p className="flex flex-wrap items-center gap-1.5">
                    <span className="font-medium">{ACTION_TEXT[h.hanh_dong] ?? h.hanh_dong}</span>
                    {h.actor.startsWith("agent:") && <Badge tone="agent">agent</Badge>}
                  </p>
                  {h.ly_do && <p className="text-fg-secondary text-pretty">{h.ly_do}</p>}
                  <p className="text-xs text-fg-tertiary">
                    {h.actor.replace("agent:", "agent ")} · {fmtDateTime(h.created_at)}
                  </p>
                </li>
              ))}
            </ol>
          </Card>
        </div>
      </div>

      <Dialog
        open={stopOpen}
        onClose={() => setStopOpen(false)}
        title={`Ngừng theo đuổi ${l.ho_ten}?`}
        description="Khách chuyển sang Không tiếp tục và không còn trong danh sách nhắc việc. Có thể mở lại khi khách quay lại."
        footer={
          <>
            <Button variant="ghost" onClick={() => setStopOpen(false)}>
              Huỷ
            </Button>
            <Button variant="danger" disabled={!note.trim()} loading={busy === "stop"}
              onClick={async () => (await run("stop", `/leads/${l.id}/transition`, { trang_thai: "khong_tiep_tuc", ghi_chu: note }, "Đã ngừng theo đuổi khách.")) && setStopOpen(false)}>
              Ngừng theo đuổi
            </Button>
          </>
        }
      >
        <Field label="Lý do (bắt buộc)">
          {(p) => <Input {...p} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Đã đăng ký ở trung tâm khác" />}
        </Field>
      </Dialog>

      <Dialog
        open={apptOpen}
        onClose={() => setApptOpen(false)}
        title="Đặt lịch hẹn"
        footer={
          <>
            <Button variant="ghost" onClick={() => setApptOpen(false)}>
              Huỷ
            </Button>
            <Button variant="primary" loading={busy === "appt"} disabled={!appt.thoi_gian}
              onClick={async () =>
                (await run("appt", `/leads/${l.id}/appointments`,
                  { loai: appt.loai, thoi_gian: new Date(appt.thoi_gian).toISOString(), lop_hoc_id: appt.lop_hoc_id ? Number(appt.lop_hoc_id) : null },
                  "Đã đặt lịch hẹn.")) && setApptOpen(false)}>
              Đặt lịch
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Field label="Loại">
            {(p) => (
              <Select {...p} value={appt.loai} onChange={(e) => setAppt({ ...appt, loai: e.target.value })}>
                <option value="hoc_thu">Học thử</option>
                <option value="tu_van">Tư vấn</option>
              </Select>
            )}
          </Field>
          <Field label="Thời gian">
            {(p) => <Input {...p} type="datetime-local" value={appt.thoi_gian} onChange={(e) => setAppt({ ...appt, thoi_gian: e.target.value })} />}
          </Field>
          {appt.loai === "hoc_thu" && (
            <Field label="Lớp học thử">
              {(p) => (
                <Select {...p} value={appt.lop_hoc_id} onChange={(e) => setAppt({ ...appt, lop_hoc_id: e.target.value })}>
                  <option value="">Chọn lớp</option>
                  {classes?.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.ma_lop} · {c.khoa_hoc}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}
        </div>
      </Dialog>

      <Dialog
        open={convertOpen}
        onClose={() => setConvertOpen(false)}
        title="Tạo hồ sơ học viên"
        description="Dùng họ tên, email và số điện thoại của khách. Sau đó bạn có thể ghi danh khách vào lớp."
        footer={
          <>
            <Button variant="ghost" onClick={() => setConvertOpen(false)}>
              Huỷ
            </Button>
            <Button variant="primary" loading={busy === "conv"}
              onClick={async () => (await run("conv", `/leads/${l.id}/convert`, { nam_sinh: Number(conv.nam_sinh), thanh_pho: conv.thanh_pho }, "Đã tạo hồ sơ học viên.")) && setConvertOpen(false)}>
              Tạo hồ sơ
            </Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Năm sinh">
            {(p) => <Input {...p} inputMode="numeric" value={conv.nam_sinh} onChange={(e) => setConv({ ...conv, nam_sinh: e.target.value })} />}
          </Field>
          <Field label="Thành phố">
            {(p) => <Input {...p} value={conv.thanh_pho} onChange={(e) => setConv({ ...conv, thanh_pho: e.target.value })} />}
          </Field>
        </div>
      </Dialog>
    </>
  );
}
