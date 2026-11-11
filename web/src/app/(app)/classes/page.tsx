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
  td,
  th,
  useToast,
} from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { CLASS_STATUS, SHIFT } from "@/lib/labels";

export type ClassRow = {
  id: number;
  ma_lop: string;
  khoa_hoc: string;
  khoa_hoc_id: number;
  hoc_phi: number;
  so_buoi: number;
  ngay_khai_giang: string;
  ngay_ket_thuc: string | null;
  ca_hoc: string;
  lich_hoc: string;
  hinh_thuc: string;
  si_so: number;
  si_so_toi_da: number;
  si_so_toi_thieu: number;
  trang_thai: string;
  giang_vien: string;
  giang_vien_id: number | null;
  phong: string | null;
  phong_hoc_id: number | null;
  co_so: string | null;
  buoi_da_hoc: number;
};

const DAYS = ["T2-T4-T6", "T3-T5-T7", "T7-CN"];

function NewClassDialog({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const { data: courses } = useSWR<{ id: number; ten: string }[]>(open ? "/courses" : null);
  const { data: teachers } = useSWR<{ id: number; ho_ten: string; chuyen_mon: string }[]>(open ? "/teachers" : null);
  const { data: rooms } = useSWR<{ id: number; ten: string; suc_chua: number; co_so: string }[]>(open ? "/rooms" : null);
  const [f, setF] = useState({
    khoa_hoc_id: "",
    ngay_khai_giang: "",
    ca_hoc: "toi",
    lich_hoc: "T2-T4-T6",
    hinh_thuc: "offline",
    si_so_toi_da: "20",
    si_so_toi_thieu: "8",
    giang_vien_id: "",
    phong_hoc_id: "",
  });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      const r = await api<{ ma_lop: string }>("/classes", {
        body: {
          ...f,
          khoa_hoc_id: Number(f.khoa_hoc_id),
          si_so_toi_da: Number(f.si_so_toi_da),
          si_so_toi_thieu: Number(f.si_so_toi_thieu),
          giang_vien_id: f.giang_vien_id ? Number(f.giang_vien_id) : null,
          phong_hoc_id: f.hinh_thuc === "offline" && f.phong_hoc_id ? Number(f.phong_hoc_id) : null,
        },
      });
      toast(`Đã mở lớp ${r.ma_lop} và tạo lịch các buổi học.`);
      onDone();
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Không tạo được lớp.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Mở lớp mới"
      description="Hệ thống từ chối nếu giảng viên hoặc phòng đã có lớp khác cùng ca, cùng ngày trong tuần."
      wide
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Huỷ
          </Button>
          <Button variant="primary" loading={busy} disabled={!f.khoa_hoc_id || !f.ngay_khai_giang} onClick={submit}>
            Tạo lớp
          </Button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Khoá học" className="sm:col-span-2">
          {(p) => (
            <Select {...p} value={f.khoa_hoc_id} onChange={set("khoa_hoc_id")}>
              <option value="">Chọn khoá học</option>
              {courses?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.ten}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Ngày khai giảng">{(p) => <Input {...p} type="date" value={f.ngay_khai_giang} onChange={set("ngay_khai_giang")} />}</Field>
        <Field label="Ca học">
          {(p) => (
            <Select {...p} value={f.ca_hoc} onChange={set("ca_hoc")}>
              {Object.entries(SHIFT).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Lịch trong tuần">
          {(p) => (
            <Select {...p} value={f.lich_hoc} onChange={set("lich_hoc")}>
              {DAYS.map((d) => (
                <option key={d}>{d}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Hình thức">
          {(p) => (
            <Select {...p} value={f.hinh_thuc} onChange={set("hinh_thuc")}>
              <option value="offline">Tại trung tâm</option>
              <option value="online">Trực tuyến</option>
            </Select>
          )}
        </Field>
        <Field label="Sĩ số tối đa">{(p) => <Input {...p} inputMode="numeric" value={f.si_so_toi_da} onChange={set("si_so_toi_da")} />}</Field>
        <Field label="Sĩ số tối thiểu để mở lớp">{(p) => <Input {...p} inputMode="numeric" value={f.si_so_toi_thieu} onChange={set("si_so_toi_thieu")} />}</Field>
        <Field label="Giảng viên">
          {(p) => (
            <Select {...p} value={f.giang_vien_id} onChange={set("giang_vien_id")}>
              <option value="">Chưa phân công</option>
              {teachers?.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.ho_ten} · {t.chuyen_mon}
                </option>
              ))}
            </Select>
          )}
        </Field>
        {f.hinh_thuc === "offline" && (
          <Field label="Phòng">
            {(p) => (
              <Select {...p} value={f.phong_hoc_id} onChange={set("phong_hoc_id")}>
                <option value="">Chọn phòng</option>
                {rooms?.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.co_so} · {r.ten} ({r.suc_chua} chỗ)
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}
      </div>
      {err && (
        <p role="alert" className="mt-4 rounded-lg bg-danger-subtle px-3 py-2 text-danger-fg">
          {err}
        </p>
      )}
    </Dialog>
  );
}

export default function ClassesPage() {
  const { can, user } = useAuth();
  const [status, setStatus] = useState(user?.role === "teacher" ? "dang_hoc" : "");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const params = new URLSearchParams({ ...(status ? { trang_thai: status } : {}), ...(q ? { q } : {}) });
  const { data, error, mutate } = useSWR<ClassRow[]>(`/classes?${params}`);
  return (
    <>
      <PageHeader
        title={user?.role === "teacher" ? "Lớp của tôi" : "Lớp học"}
        description="Sĩ số tính theo ghi danh còn hiệu lực (chờ thanh toán, đang học, tạm dừng)."
        actions={
          can("class.write") && (
            <Button variant="primary" onClick={() => setOpen(true)}>
              <Plus className="size-4" aria-hidden />
              Mở lớp mới
            </Button>
          )
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Segmented
          label="Lọc theo trạng thái"
          value={status}
          onChange={setStatus}
          options={[{ value: "", label: "Tất cả" }, ...Object.entries(CLASS_STATUS).map(([k, [v]]) => ({ value: k, label: v }))]}
        />
        <div className="relative min-w-56 flex-1 sm:max-w-xs">
          <Search className="pointer-events-none absolute start-3 top-2.5 size-4 text-fg-tertiary" aria-hidden />
          <label htmlFor="class-q" className="sr-only">
            Tìm lớp
          </label>
          <Input id="class-q" type="search" className="ps-9" placeholder="Mã lớp hoặc tên khoá" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      {error && <ErrorBox error={error} onRetry={() => mutate()} />}
      <Card>
        {!data ? (
          <Spinner />
        ) : data.length === 0 ? (
          <EmptyState title="Không có lớp nào khớp bộ lọc" action={<Button onClick={() => { setStatus(""); setQ(""); }}>Xoá bộ lọc</Button>} />
        ) : (
          <Table label="Danh sách lớp">
            <thead>
              <tr>
                <th className={th}>Lớp</th>
                <th className={th}>Trạng thái</th>
                <th className={th}>Lịch</th>
                <th className={th}>Giảng viên · phòng</th>
                <th className={`${th} text-end`}>Sĩ số</th>
                <th className={`${th} text-end`}>Tiến độ</th>
              </tr>
            </thead>
            <tbody>
              {data.map((c) => (
                <tr key={c.id} className="hover:bg-surface-hover">
                  <td className={td}>
                    <Link href={`/classes/${c.id}`} className="font-medium hover:underline">
                      {c.ma_lop}
                    </Link>
                    <p className="text-fg-tertiary">{c.khoa_hoc}</p>
                  </td>
                  <td className={td}>
                    <div className="flex flex-col items-start gap-1">
                      <StatusBadge map={CLASS_STATUS} value={c.trang_thai} />
                      {c.trang_thai === "sap_khai_giang" && c.si_so < c.si_so_toi_thieu && <Badge tone="warning">Thiếu sĩ số</Badge>}
                    </div>
                  </td>
                  <td className={td}>
                    <p>
                      {SHIFT[c.ca_hoc]} {c.lich_hoc}
                    </p>
                    <p className="num text-fg-tertiary">Khai giảng {fmtDate(c.ngay_khai_giang)}</p>
                  </td>
                  <td className={td}>
                    <p>{c.giang_vien}</p>
                    <p className="text-fg-tertiary">{c.hinh_thuc === "online" ? "Trực tuyến" : `${c.co_so ?? ""} · ${c.phong ?? ""}`}</p>
                  </td>
                  <td className={`${td} num text-end`}>
                    {c.si_so}/{c.si_so_toi_da}
                    <p className="text-xs text-fg-tertiary">tối thiểu {c.si_so_toi_thieu}</p>
                  </td>
                  <td className={`${td} num text-end`}>
                    {c.buoi_da_hoc}/{c.so_buoi} buổi
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
      <NewClassDialog open={open} onClose={() => setOpen(false)} onDone={() => mutate()} />
    </>
  );
}
