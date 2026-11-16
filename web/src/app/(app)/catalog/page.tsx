"use client";

import { Plus } from "lucide-react";
import { useEffect, useState } from "react";
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
  Table,
  Textarea,
  td,
  th,
} from "@/components/ui";
import { api } from "@/lib/api";
import { vnd } from "@/lib/format";

type Course = {
  id: number;
  ma: string;
  ten: string;
  danh_muc: string;
  trinh_do: string;
  hoc_phi: number;
  so_buoi: number;
  mo_ta: string;
  dang_mo_ban: boolean;
  so_lop_dang_mo: number;
  slug: string;
  mo_ta_ngan: string | null;
  doi_tuong: string | null;
  ket_qua: string | null;
  lo_trinh: { ten: string; noi_dung: string }[];
};

// Lộ trình nhập dạng chữ: mỗi dòng một giai đoạn "Tên giai đoạn: nội dung"
const phasesToText = (ps: { ten: string; noi_dung: string }[]) => ps.map((p) => (p.noi_dung ? `${p.ten}: ${p.noi_dung}` : p.ten)).join("\n");
const textToPhases = (t: string) =>
  t
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => {
      const i = l.indexOf(":");
      return i > 0 ? { ten: l.slice(0, i).trim(), noi_dung: l.slice(i + 1).trim() } : { ten: l, noi_dung: "" };
    });
type Branch = { id: number; ten: string; dia_chi: string; so_phong: number };
type Room = { id: number; ten: string; suc_chua: number; co_so_id: number; co_so: string };
type Teacher = {
  id: number;
  ho_ten: string;
  email: string;
  chuyen_mon: string;
  username: string | null;
  tieu_su: string | null;
  hien_thi_cong_khai: boolean;
};

/** Hộp thoại form dùng chung: giữ giá trị, gọi API, hiện lỗi nghiệp vụ nguyên văn. */
function useForm<T extends Record<string, string | boolean>>(initial: T) {
  const [f, setF] = useState<T>(initial);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof T) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setF((v) => ({ ...v, [k]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value }));
  async function run(fn: () => Promise<unknown>, onOk: () => void) {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      onOk();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Không lưu được.");
    } finally {
      setBusy(false);
    }
  }
  return { f, setF, set, err, setErr, busy, run };
}

function FormError({ err }: { err: string | null }) {
  return err ? (
    <p role="alert" className="mt-4 rounded-lg bg-danger-subtle px-3 py-2 text-danger-fg">
      {err}
    </p>
  ) : null;
}

const digits = (s: string) => Number(s.replace(/\D/g, ""));

// ---------------------------------------------------------------- khoá học
function CourseDialog({ course, open, onClose, onSaved }: { course: Course | null; open: boolean; onClose: () => void; onSaved: () => void }) {
  const { data: opts } = useSWR<{ danh_muc: string[]; trinh_do: string[] }>(open ? "/courses/options" : null);
  const empty = {
    ma: "", ten: "", danh_muc: "", trinh_do: "", hoc_phi: "", so_buoi: "", mo_ta: "", dang_mo_ban: true,
    slug: "", mo_ta_ngan: "", doi_tuong: "", ket_qua: "", lo_trinh: "",
  };
  const fromCourse = (c: Course) => ({
    ma: c.ma,
    ten: c.ten,
    danh_muc: c.danh_muc,
    trinh_do: c.trinh_do,
    hoc_phi: String(c.hoc_phi),
    so_buoi: String(c.so_buoi),
    mo_ta: c.mo_ta,
    dang_mo_ban: c.dang_mo_ban,
    slug: c.slug,
    mo_ta_ngan: c.mo_ta_ngan ?? "",
    doi_tuong: c.doi_tuong ?? "",
    ket_qua: c.ket_qua ?? "",
    lo_trinh: phasesToText(c.lo_trinh ?? []),
  });
  const form = useForm(course ? fromCourse(course) : empty);
  const { f, set, err, busy, run } = form;
  useEffect(() => {
    if (!open) return;
    form.setF(course ? fromCourse(course) : empty);
    form.setErr(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, course?.id]);

  function save() {
    const body = {
      ten: f.ten, danh_muc: f.danh_muc, trinh_do: f.trinh_do, hoc_phi: digits(f.hoc_phi), so_buoi: digits(f.so_buoi),
      mo_ta: f.mo_ta, dang_mo_ban: f.dang_mo_ban, slug: f.slug.trim() || null, mo_ta_ngan: f.mo_ta_ngan.trim() || null,
      doi_tuong: f.doi_tuong.trim() || null, ket_qua: f.ket_qua.trim() || null, lo_trinh: textToPhases(f.lo_trinh),
    };
    run(
      () => (course ? api(`/courses/${course.id}`, { method: "PATCH", body }) : api("/courses", { body: { ...body, ma: f.ma } })),
      () => {
        onSaved();
        onClose();
      },
    );
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      wide
      title={course ? `Sửa khoá ${course.ma}` : "Thêm khoá học"}
      description={course ? "Đổi học phí chỉ áp dụng cho ghi danh mới; học viên đã ghi danh giữ giá cũ." : undefined}
      footer={
        <>
          <Button onClick={onClose}>Huỷ</Button>
          <Button variant="primary" loading={busy} onClick={save}>
            Lưu
          </Button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Mã khoá" hint={course ? "Không đổi được" : "VD: ENG-B1"}>
          {(p) => <Input {...p} value={f.ma} disabled={!!course} onChange={set("ma")} className="font-mono uppercase" />}
        </Field>
        <Field label="Tên khoá học" className="sm:col-span-2">
          {(p) => <Input {...p} value={f.ten} onChange={set("ten")} />}
        </Field>
        <Field label="Danh mục">
          {(p) => (
            <Select {...p} value={f.danh_muc} onChange={set("danh_muc")}>
              <option value="">Chọn…</option>
              {opts?.danh_muc.map((d) => (
                <option key={d}>{d}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Trình độ">
          {(p) => (
            <Select {...p} value={f.trinh_do} onChange={set("trinh_do")}>
              <option value="">Chọn…</option>
              {opts?.trinh_do.map((d) => (
                <option key={d}>{d}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Số buổi">{(p) => <Input {...p} inputMode="numeric" value={f.so_buoi} onChange={set("so_buoi")} />}</Field>
        <Field label="Học phí trọn khoá (đồng)" hint={f.hoc_phi ? vnd(digits(f.hoc_phi)) : undefined}>
          {(p) => <Input {...p} inputMode="numeric" value={f.hoc_phi} onChange={set("hoc_phi")} />}
        </Field>
        <label className="flex items-center gap-2 self-end pb-2 sm:col-span-2">
          <input type="checkbox" checked={f.dang_mo_ban} onChange={set("dang_mo_ban")} className="size-4 accent-accent-solid" />
          Đang mở bán (bỏ chọn: không mở lớp mới, Copilot không giới thiệu khoá này)
        </label>
        <Field label="Mô tả" className="sm:col-span-3">
          {(p) => <Textarea {...p} value={f.mo_ta} onChange={set("mo_ta")} />}
        </Field>
      </div>
      <fieldset className="mt-6 border-t border-line pt-4">
        <legend className="pe-2 font-semibold">Trang khoá học trên website</legend>
        <div className="mt-3 grid gap-4 sm:grid-cols-3">
          <Field label="Đường dẫn" hint={`/khoa-hoc/${f.slug || f.ma.toLowerCase() || "…"}`}>
            {(p) => <Input {...p} value={f.slug} onChange={set("slug")} placeholder={f.ma.toLowerCase()} className="font-mono" />}
          </Field>
          <Field label="Mô tả ngắn (thẻ khoá học, Google)" className="sm:col-span-2">
            {(p) => <Input {...p} value={f.mo_ta_ngan} onChange={set("mo_ta_ngan")} maxLength={200} />}
          </Field>
          <Field label="Phù hợp với ai">{(p) => <Textarea {...p} value={f.doi_tuong} onChange={set("doi_tuong")} maxLength={500} className="min-h-20" />}</Field>
          <Field label="Kết quả sau khoá" className="sm:col-span-2">
            {(p) => <Textarea {...p} value={f.ket_qua} onChange={set("ket_qua")} maxLength={500} className="min-h-20" />}
          </Field>
          <Field label="Lộ trình" hint="Mỗi dòng một giai đoạn, dạng: Tên giai đoạn: nội dung" className="sm:col-span-3">
            {(p) => <Textarea {...p} value={f.lo_trinh} onChange={set("lo_trinh")} />}
          </Field>
        </div>
        {f.dang_mo_ban && course && (
          <a href={`/khoa-hoc/${f.slug || course.slug}`} target="_blank" rel="noopener noreferrer" className="mt-3 inline-block text-[0.8125rem] font-medium text-accent-fg hover:underline">
            Xem trang công khai ↗
          </a>
        )}
      </fieldset>
      <FormError err={err} />
    </Dialog>
  );
}

function CoursesTab() {
  const { can } = useAuth();
  const { data, error, mutate } = useSWR<Course[]>("/courses");
  const [edit, setEdit] = useState<{ course: Course | null } | null>(null);
  const editable = can("course.write");
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return <Spinner />;
  return (
    <Card>
      <CardHeader
        title={`Khoá học (${data.length})`}
        description={editable ? undefined : "Chỉ quản lý thêm, sửa khoá học."}
        action={
          editable && (
            <Button variant="primary" size="sm" onClick={() => setEdit({ course: null })}>
              <Plus className="size-4" aria-hidden />
              Thêm khoá
            </Button>
          )
        }
      />
      {data.length === 0 ? (
        <EmptyState title="Chưa có khoá học" description="Thêm khoá học đầu tiên để mở lớp và ghi danh." />
      ) : (
        <Table label="Danh sách khoá học">
          <thead>
            <tr>
              <th className={th}>Khoá học</th>
              <th className={th}>Danh mục</th>
              <th className={`${th} text-end`}>Học phí</th>
              <th className={`${th} text-end`}>Buổi</th>
              <th className={`${th} text-end`}>Lớp đang mở</th>
              <th className={th}>Trạng thái</th>
              {editable && (
                <th className={th}>
                  <span className="sr-only">Thao tác</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {data.map((c) => (
              <tr key={c.id}>
                <td className={td}>
                  <p className="font-medium">{c.ten}</p>
                  <p className="font-mono text-xs text-fg-tertiary">{c.ma}</p>
                </td>
                <td className={td}>
                  {c.danh_muc}
                  <p className="text-xs text-fg-tertiary">{c.trinh_do}</p>
                </td>
                <td className={`${td} num text-end`}>{vnd(c.hoc_phi)}</td>
                <td className={`${td} num text-end`}>{c.so_buoi}</td>
                <td className={`${td} num text-end`}>{c.so_lop_dang_mo}</td>
                <td className={td}>{c.dang_mo_ban ? <Badge tone="success">Đang bán</Badge> : <Badge>Ngừng bán</Badge>}</td>
                {editable && (
                  <td className={`${td} text-end`}>
                    <Button size="sm" onClick={() => setEdit({ course: c })}>
                      Sửa
                    </Button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <CourseDialog course={edit?.course ?? null} open={!!edit} onClose={() => setEdit(null)} onSaved={() => mutate()} />
    </Card>
  );
}

// ---------------------------------------------------------------- cơ sở & phòng
function BranchDialog({ branch, open, onClose, onSaved }: { branch: Branch | null; open: boolean; onClose: () => void; onSaved: () => void }) {
  const form = useForm({ ten: branch?.ten ?? "", dia_chi: branch?.dia_chi ?? "" });
  useEffect(() => {
    if (!open) return;
    form.setF({ ten: branch?.ten ?? "", dia_chi: branch?.dia_chi ?? "" });
    form.setErr(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, branch?.id]);
  const { f, set, err, busy, run } = form;
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={branch ? "Sửa cơ sở" : "Thêm cơ sở"}
      footer={
        <>
          <Button onClick={onClose}>Huỷ</Button>
          <Button
            variant="primary"
            loading={busy}
            onClick={() =>
              run(() => (branch ? api(`/branches/${branch.id}`, { method: "PUT", body: f }) : api("/branches", { body: f })), () => {
                onSaved();
                onClose();
              })
            }
          >
            Lưu
          </Button>
        </>
      }
    >
      <div className="grid gap-4">
        <Field label="Tên cơ sở">{(p) => <Input {...p} value={f.ten} onChange={set("ten")} />}</Field>
        <Field label="Địa chỉ">{(p) => <Input {...p} value={f.dia_chi} onChange={set("dia_chi")} />}</Field>
      </div>
      <FormError err={err} />
    </Dialog>
  );
}

function RoomDialog({ room, branches, open, onClose, onSaved }: { room: Room | null; branches: Branch[]; open: boolean; onClose: () => void; onSaved: () => void }) {
  const init = () => ({ co_so_id: String(room?.co_so_id ?? branches[0]?.id ?? ""), ten: room?.ten ?? "", suc_chua: String(room?.suc_chua ?? "") });
  const form = useForm(init());
  useEffect(() => {
    if (!open) return;
    form.setF(init());
    form.setErr(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, room?.id]);
  const { f, set, err, busy, run } = form;
  const body = { co_so_id: Number(f.co_so_id), ten: f.ten, suc_chua: digits(f.suc_chua) };
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={room ? "Sửa phòng học" : "Thêm phòng học"}
      footer={
        <>
          <Button onClick={onClose}>Huỷ</Button>
          <Button
            variant="primary"
            loading={busy}
            onClick={() =>
              run(() => (room ? api(`/rooms/${room.id}`, { method: "PUT", body }) : api("/rooms", { body })), () => {
                onSaved();
                onClose();
              })
            }
          >
            Lưu
          </Button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Cơ sở" className="sm:col-span-3">
          {(p) => (
            <Select {...p} value={f.co_so_id} onChange={set("co_so_id")}>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.ten}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Tên phòng" className="sm:col-span-2">
          {(p) => <Input {...p} value={f.ten} onChange={set("ten")} />}
        </Field>
        <Field label="Sức chứa">{(p) => <Input {...p} inputMode="numeric" value={f.suc_chua} onChange={set("suc_chua")} />}</Field>
      </div>
      <FormError err={err} />
    </Dialog>
  );
}

function PlacesTab() {
  const { can } = useAuth();
  const branches = useSWR<Branch[]>("/branches");
  const rooms = useSWR<Room[]>("/rooms");
  const [branch, setBranch] = useState<{ b: Branch | null } | null>(null);
  const [room, setRoom] = useState<{ r: Room | null } | null>(null);
  if (branches.error) return <ErrorBox error={branches.error} onRetry={() => branches.mutate()} />;
  if (!branches.data || !rooms.data) return <Spinner />;
  const refresh = () => {
    branches.mutate();
    rooms.mutate();
  };
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
      <Card>
        <CardHeader
          title={`Cơ sở (${branches.data.length})`}
          action={
            can("course.write") && (
              <Button size="sm" variant="primary" onClick={() => setBranch({ b: null })}>
                <Plus className="size-4" aria-hidden />
                Thêm
              </Button>
            )
          }
        />
        <ul className="px-4 pb-4">
          {branches.data.length === 0 && <li className="text-fg-secondary">Chưa có cơ sở. Thêm cơ sở trước khi thêm phòng.</li>}
          {branches.data.map((b) => (
            <li key={b.id} className="flex items-start justify-between gap-3 border-b border-line py-2.5 last:border-0">
              <span className="min-w-0">
                <span className="block font-medium">{b.ten}</span>
                <span className="block text-xs text-fg-tertiary">
                  {b.dia_chi} · {b.so_phong} phòng
                </span>
              </span>
              {can("course.write") && (
                <Button size="sm" variant="ghost" onClick={() => setBranch({ b })}>
                  Sửa
                </Button>
              )}
            </li>
          ))}
        </ul>
      </Card>
      <Card>
        <CardHeader
          title={`Phòng học (${rooms.data.length})`}
          action={
            can("class.write") &&
            branches.data.length > 0 && (
              <Button size="sm" variant="primary" onClick={() => setRoom({ r: null })}>
                <Plus className="size-4" aria-hidden />
                Thêm
              </Button>
            )
          }
        />
        <Table label="Danh sách phòng học">
          <thead>
            <tr>
              <th className={th}>Phòng</th>
              <th className={th}>Cơ sở</th>
              <th className={`${th} text-end`}>Sức chứa</th>
              <th className={th}>
                <span className="sr-only">Thao tác</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rooms.data.map((r) => (
              <tr key={r.id}>
                <td className={`${td} font-medium`}>{r.ten}</td>
                <td className={td}>{r.co_so}</td>
                <td className={`${td} num text-end`}>{r.suc_chua}</td>
                <td className={`${td} text-end`}>
                  {can("class.write") && (
                    <Button size="sm" variant="ghost" onClick={() => setRoom({ r })}>
                      Sửa
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
      <BranchDialog branch={branch?.b ?? null} open={!!branch} onClose={() => setBranch(null)} onSaved={refresh} />
      <RoomDialog room={room?.r ?? null} branches={branches.data} open={!!room} onClose={() => setRoom(null)} onSaved={refresh} />
    </div>
  );
}

// ---------------------------------------------------------------- giảng viên
function TeacherDialog({ teacher, open, onClose, onSaved }: { teacher: Teacher | null; open: boolean; onClose: () => void; onSaved: () => void }) {
  const init = () => ({
    ho_ten: teacher?.ho_ten ?? "",
    email: teacher?.email ?? "",
    chuyen_mon: teacher?.chuyen_mon ?? "",
    tieu_su: teacher?.tieu_su ?? "",
    hien_thi_cong_khai: teacher?.hien_thi_cong_khai ?? true,
  });
  const form = useForm(init());
  useEffect(() => {
    if (!open) return;
    form.setF(init());
    form.setErr(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, teacher?.id]);
  const { f, set, err, busy, run } = form;
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={teacher ? "Sửa giảng viên" : "Thêm giảng viên"}
      description="Tài khoản đăng nhập của giảng viên cấp ở trang Người dùng (vai trò Giảng viên, gắn hồ sơ này)."
      footer={
        <>
          <Button onClick={onClose}>Huỷ</Button>
          <Button
            variant="primary"
            loading={busy}
            onClick={() =>
              run(() => (teacher ? api(`/teachers/${teacher.id}`, { method: "PUT", body: f }) : api("/teachers", { body: f })), () => {
                onSaved();
                onClose();
              })
            }
          >
            Lưu
          </Button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Họ tên">{(p) => <Input {...p} value={f.ho_ten} onChange={set("ho_ten")} />}</Field>
        <Field label="Email">{(p) => <Input {...p} type="email" value={f.email} onChange={set("email")} />}</Field>
        <Field label="Chuyên môn" className="sm:col-span-2">
          {(p) => <Input {...p} value={f.chuyen_mon} onChange={set("chuyen_mon")} placeholder="VD: IELTS, Tiếng Anh giao tiếp" />}
        </Field>
        <Field label="Giới thiệu ngắn (hiện trên website)" className="sm:col-span-2">
          {(p) => <Textarea {...p} value={f.tieu_su} onChange={set("tieu_su")} maxLength={1000} className="min-h-20" />}
        </Field>
        <label className="flex items-center gap-2 sm:col-span-2">
          <input type="checkbox" checked={f.hien_thi_cong_khai} onChange={set("hien_thi_cong_khai")} className="size-4 accent-accent-solid" />
          Hiện tên và giới thiệu trên website công khai
        </label>
      </div>
      <FormError err={err} />
    </Dialog>
  );
}

function TeachersTab() {
  const { can } = useAuth();
  const { data, error, mutate } = useSWR<Teacher[]>("/teachers");
  const [edit, setEdit] = useState<{ t: Teacher | null } | null>(null);
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return <Spinner />;
  return (
    <Card>
      <CardHeader
        title={`Giảng viên (${data.length})`}
        action={
          can("class.write") && (
            <Button size="sm" variant="primary" onClick={() => setEdit({ t: null })}>
              <Plus className="size-4" aria-hidden />
              Thêm giảng viên
            </Button>
          )
        }
      />
      <Table label="Danh sách giảng viên">
        <thead>
          <tr>
            <th className={th}>Giảng viên</th>
            <th className={th}>Chuyên môn</th>
            <th className={th}>Tài khoản</th>
            <th className={th}>
              <span className="sr-only">Thao tác</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {data.map((t) => (
            <tr key={t.id}>
              <td className={td}>
                <p className="font-medium">{t.ho_ten}</p>
                <p className="text-xs text-fg-tertiary">{t.email}</p>
              </td>
              <td className={td}>{t.chuyen_mon}</td>
              <td className={td}>{t.username ? <span className="font-mono">{t.username}</span> : <Badge>Chưa có</Badge>}</td>
              <td className={`${td} text-end`}>
                {can("class.write") && (
                  <Button size="sm" variant="ghost" onClick={() => setEdit({ t })}>
                    Sửa
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
      <TeacherDialog teacher={edit?.t ?? null} open={!!edit} onClose={() => setEdit(null)} onSaved={() => mutate()} />
    </Card>
  );
}

type Tab = "courses" | "places" | "teachers";

export default function CatalogPage() {
  const [tab, setTab] = useState<Tab>("courses");
  return (
    <>
      <PageHeader
        eyebrow="Quản trị"
        title="Danh mục đào tạo"
        description="Khoá học, cơ sở, phòng học và giảng viên. Mọi thay đổi được ghi vào nhật ký kiểm toán."
      />
      <div className="mb-4">
        <Segmented
          label="Chọn danh mục"
          value={tab}
          onChange={setTab}
          options={[
            { value: "courses", label: "Khoá học" },
            { value: "places", label: "Cơ sở & phòng" },
            { value: "teachers", label: "Giảng viên" },
          ]}
        />
      </div>
      {tab === "courses" && <CoursesTab />}
      {tab === "places" && <PlacesTab />}
      {tab === "teachers" && <TeachersTab />}
    </>
  );
}
