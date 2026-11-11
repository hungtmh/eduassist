"use client";

import { ArrowLeft, ClipboardList } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
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
  cx,
  td,
  th,
  useToast,
} from "@/components/ui";
import { api } from "@/lib/api";
import { daysFrom, fmtDate, fmtWeekday, vnd } from "@/lib/format";
import { ATTENDANCE, CLASS_STATUS, ENROLL_STATUS, SHIFT } from "@/lib/labels";
import type { ClassRow } from "../page";

type Detail = ClassRow & {
  buoi: { id: number; so_thu_tu: number; ngay: string; trang_thai: string; da_diem_danh: number }[];
  hoc_vien: {
    don_hang_id: number;
    hoc_vien_id: number;
    ho_ten: string;
    email: string;
    trang_thai: string;
    trang_thai_hoc: string;
    con_no: number;
    so_buoi_vang: number;
    so_buoi_diem_danh: number;
  }[];
};

type Roster = { id: number; ngay: string; so_thu_tu: number; hoc_vien: { don_hang_id: number; ho_ten: string; trang_thai: string | null }[] };

function AttendanceDialog({ sessionId, onClose, onDone }: { sessionId: number | null; onClose: () => void; onDone: () => void }) {
  const { data } = useSWR<Roster>(sessionId ? `/sessions/${sessionId}` : null);
  const toast = useToast();
  const [marks, setMarks] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (data) setMarks(Object.fromEntries(data.hoc_vien.map((h) => [h.don_hang_id, h.trang_thai ?? "co_mat"])));
  }, [data]);
  async function save() {
    if (!sessionId) return;
    setBusy(true);
    try {
      const r = await api<{ vang: number }>(`/sessions/${sessionId}/attendance`, {
        body: { entries: Object.entries(marks).map(([k, v]) => ({ don_hang_id: Number(k), trang_thai: v })) },
      });
      toast(r.vang ? `Đã lưu điểm danh, ${r.vang} học viên vắng. Agent chăm sóc sẽ xem xét học viên vắng liên tiếp.` : "Đã lưu điểm danh.");
      onDone();
      onClose();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Không lưu được.", "danger");
    } finally {
      setBusy(false);
    }
  }
  const absent = Object.values(marks).filter((v) => v === "vang").length;
  return (
    <Dialog
      open={!!sessionId}
      onClose={onClose}
      title={data ? `Điểm danh buổi ${data.so_thu_tu} · ${fmtWeekday(data.ngay)}` : "Điểm danh"}
      description="Mặc định là có mặt. Đi trễ quá 15 phút tính là vắng nửa buổi."
      wide
      footer={
        <>
          <span className="me-auto self-center text-fg-secondary">
            <span className="num">{absent}</span> vắng
          </span>
          <Button variant="ghost" onClick={onClose}>
            Huỷ
          </Button>
          <Button variant="primary" loading={busy} disabled={!data?.hoc_vien.length} onClick={save}>
            Lưu điểm danh
          </Button>
        </>
      }
    >
      {!data ? (
        <Spinner />
      ) : data.hoc_vien.length === 0 ? (
        <EmptyState title="Lớp chưa có học viên đang học" />
      ) : (
        <ul className="flex flex-col">
          {data.hoc_vien.map((h) => (
            <li key={h.don_hang_id} className="flex flex-wrap items-center justify-between gap-3 border-b border-line py-2 last:border-0">
              <span className="min-w-0 font-medium">{h.ho_ten}</span>
              <div role="radiogroup" aria-label={`Điểm danh ${h.ho_ten}`} className="flex flex-wrap gap-1">
                {Object.entries(ATTENDANCE).map(([k, [text]]) => (
                  <label
                    key={k}
                    className={cx(
                      "cursor-pointer rounded-md px-2.5 py-1 text-[0.8125rem] font-medium has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-[var(--color-focus)]",
                      marks[h.don_hang_id] === k
                        ? k === "vang"
                          ? "bg-danger-subtle text-danger-fg"
                          : k === "co_mat"
                            ? "bg-success-subtle text-success-fg"
                            : "bg-warning-subtle text-warning-fg"
                        : "bg-surface-hover text-fg-secondary",
                    )}
                  >
                    <input
                      type="radio"
                      className="sr-only"
                      name={`att-${h.don_hang_id}`}
                      checked={marks[h.don_hang_id] === k}
                      onChange={() => setMarks({ ...marks, [h.don_hang_id]: k })}
                    />
                    {text}
                  </label>
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Dialog>
  );
}

export default function ClassDetail() {
  const { id } = useParams<{ id: string }>();
  const { can } = useAuth();
  const toast = useToast();
  const { data: c, error, mutate } = useSWR<Detail>(`/classes/${id}`);
  const { data: teachers } = useSWR<{ id: number; ho_ten: string }[]>(can("class.write") ? "/teachers" : null);
  const { data: rooms } = useSWR<{ id: number; ten: string; co_so: string; suc_chua: number }[]>(can("class.write") ? "/rooms" : null);
  const [session, setSession] = useState<number | null>(null);
  const [enroll, setEnroll] = useState(false);
  const [cancel, setCancel] = useState(false);
  const [edit, setEdit] = useState(false);
  const [reason, setReason] = useState("");
  const [sched, setSched] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!c) return <Spinner />;

  async function act(path: string, body: unknown, ok: string, method = "POST") {
    setBusy(true);
    try {
      await api(path, { method, body });
      toast(ok);
      await mutate();
      return true;
    } catch (e) {
      toast(e instanceof Error ? e.message : "Không thực hiện được.", "danger");
      return false;
    } finally {
      setBusy(false);
    }
  }

  const accepting = c.trang_thai === "sap_khai_giang" || c.trang_thai === "dang_hoc";
  const markable = c.buoi.filter((b) => daysFrom(b.ngay) <= 0);

  return (
    <>
      <PageHeader
        back={
          <Link href="/classes" className="mb-2 inline-flex items-center gap-1 text-[0.8125rem] text-fg-secondary hover:text-fg">
            <ArrowLeft className="size-3.5" aria-hidden />
            Lớp học
          </Link>
        }
        title={`Lớp ${c.ma_lop}`}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <StatusBadge map={CLASS_STATUS} value={c.trang_thai} />
            {c.khoa_hoc} · {SHIFT[c.ca_hoc]} {c.lich_hoc} · {c.giang_vien}
          </span>
        }
        actions={
          <>
            {can("class.write") && c.trang_thai === "sap_khai_giang" && (
              <>
                <Button variant="ghost" onClick={() => setCancel(true)}>
                  Huỷ lớp
                </Button>
                <Button loading={busy} onClick={() => act(`/classes/${c.id}/open`, undefined, `Đã khai giảng lớp ${c.ma_lop}.`)}>
                  Khai giảng
                </Button>
              </>
            )}
            {can("class.write") && accepting && <Button onClick={() => setEdit(true)}>Đổi lịch / giảng viên</Button>}
            {can("enroll.create") && accepting && (
              <Button variant="primary" onClick={() => setEnroll(true)}>
                Ghi danh học viên
              </Button>
            )}
          </>
        }
      />

      <div className="mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Sĩ số", `${c.si_so}/${c.si_so_toi_da}`, `Tối thiểu ${c.si_so_toi_thieu} để mở lớp`],
          ["Khai giảng", fmtDate(c.ngay_khai_giang), c.ngay_ket_thuc ? `Kết thúc ${fmtDate(c.ngay_ket_thuc)}` : ""],
          ["Tiến độ", `${c.buoi_da_hoc}/${c.so_buoi} buổi`, ""],
          ["Địa điểm", c.hinh_thuc === "online" ? "Trực tuyến" : c.phong ?? "Chưa xếp phòng", c.co_so ?? ""],
        ].map(([k, v, h]) => (
          <Card key={k} as="div" className="p-4">
            <p className="text-fg-secondary">{k}</p>
            <p className="num mt-1 text-lg font-semibold">{v}</p>
            {h && <p className="text-xs text-fg-tertiary">{h}</p>}
          </Card>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,20rem)]">
        <Card>
          <CardHeader title={`Học viên (${c.hoc_vien.length})`} />
          {c.hoc_vien.length === 0 ? (
            <EmptyState title="Lớp chưa có học viên" description="Ghi danh học viên để tạo hoá đơn và các đợt thanh toán." />
          ) : (
            <Table label="Học viên của lớp">
              <thead>
                <tr>
                  <th className={th}>Học viên</th>
                  <th className={th}>Trạng thái</th>
                  <th className={`${th} text-end`}>Vắng</th>
                  {can("invoice.read") && <th className={`${th} text-end`}>Còn nợ</th>}
                </tr>
              </thead>
              <tbody>
                {c.hoc_vien.map((h) => (
                  <tr key={h.don_hang_id} className="hover:bg-surface-hover">
                    <td className={td}>
                      {can("student.read") ? (
                        <Link href={`/students/${h.hoc_vien_id}`} className="font-medium hover:underline">
                          {h.ho_ten}
                        </Link>
                      ) : (
                        <span className="font-medium">{h.ho_ten}</span>
                      )}
                    </td>
                    <td className={td}>
                      <StatusBadge map={ENROLL_STATUS} value={h.trang_thai_hoc} />
                    </td>
                    <td className={`${td} num text-end`}>
                      {h.so_buoi_vang}/{h.so_buoi_diem_danh}
                    </td>
                    {can("invoice.read") && (
                      <td className={`${td} num text-end ${h.con_no > 0 ? "font-medium" : "text-fg-tertiary"}`}>{vnd(h.con_no)}</td>
                    )}
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>

        <Card>
          <CardHeader title="Buổi học" description={can("attendance.write") ? "Chọn một buổi đã diễn ra để điểm danh." : undefined} />
          <ol className="max-h-[32rem] overflow-y-auto overscroll-contain px-2 pb-2">
            {c.buoi.map((b) => {
              const canMark = can("attendance.write") && daysFrom(b.ngay) <= 0 && c.trang_thai === "dang_hoc";
              return (
                <li key={b.id} className="flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-surface-hover">
                  <span className="num w-8 text-fg-tertiary">#{b.so_thu_tu}</span>
                  <span className="num flex-1">{fmtWeekday(b.ngay)}</span>
                  {b.da_diem_danh > 0 ? (
                    <Badge tone="success">Đã điểm danh</Badge>
                  ) : daysFrom(b.ngay) === 0 ? (
                    <Badge tone="accent">Hôm nay</Badge>
                  ) : null}
                  {canMark && (
                    <Button size="sm" variant="ghost" onClick={() => setSession(b.id)} aria-label={`Điểm danh buổi ${b.so_thu_tu}`}>
                      <ClipboardList className="size-4" aria-hidden />
                    </Button>
                  )}
                </li>
              );
            })}
          </ol>
          {markable.length === 0 && <p className="px-4 pb-4 text-fg-secondary">Chưa có buổi nào diễn ra.</p>}
        </Card>
      </div>

      <AttendanceDialog sessionId={session} onClose={() => setSession(null)} onDone={() => mutate()} />
      <EnrollDialog open={enroll} onClose={() => setEnroll(false)} onDone={() => mutate()} classId={c.id} />

      <Dialog
        open={cancel}
        onClose={() => setCancel(false)}
        title={`Huỷ lớp ${c.ma_lop}?`}
        description={`${c.si_so} ghi danh sẽ bị huỷ và mỗi khoản đã đóng tạo một yêu cầu hoàn 100% chờ kế toán duyệt. Không khôi phục được lớp sau khi huỷ.`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setCancel(false)}>
              Giữ lớp
            </Button>
            <Button variant="danger" loading={busy} disabled={reason.trim().length < 3}
              onClick={async () => (await act(`/classes/${c.id}/cancel`, { ly_do: reason }, `Đã huỷ lớp ${c.ma_lop}.`)) && setCancel(false)}>
              Huỷ lớp và tạo yêu cầu hoàn phí
            </Button>
          </>
        }
      >
        <Field label="Lý do huỷ">{(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Không đủ sĩ số tối thiểu" />}</Field>
      </Dialog>

      <Dialog
        open={edit}
        onClose={() => setEdit(false)}
        title="Đổi lịch / giảng viên / phòng"
        description="Các buổi chưa học được xếp lại theo lịch mới. Hệ thống từ chối nếu trùng lịch giảng viên hoặc phòng."
        footer={
          <>
            <Button variant="ghost" onClick={() => setEdit(false)}>
              Huỷ
            </Button>
            <Button variant="primary" loading={busy} disabled={!Object.keys(sched).length}
              onClick={async () => {
                const body = Object.fromEntries(Object.entries(sched).map(([k, v]) => [k, k.endsWith("_id") || k.startsWith("si_so") ? Number(v) : v]));
                if (await act(`/classes/${c.id}`, body, "Đã cập nhật lịch lớp.", "PATCH")) {
                  setEdit(false);
                  setSched({});
                }
              }}>
              Lưu thay đổi
            </Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Giảng viên">
            {(p) => (
              <Select {...p} value={sched.giang_vien_id ?? String(c.giang_vien_id ?? "")} onChange={(e) => setSched({ ...sched, giang_vien_id: e.target.value })}>
                {teachers?.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.ho_ten}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Phòng">
            {(p) => (
              <Select {...p} value={sched.phong_hoc_id ?? String(c.phong_hoc_id ?? "")} onChange={(e) => setSched({ ...sched, phong_hoc_id: e.target.value })}>
                <option value="">Trực tuyến / chưa xếp</option>
                {rooms?.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.co_so} · {r.ten} ({r.suc_chua})
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Ca học">
            {(p) => (
              <Select {...p} value={sched.ca_hoc ?? c.ca_hoc} onChange={(e) => setSched({ ...sched, ca_hoc: e.target.value })}>
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
              <Select {...p} value={sched.lich_hoc ?? c.lich_hoc} onChange={(e) => setSched({ ...sched, lich_hoc: e.target.value })}>
                {["T2-T4-T6", "T3-T5-T7", "T7-CN"].map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </Select>
            )}
          </Field>
        </div>
      </Dialog>
    </>
  );
}
