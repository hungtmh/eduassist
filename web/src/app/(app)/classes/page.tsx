"use client";

import { CalendarDays, List, Moon, Plus, Search, Sun, Sunrise } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { useAuth } from "@/components/providers";
import {
  Meter,
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorBox,
  Field,
  Input,
  LoadMore,
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
import { fmtDate, fmtDay } from "@/lib/format";
import { CLASS_STATUS, SHIFT } from "@/lib/labels";
import { usePaged } from "@/lib/use-paged";

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

const WEEK = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"] as const;
const WEEK_LABEL: Record<string, string> = { T2: "Thứ Hai", T3: "Thứ Ba", T4: "Thứ Tư", T5: "Thứ Năm", T6: "Thứ Sáu", T7: "Thứ Bảy", CN: "Chủ Nhật" };
const SHIFTS = ["sang", "chieu", "toi"] as const;
const SHIFT_ICON = { sang: Sunrise, chieu: Sun, toi: Moon } as const;

const days = (c: ClassRow) => c.lich_hoc.split("-");
const end = (c: ClassRow) => c.ngay_ket_thuc ?? "9999-12-31";
const datesOverlap = (a: ClassRow, b: ClassRow) => a.ngay_khai_giang <= end(b) && b.ngay_khai_giang <= end(a);

/** Hai lớp cùng ô (cùng ngày trong tuần + cùng ca) và giao khoảng ngày học mà chung giảng viên hoặc phòng = trùng lịch. */
function clashes(c: ClassRow, cell: ClassRow[]): string[] {
  const out = new Set<string>();
  for (const o of cell) {
    if (o.id === c.id || !datesOverlap(c, o)) continue;
    if (c.giang_vien_id && c.giang_vien_id === o.giang_vien_id) out.add(`Trùng giảng viên|${o.ma_lop}`);
    if (c.phong_hoc_id && c.phong_hoc_id === o.phong_hoc_id) out.add(`Trùng phòng|${o.ma_lop}`);
  }
  return [...out];
}

function ClassChip({ c, cell }: { c: ClassRow; cell: ClassRow[] }) {
  const upcoming = c.trang_thai === "sap_khai_giang";
  const short = upcoming && c.si_so < c.si_so_toi_thieu;
  const problems = clashes(c, cell);
  return (
    <Link
      href={`/classes/${c.id}`}
      className={cx(
        "relative block rounded-lg px-2 py-1.5 transition-[box-shadow] duration-150",
        upcoming ? "border border-dashed border-control-border bg-surface hover:shadow-card" : "border-s-[3px] border-accent-solid bg-surface shadow-card hover:shadow-lift",
        problems.length > 0 && "outline-2 outline-danger-fg",
      )}
    >
      <span className="block font-mono text-[0.6875rem] leading-snug font-medium break-all">{c.ma_lop}</span>
      <span className="flex items-baseline justify-between gap-1 text-[0.6875rem] text-fg-secondary">
        <span className="truncate">{c.hinh_thuc === "online" ? "Trực tuyến" : (c.phong ?? "Chưa có phòng")}</span>
        <span className="num shrink-0">
          {c.si_so}/{c.si_so_toi_da}
          <span className="sr-only"> học viên</span>
        </span>
      </span>
      {upcoming && <span className={cx("num block text-[0.6875rem]", short ? "font-medium text-warning-fg" : "text-fg-tertiary")}>KG {fmtDay(c.ngay_khai_giang)}{short && " · thiếu sĩ số"}</span>}
      {problems.map((p) => {
        const [what, other] = p.split("|");
        return (
          <span key={p} className="block text-[0.6875rem] font-medium text-danger-fg">
            ⚠ {what}
            <span className="sr-only"> với lớp {other}</span>
          </span>
        );
      })}
    </Link>
  );
}

function Timetable({ classes }: { classes: ClassRow[] }) {
  const live = classes.filter((c) => c.trang_thai === "dang_hoc" || c.trang_thai === "sap_khai_giang");
  const cell = (d: string, s: string) => live.filter((c) => c.ca_hoc === s && days(c).includes(d)).sort((a, b) => a.ma_lop.localeCompare(b.ma_lop));
  const todayIdx = (new Date().getDay() + 6) % 7;
  if (!live.length) return <EmptyState title="Không có lớp đang học hay sắp khai giảng" description="Đổi sang kiểu Danh sách để xem các lớp đã kết thúc." />;
  return (
    <div className="relative -mx-4 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0" role="region" aria-label="Thời khoá biểu tuần" tabIndex={0}>
      <table className="w-full min-w-[60rem] table-fixed border-separate border-spacing-1.5">
        <caption className="sr-only">Lớp theo ngày trong tuần và ca học. Viền nét đứt là lớp sắp khai giảng.</caption>
        <thead>
          <tr>
            <th className="w-20" />
            {WEEK.map((d, i) => (
              <th key={d} scope="col" className={cx("rounded-lg px-2 py-2 text-start", i === todayIdx ? "bg-fg text-surface" : "text-fg-secondary")}>
                <span className="block text-xs font-semibold">{WEEK_LABEL[d]}</span>
                {i === todayIdx && <span className="block text-[0.6875rem] font-normal opacity-80">hôm nay</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {SHIFTS.map((s) => {
            const Icon = SHIFT_ICON[s];
            return (
              <tr key={s}>
                <th scope="row" className="align-top">
                  <span className="flex flex-col items-start gap-1 px-1 pt-2 text-start text-fg-secondary">
                    <Icon className="size-4" strokeWidth={1.75} aria-hidden />
                    <span className="font-semibold">{SHIFT[s]}</span>
                  </span>
                </th>
                {WEEK.map((d, i) => {
                  const rows = cell(d, s);
                  return (
                    <td key={d} className={cx("h-28 rounded-xl p-1.5 align-top", i === todayIdx ? "bg-brand-subtle" : "bg-surface-muted")}>
                      <ul className="flex flex-col gap-1.5">
                        {rows.map((c) => (
                          <li key={c.id}>
                            <ClassChip c={c} cell={rows} />
                          </li>
                        ))}
                      </ul>
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-fg-secondary">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-4 rounded-sm border-s-[3px] border-accent-solid bg-surface shadow-card" aria-hidden />
          Đang học
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-4 rounded-sm border border-dashed border-control-border bg-surface" aria-hidden />
          Sắp khai giảng (KG)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-4 rounded-sm outline-2 outline-danger-fg" aria-hidden />
          Trùng giảng viên hoặc phòng
        </span>
      </p>
    </div>
  );
}

export default function ClassesPage() {
  const { can, user } = useAuth();
  const [view, setView] = useState<"week" | "list">("week");
  const [status, setStatus] = useState(user?.role === "teacher" ? "dang_hoc" : "");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  // Thời khoá biểu chỉ cần lớp đang học / sắp khai giảng. Danh sách đầy đủ (gồm hàng nghìn lớp đã kết thúc của
  // trung tâm lâu năm) thì tải theo trang.
  const openParams = new URLSearchParams({ con_mo: "true", ...(q ? { q } : {}) });
  const openClasses = useSWR<ClassRow[]>(`/classes?${openParams}`);
  const listParams = new URLSearchParams({ ...(status ? { trang_thai: status } : {}), ...(q ? { q } : {}) });
  const list = usePaged<ClassRow>(view === "list" ? `/classes?${listParams}` : null, 100);
  const data = view === "week" ? openClasses.data : list.items;
  const error = view === "week" ? openClasses.error : list.error;
  const mutate = () => {
    openClasses.mutate();
    list.mutate();
  };
  const running = openClasses.data?.filter((c) => c.trang_thai === "dang_hoc").length ?? 0;
  const upcoming = openClasses.data?.filter((c) => c.trang_thai === "sap_khai_giang").length ?? 0;
  return (
    <>
      <PageHeader
        eyebrow="Đào tạo"
        title={user?.role === "teacher" ? "Lịch dạy của tôi" : "Thời khoá biểu"}
        description={
          openClasses.data
            ? `${running} lớp đang học, ${upcoming} lớp sắp khai giảng. Hệ thống từ chối mở lớp nếu giảng viên hoặc phòng đã có lớp khác cùng ca, cùng ngày.`
            : undefined
        }
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
          label="Kiểu xem"
          value={view}
          onChange={setView}
          options={[
            { value: "week", label: "Theo tuần", icon: <CalendarDays className="size-3.5" aria-hidden /> },
            { value: "list", label: "Danh sách", icon: <List className="size-3.5" aria-hidden /> },
          ]}
        />
        {view === "list" && (
          <Segmented
            label="Lọc theo trạng thái"
            value={status}
            onChange={setStatus}
            options={[{ value: "", label: "Tất cả" }, ...Object.entries(CLASS_STATUS).map(([k, [v]]) => ({ value: k, label: v }))]}
          />
        )}
        <div className="relative min-w-56 flex-1 sm:max-w-xs">
          <Search className="pointer-events-none absolute start-3 top-2.5 size-4 text-fg-tertiary" aria-hidden />
          <label htmlFor="class-q" className="sr-only">
            Tìm lớp
          </label>
          <Input id="class-q" type="search" className="ps-9" placeholder="Mã lớp hoặc tên khoá" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      {error && <ErrorBox error={error} onRetry={() => mutate()} />}
      {!data ? (
        <Spinner />
      ) : view === "week" ? (
        <Timetable classes={data} />
      ) : (
        <Card>
          {data.length === 0 ? (
            <EmptyState
              title="Không có lớp nào khớp bộ lọc"
              action={
                <Button
                  onClick={() => {
                    setStatus("");
                    setQ("");
                  }}
                >
                  Xoá bộ lọc
                </Button>
              }
            />
          ) : (
            <Table label="Danh sách lớp">
              <thead>
                <tr>
                  <th className={th}>Lớp</th>
                  <th className={th}>Trạng thái</th>
                  <th className={th}>Lịch</th>
                  <th className={th}>Giảng viên · phòng</th>
                  <th className={th}>Sĩ số</th>
                  <th className={`${th} text-end`}>Tiến độ</th>
                </tr>
              </thead>
              <tbody>
                {data.map((c) => (
                  <tr key={c.id} className="hover:bg-surface-hover">
                    <td className={td}>
                      <Link href={`/classes/${c.id}`} className="font-mono font-medium hover:underline">
                        {c.ma_lop}
                      </Link>
                      <p className="text-fg-tertiary">{c.khoa_hoc}</p>
                    </td>
                    <td className={td}>
                      <StatusBadge map={CLASS_STATUS} value={c.trang_thai} />
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
                    <td className={`${td} w-40`}>
                      <Meter value={c.si_so} max={c.si_so_toi_da} mark={c.si_so_toi_thieu} tone={c.si_so < c.si_so_toi_thieu ? "warning" : "success"} />
                      <p className="num mt-1 text-xs text-fg-secondary">
                        {c.si_so}/{c.si_so_toi_da} · tối thiểu {c.si_so_toi_thieu}
                      </p>
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
      )}
      {view === "list" && data && (
        <LoadMore shown={data.length} total={list.total} noun="lớp" hasMore={list.hasMore} loading={list.loadingMore} onMore={list.loadMore} />
      )}
      <NewClassDialog open={open} onClose={() => setOpen(false)} onDone={() => mutate()} />
    </>
  );
}
