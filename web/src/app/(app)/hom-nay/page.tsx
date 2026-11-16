"use client";

import { AlertTriangle, CalendarClock, CheckCircle2, ClipboardList, Inbox, Phone, Users, Wallet } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import useSWR from "swr";
import { useAuth } from "@/components/providers";
import { Badge, Card, CardHeader, ErrorBox, PageHeader, Spinner, Stat } from "@/components/ui";
import { fmtDateTime, fmtWeekday, relDay, vnd } from "@/lib/format";
import { SHIFT } from "@/lib/labels";

type Session = {
  id: number;
  ngay: string;
  so_thu_tu: number;
  lop_hoc_id: number;
  ma_lop: string;
  ca_hoc: string;
  hinh_thuc: string;
  khoa_hoc: string;
  so_buoi: number;
  phong: string | null;
  co_so: string | null;
  giang_vien: string | null;
  si_so: number;
  da_diem_danh: boolean;
};
type MyDay = {
  ngay: string;
  viec_den_han: { id: number; tieu_de: string; han: string; loai_doi_tuong: string | null; doi_tuong_id: number | null; ten_khach: string | null }[];
  so_viec_den_han: number;
  de_xuat_cho_duyet: number;
  giang_day?: { hom_nay: Session[]; tuan_toi: Session[]; chua_diem_danh: Session[] };
  tuyen_sinh?: {
    khach_moi_24h: number;
    qua_han_lien_he: number;
    lich_hen: { id: number; loai: string; thoi_gian: string; khach_id: number; ho_ten: string; so_dien_thoai: string }[];
  };
  tai_chinh?: { den_han_hom_nay: number; so_dot_hom_nay: number; qua_han: number; hoc_vien_qua_han: number; da_thu_hom_nay: number; hoan_phi_cho_duyet: number };
  giao_vu?: {
    buoi_hom_nay: Session[];
    yeu_cau_moi: number;
    lop_thieu_si_so: { id: number; ma_lop: string; khoa_hoc: string; ngay_khai_giang: string; si_so: number; si_so_toi_thieu: number }[];
  };
};

const where = (s: Session) => (s.hinh_thuc === "online" ? "Online" : [s.phong, s.co_so].filter(Boolean).join(" · ") || "Chưa xếp phòng");

function SessionRow({ s, showTeacher, showDay }: { s: Session; showTeacher?: boolean; showDay?: boolean }) {
  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-line px-4 py-3 last:border-0">
      <span className="w-20 shrink-0 font-medium">
        {showDay ? <span className="block first-letter:uppercase">{fmtWeekday(s.ngay)}</span> : null}
        <span className={showDay ? "text-xs text-fg-tertiary" : ""}>Ca {SHIFT[s.ca_hoc]?.toLowerCase()}</span>
      </span>
      <span className="min-w-0 flex-1">
        <Link href={`/classes/${s.lop_hoc_id}`} className="font-medium hover:underline">
          {s.ma_lop}
        </Link>
        <span className="text-fg-secondary"> · {s.khoa_hoc}</span>
        <span className="block text-xs text-fg-tertiary">
          Buổi {s.so_thu_tu}/{s.so_buoi} · {where(s)} · {s.si_so} học viên{showTeacher && s.giang_vien ? ` · ${s.giang_vien}` : ""}
        </span>
      </span>
      {s.da_diem_danh ? <Badge tone="success">Đã điểm danh</Badge> : null}
    </li>
  );
}

function Section({ title, description, children, action }: { title: string; description?: ReactNode; children: ReactNode; action?: ReactNode }) {
  return (
    <Card>
      <CardHeader title={title} description={description} action={action} />
      {children}
    </Card>
  );
}

const Empty = ({ children }: { children: ReactNode }) => (
  <p className="flex items-center gap-2 px-4 pb-4 text-fg-secondary">
    <CheckCircle2 className="size-4 text-success-fg" aria-hidden />
    {children}
  </p>
);

export default function MyDayPage() {
  const { user } = useAuth();
  const { data: d, error, mutate } = useSWR<MyDay>("/me/today", { refreshInterval: 120_000 });
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!d) return <Spinner />;
  const hour = new Date().getHours();
  const hello = hour < 11 ? "Chào buổi sáng" : hour < 14 ? "Chào buổi trưa" : hour < 18 ? "Chào buổi chiều" : "Chào buổi tối";

  return (
    <>
      <PageHeader eyebrow="Việc hôm nay" title={`${hello}, ${user?.display_name.split(" ").at(-1)}`} description="Những việc cần làm hôm nay của bạn, tự cập nhật mỗi 2 phút." />

      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Link href="/tasks" className="block rounded-xl [&>div]:h-full [&>div]:transition-shadow hover:[&>div]:shadow-lift">
          <Stat label="Việc đến hạn" value={d.so_viec_den_han} tone={d.so_viec_den_han ? "warning" : undefined} hint="Gồm cả việc quá hạn" />
        </Link>
        {d.de_xuat_cho_duyet > 0 || user?.permissions.includes("chat.data") ? (
          <Link href="/inbox" className="block rounded-xl [&>div]:h-full [&>div]:transition-shadow hover:[&>div]:shadow-lift">
            <Stat label="Đề xuất chờ bạn duyệt" value={d.de_xuat_cho_duyet} tone={d.de_xuat_cho_duyet ? "agent" : undefined} hint="Từ các agent" />
          </Link>
        ) : null}
        {d.giang_day && (
          <div>
            <Stat label="Buổi dạy hôm nay" value={d.giang_day.hom_nay.length} hint={`${d.giang_day.tuan_toi.length} buổi trong 6 ngày tới`} />
          </div>
        )}
        {d.tuyen_sinh && (
          <>
            <Link href="/leads" className="block rounded-xl [&>div]:h-full [&>div]:transition-shadow hover:[&>div]:shadow-lift">
              <Stat label="Khách quá 3 ngày chưa gọi" value={d.tuyen_sinh.qua_han_lien_he} tone={d.tuyen_sinh.qua_han_lien_he ? "danger" : undefined} />
            </Link>
            <Link href="/leads" className="block rounded-xl [&>div]:h-full [&>div]:transition-shadow hover:[&>div]:shadow-lift">
              <Stat label="Khách mới 24 giờ qua" value={d.tuyen_sinh.khach_moi_24h} />
            </Link>
          </>
        )}
        {d.tai_chinh && (
          <>
            <Link href="/finance" className="block rounded-xl [&>div]:h-full [&>div]:transition-shadow hover:[&>div]:shadow-lift">
              <Stat label="Đến hạn hôm nay" value={vnd(d.tai_chinh.den_han_hom_nay)} hint={`${d.tai_chinh.so_dot_hom_nay} đợt thanh toán`} />
            </Link>
            <Link href="/finance" className="block rounded-xl [&>div]:h-full [&>div]:transition-shadow hover:[&>div]:shadow-lift">
              <Stat label="Nợ quá hạn" value={vnd(d.tai_chinh.qua_han)} tone="danger" hint={`${d.tai_chinh.hoc_vien_qua_han} học viên`} />
            </Link>
          </>
        )}
        {d.giao_vu && (
          <Link href="/requests" className="block rounded-xl [&>div]:h-full [&>div]:transition-shadow hover:[&>div]:shadow-lift">
            <Stat label="Yêu cầu học viên mới" value={d.giao_vu.yeu_cau_moi} tone={d.giao_vu.yeu_cau_moi ? "warning" : undefined} />
          </Link>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {d.giang_day && (
          <>
            <Section title="Lịch dạy hôm nay" description="Bấm vào lớp để điểm danh">
              {d.giang_day.hom_nay.length ? (
                <ul>{d.giang_day.hom_nay.map((s) => <SessionRow key={s.id} s={s} />)}</ul>
              ) : (
                <Empty>Hôm nay bạn không có buổi dạy.</Empty>
              )}
            </Section>
            {d.giang_day.chua_diem_danh.length > 0 && (
              <Section title={`Buổi chưa điểm danh (${d.giang_day.chua_diem_danh.length})`} description="Trong 14 ngày qua. Agent chăm sóc cần điểm danh để phát hiện học viên nghỉ nhiều.">
                <ul>{d.giang_day.chua_diem_danh.map((s) => <SessionRow key={s.id} s={s} showDay />)}</ul>
              </Section>
            )}
            <Section title="6 ngày tới" action={<Link href="/lich" className="text-[0.8125rem] font-medium text-accent-fg hover:underline">Xem thời khoá biểu</Link>}>
              {d.giang_day.tuan_toi.length ? (
                <ul>{d.giang_day.tuan_toi.map((s) => <SessionRow key={s.id} s={s} showDay />)}</ul>
              ) : (
                <Empty>Không có buổi dạy trong 6 ngày tới.</Empty>
              )}
            </Section>
          </>
        )}

        {d.tuyen_sinh && (
          <Section title="Lịch hẹn hôm nay" description="Tư vấn và học thử chưa ghi kết quả">
            {d.tuyen_sinh.lich_hen.length ? (
              <ul>
                {d.tuyen_sinh.lich_hen.map((h) => (
                  <li key={h.id} className="flex items-center gap-3 border-b border-line px-4 py-3 last:border-0">
                    <CalendarClock className="size-4 shrink-0 text-fg-tertiary" aria-hidden />
                    <span className="num w-12 shrink-0 font-medium">{fmtDateTime(h.thoi_gian).slice(0, 5)}</span>
                    <Link href={`/leads/${h.khach_id}`} className="min-w-0 flex-1 truncate font-medium hover:underline">
                      {h.ho_ten}
                    </Link>
                    <Badge tone={h.loai === "hoc_thu" ? "accent" : "neutral"}>{h.loai === "hoc_thu" ? "Học thử" : "Tư vấn"}</Badge>
                    <a href={`tel:${h.so_dien_thoai}`} className="inline-flex size-8 items-center justify-center rounded-lg hover:bg-surface-hover" aria-label={`Gọi ${h.ho_ten}`}>
                      <Phone className="size-4" aria-hidden />
                    </a>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty>Không có lịch hẹn nào hôm nay.</Empty>
            )}
          </Section>
        )}

        {d.tai_chinh && (
          <Section title="Tiền hôm nay">
            <dl className="grid grid-cols-2 gap-4 px-4 pb-4">
              <div>
                <dt className="text-fg-secondary">Đã ghi nhận thu</dt>
                <dd className="num text-lg font-semibold">{vnd(d.tai_chinh.da_thu_hom_nay)}</dd>
              </div>
              <div>
                <dt className="text-fg-secondary">Hoàn phí chờ duyệt</dt>
                <dd className="num text-lg font-semibold">
                  {d.tai_chinh.hoan_phi_cho_duyet ? <Link href="/finance" className="hover:underline">{d.tai_chinh.hoan_phi_cho_duyet} yêu cầu</Link> : "Không có"}
                </dd>
              </div>
            </dl>
          </Section>
        )}

        {d.giao_vu && (
          <>
            <Section title={`Buổi học hôm nay (${d.giao_vu.buoi_hom_nay.length})`} action={<Link href="/lich" className="text-[0.8125rem] font-medium text-accent-fg hover:underline">Thời khoá biểu</Link>}>
              {d.giao_vu.buoi_hom_nay.length ? (
                <ul className="max-h-96 overflow-y-auto">{d.giao_vu.buoi_hom_nay.map((s) => <SessionRow key={s.id} s={s} showTeacher />)}</ul>
              ) : (
                <Empty>Hôm nay không có buổi học nào.</Empty>
              )}
            </Section>
            <Section title="Lớp sắp khai giảng còn thiếu sĩ số" description="Khai giảng trong 14 ngày tới">
              {d.giao_vu.lop_thieu_si_so.length ? (
                <ul>
                  {d.giao_vu.lop_thieu_si_so.map((l) => (
                    <li key={l.id} className="flex items-center gap-3 border-b border-line px-4 py-3 last:border-0">
                      <AlertTriangle className="size-4 shrink-0 text-warning-fg" aria-hidden />
                      <span className="min-w-0 flex-1">
                        <Link href={`/classes/${l.id}`} className="font-medium hover:underline">{l.ma_lop}</Link>
                        <span className="block text-xs text-fg-tertiary">{l.khoa_hoc} · khai giảng {relDay(l.ngay_khai_giang)}</span>
                      </span>
                      <span className="num inline-flex items-center gap-1 text-fg-secondary">
                        <Users className="size-4" aria-hidden />
                        {l.si_so}/{l.si_so_toi_thieu}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty>Các lớp sắp mở đều đủ sĩ số tối thiểu.</Empty>
              )}
            </Section>
          </>
        )}

        <Section title="Việc được giao đến hạn" action={<Link href="/tasks" className="text-[0.8125rem] font-medium text-accent-fg hover:underline">Sổ việc</Link>}>
          {d.viec_den_han.length ? (
            <ul>
              {d.viec_den_han.map((t) => (
                <li key={t.id} className="flex items-center gap-3 border-b border-line px-4 py-3 last:border-0">
                  <ClipboardList className="size-4 shrink-0 text-fg-tertiary" aria-hidden />
                  <span className="min-w-0 flex-1">
                    {t.loai_doi_tuong === "khach_tiem_nang" && t.doi_tuong_id ? (
                      <Link href={`/leads/${t.doi_tuong_id}`} className="font-medium hover:underline">{t.tieu_de}</Link>
                    ) : (
                      <span className="font-medium">{t.tieu_de}</span>
                    )}
                  </span>
                  <span className="text-xs text-fg-tertiary">{relDay(t.han)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty>Không có việc nào đến hạn.</Empty>
          )}
        </Section>

        {d.de_xuat_cho_duyet > 0 && (
          <Section title="Agent đang chờ bạn">
            <p className="flex items-center gap-2 px-4 pb-4">
              <Inbox className="size-4 text-agent-fg" aria-hidden />
              <Link href="/inbox" className="font-medium hover:underline">{d.de_xuat_cho_duyet} đề xuất chờ duyệt</Link>
            </p>
          </Section>
        )}
        {d.tai_chinh && d.tai_chinh.qua_han > 0 && (
          <Section title="Nhắc nợ">
            <p className="flex items-center gap-2 px-4 pb-4 text-fg-secondary">
              <Wallet className="size-4" aria-hidden />
              Agent công nợ nhắc theo bậc mỗi sáng; xem <Link href="/finance" className="font-medium text-accent-fg hover:underline">thang nhắc nợ</Link>.
            </p>
          </Section>
        )}
      </div>
    </>
  );
}
