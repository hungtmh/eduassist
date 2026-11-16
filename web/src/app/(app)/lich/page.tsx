"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import useSWR from "swr";
import { useAuth } from "@/components/providers";
import { Button, ErrorBox, Field, IconButton, PageHeader, Select, Spinner, cx } from "@/components/ui";
import { SHIFT } from "@/lib/labels";

type Session = {
  id: number;
  ngay: string;
  so_thu_tu: number;
  trang_thai: string;
  lop_hoc_id: number;
  ma_lop: string;
  ca_hoc: "sang" | "chieu" | "toi";
  hinh_thuc: string;
  khoa_hoc: string;
  danh_muc: string;
  so_buoi: number;
  phong: string | null;
  co_so: string | null;
  giang_vien: string | null;
  si_so: number;
  da_diem_danh: boolean;
};

const CAT_COLOR: Record<string, string> = {
  "Tiếng Anh": "var(--cat-eng)",
  "Tin học văn phòng": "var(--cat-off)",
  "Lập trình": "var(--cat-dev)",
  "Phân tích dữ liệu": "var(--cat-da)",
  "Kỹ năng mềm": "var(--cat-sk)",
};
const SHIFTS = [
  ["sang", "8h00–10h00"],
  ["chieu", "14h00–16h00"],
  ["toi", "18h30–20h30"],
] as const;

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
function mondayOf(d: Date) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  x.setDate(x.getDate() - ((x.getDay() + 6) % 7));
  return x;
}
const addDays = (d: Date, n: number) => {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
};
const dayFmt = new Intl.DateTimeFormat("vi-VN", { weekday: "short" });
const dateFmt = new Intl.DateTimeFormat("vi-VN", { day: "numeric", month: "numeric" });

function Chip({ s, showTeacher }: { s: Session; showTeacher: boolean }) {
  const past = s.ngay < iso(new Date());
  return (
    <Link
      href={`/classes/${s.lop_hoc_id}`}
      title={`${s.ma_lop} · ${s.khoa_hoc}`}
      className="block rounded-lg bg-surface px-2 py-1.5 text-xs shadow-card transition-shadow hover:shadow-lift"
      style={{ borderInlineStart: `3px solid ${CAT_COLOR[s.danh_muc] ?? "var(--color-line-strong)"}` }}
    >
      <span className="block font-semibold [overflow-wrap:anywhere]">{s.ma_lop}</span>
      <span className="block truncate text-fg-secondary">
        Buổi {s.so_thu_tu}/{s.so_buoi} · {s.hinh_thuc === "online" ? "Online" : (s.phong ?? "Chưa có phòng")}
      </span>
      {showTeacher && s.giang_vien && <span className="block truncate text-fg-tertiary">{s.giang_vien}</span>}
      {past && !s.da_diem_danh && <span className="mt-0.5 block font-medium text-warning-fg">Chưa điểm danh</span>}
    </Link>
  );
}

export default function TimetablePage() {
  const { can } = useAuth();
  const all = can("class.read");
  const [week, setWeek] = useState(() => mondayOf(new Date()));
  const [teacher, setTeacher] = useState("");
  const [room, setRoom] = useState("");
  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(week, i)), [week]);
  const qs = new URLSearchParams({ tu: iso(days[0]), den: iso(days[6]), ...(teacher && { giang_vien_id: teacher }), ...(room && { phong_hoc_id: room }) });
  const { data, error, mutate } = useSWR<Session[]>(`/schedule?${qs}`);
  const { data: teachers } = useSWR<{ id: number; ho_ten: string }[]>(all ? "/teachers" : null);
  const { data: rooms } = useSWR<{ id: number; ten: string; co_so: string }[]>(all ? "/rooms" : null);
  const today = iso(new Date());
  const cell = (d: Date, ca: string) => (data ?? []).filter((s) => s.ngay === iso(d) && s.ca_hoc === ca);
  const label = `${dateFmt.format(days[0])} – ${dateFmt.format(days[6])}/${days[6].getFullYear()}`;

  return (
    <>
      <PageHeader
        eyebrow="Đào tạo"
        title="Thời khoá biểu"
        description={all ? "Lịch các buổi học theo tuần. Lọc theo giảng viên hoặc phòng để kiểm tra trùng lịch." : "Lịch dạy của bạn theo tuần. Bấm vào buổi để điểm danh."}
      />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="flex items-center gap-1">
          <IconButton label="Tuần trước" onClick={() => setWeek((w) => addDays(w, -7))}>
            <ChevronLeft className="size-4" aria-hidden />
          </IconButton>
          <p className="num min-w-36 text-center font-semibold" aria-live="polite">
            {label}
          </p>
          <IconButton label="Tuần sau" onClick={() => setWeek((w) => addDays(w, 7))}>
            <ChevronRight className="size-4" aria-hidden />
          </IconButton>
          <Button size="sm" variant="ghost" onClick={() => setWeek(mondayOf(new Date()))}>
            Tuần này
          </Button>
        </div>
        {all && (
          <>
            <Field label="Giảng viên" className="w-52">
              {(p) => (
                <Select {...p} value={teacher} onChange={(e) => setTeacher(e.target.value)}>
                  <option value="">Tất cả</option>
                  {teachers?.map((t) => <option key={t.id} value={t.id}>{t.ho_ten}</option>)}
                </Select>
              )}
            </Field>
            <Field label="Phòng" className="w-52">
              {(p) => (
                <Select {...p} value={room} onChange={(e) => setRoom(e.target.value)}>
                  <option value="">Tất cả</option>
                  {rooms?.map((r) => <option key={r.id} value={r.id}>{r.ten} · {r.co_so}</option>)}
                </Select>
              )}
            </Field>
          </>
        )}
        {data && <p className="ms-auto text-fg-secondary">{data.length} buổi trong tuần</p>}
      </div>
      {error && <ErrorBox error={error} onRetry={() => mutate()} />}
      {!data ? (
        <Spinner />
      ) : (
        <>
          {/* Lưới tuần (màn hình rộng) */}
          <div className="hidden overflow-x-auto rounded-xl bg-surface-muted p-2 md:block" role="region" aria-label={`Thời khoá biểu tuần ${label}`} tabIndex={0}>
            <table className="w-full min-w-[56rem] table-fixed border-separate border-spacing-1">
              <thead>
                <tr>
                  <th className="w-24" scope="col"><span className="sr-only">Ca</span></th>
                  {days.map((d) => (
                    <th key={iso(d)} scope="col" className={cx("rounded-lg px-2 py-2 text-xs font-medium", iso(d) === today ? "bg-accent-solid text-white" : "text-fg-secondary")}>
                      <span className="block capitalize">{dayFmt.format(d)}</span>
                      <span className="num block">{dateFmt.format(d)}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {SHIFTS.map(([ca, time]) => (
                  <tr key={ca}>
                    <th scope="row" className="px-2 py-2 text-start align-top text-xs font-medium text-fg-secondary">
                      <span className="block text-sm text-fg">{SHIFT[ca]}</span>
                      <span className="num">{time}</span>
                    </th>
                    {days.map((d) => (
                      <td key={iso(d)} className={cx("h-24 rounded-lg p-1 align-top", iso(d) === today ? "bg-accent-subtle" : "bg-surface/60")}>
                        <div className="flex max-h-72 flex-col gap-1 overflow-y-auto">
                          {cell(d, ca).map((s) => <Chip key={s.id} s={s} showTeacher={all && !teacher} />)}
                        </div>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Danh sách theo ngày (điện thoại) */}
          <ol className="flex flex-col gap-4 md:hidden">
            {days.map((d) => {
              const rows = (data ?? []).filter((s) => s.ngay === iso(d));
              return (
                <li key={iso(d)}>
                  <h2 className={cx("mb-2 font-semibold capitalize", iso(d) === today && "text-accent-fg")}>
                    {dayFmt.format(d)} {dateFmt.format(d)}
                    {iso(d) === today && " · hôm nay"}
                  </h2>
                  {rows.length ? (
                    <div className="flex flex-col gap-2">
                      {SHIFTS.flatMap(([ca]) => cell(d, ca)).map((s) => (
                        <div key={s.id} className="flex items-start gap-3">
                          <span className="w-12 shrink-0 pt-1.5 text-xs text-fg-secondary">{SHIFT[s.ca_hoc]}</span>
                          <div className="min-w-0 flex-1"><Chip s={s} showTeacher={all && !teacher} /></div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-fg-tertiary">Không có buổi học.</p>
                  )}
                </li>
              );
            })}
          </ol>
        </>
      )}
    </>
  );
}
