"use client";

import { Columns3, List, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { useAuth } from "@/components/providers";
import { usePaged } from "@/lib/use-paged";
import {
  Avatar,
  Badge,
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorBox,
  LoadMore,
  Field,
  Input,
  PageHeader,
  Segmented,
  Select,
  Spinner,
  StatusBadge,
  Table,
  Textarea,
  td,
  th,
  cx,
  useToast,
} from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { LEAD_STATUS, SOURCE } from "@/lib/labels";

export type Lead = {
  id: number;
  ho_ten: string;
  so_dien_thoai: string;
  email: string | null;
  nguon: string;
  nhu_cau: string;
  khoa_quan_tam: string | null;
  trang_thai: string;
  phu_trach: string | null;
  ten_phu_trach: string | null;
  diem: number | null;
  so_ngay: number;
  lien_he_cuoi: string | null;
  created_at: string;
};

type Course = { id: number; ten: string };

function NewLeadDialog({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const { data: courses } = useSWR<Course[]>(open ? "/courses" : null);
  const toast = useToast();
  const [f, setF] = useState({ ho_ten: "", so_dien_thoai: "", email: "", nguon: "website", nhu_cau: "", khoa_quan_tam_id: "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api("/leads", {
        body: { ...f, email: f.email || null, khoa_quan_tam_id: f.khoa_quan_tam_id ? Number(f.khoa_quan_tam_id) : null },
      });
      toast(`Đã thêm khách ${f.ho_ten}. Agent tuyển sinh sẽ chấm điểm và gợi ý lớp.`);
      setF({ ho_ten: "", so_dien_thoai: "", email: "", nguon: "website", nhu_cau: "", khoa_quan_tam_id: "" });
      onCreated();
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Không thêm được khách.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog open={open} onClose={onClose} title="Thêm khách tiềm năng" description="Khách được tự phân cho tư vấn viên đang ít khách nhất nếu bạn không phải tư vấn viên.">
      <form id="new-lead" onSubmit={submit} className="grid gap-4 sm:grid-cols-2" noValidate>
        <Field label="Họ tên" className="sm:col-span-2">
          {(p) => <Input {...p} required autoComplete="off" value={f.ho_ten} onChange={set("ho_ten")} placeholder="Nguyễn Thị Lan" />}
        </Field>
        <Field label="Số điện thoại">
          {(p) => <Input {...p} type="tel" inputMode="tel" required value={f.so_dien_thoai} onChange={set("so_dien_thoai")} placeholder="0901234567" />}
        </Field>
        <Field label="Email" hint="Cần có để agent gửi tin tư vấn">
          {(p) => <Input {...p} type="email" value={f.email} onChange={set("email")} placeholder="lan@example.com" />}
        </Field>
        <Field label="Nguồn">
          {(p) => (
            <Select {...p} value={f.nguon} onChange={set("nguon")}>
              {Object.entries(SOURCE).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Khoá quan tâm">
          {(p) => (
            <Select {...p} value={f.khoa_quan_tam_id} onChange={set("khoa_quan_tam_id")}>
              <option value="">Chưa rõ</option>
              {courses?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.ten}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Nhu cầu" className="sm:col-span-2" hint="Càng cụ thể, agent gợi ý lớp càng đúng">
          {(p) => <Textarea {...p} rows={3} value={f.nhu_cau} onChange={set("nhu_cau")} placeholder="Muốn học IELTS buổi tối, hiện khoảng 5.0" />}
        </Field>
        {err && (
          <p role="alert" className="rounded-lg bg-danger-subtle px-3 py-2 text-danger-fg sm:col-span-2">
            {err}
          </p>
        )}
      </form>
      <div className="mt-5 flex justify-end gap-3">
        <Button variant="ghost" onClick={onClose}>
          Huỷ
        </Button>
        <Button variant="primary" type="submit" form="new-lead" loading={busy}>
          Thêm khách
        </Button>
      </div>
    </Dialog>
  );
}

function ScoreDial({ score }: { score: number | null }) {
  const r = 15;
  const c = 2 * Math.PI * r;
  return (
    <span className="relative inline-grid size-10 shrink-0 place-items-center">
      <svg viewBox="0 0 36 36" className="absolute inset-0 -rotate-90" aria-hidden>
        <circle cx="18" cy="18" r={r} fill="none" stroke="var(--color-surface-hover)" strokeWidth="3" />
        {score != null && (
          <circle
            cx="18"
            cy="18"
            r={r}
            fill="none"
            stroke="var(--color-accent-solid)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray={`${(score / 100) * c} ${c}`}
          />
        )}
      </svg>
      <span className="num text-xs font-semibold" aria-hidden>
        {score ?? "–"}
      </span>
      <span className="sr-only">{score == null ? "Chưa chấm điểm" : `Điểm tiềm năng ${score} trên 100`}</span>
    </span>
  );
}

const STAGES = ["moi", "da_lien_he", "hen_hoc_thu", "da_ghi_danh", "khong_tiep_tuc"] as const;
const STAGE_HINT: Record<string, string> = {
  moi: "Gọi trong 3 ngày",
  da_lien_he: "Mời học thử",
  hen_hoc_thu: "Chốt ghi danh",
  da_ghi_danh: "Đã thành học viên",
  khong_tiep_tuc: "Có thể liên hệ lại sau",
};

const isStale = (l: Lead) => l.trang_thai === "moi" && !l.lien_he_cuoi && l.so_ngay > 3;

function LeadCard({ l }: { l: Lead }) {
  const stale = isStale(l);
  return (
    <Link
      href={`/leads/${l.id}`}
      className={cx(
        "block rounded-xl bg-surface p-3 shadow-card transition-[box-shadow] duration-150 hover:shadow-lift",
        stale && "border-s-4 border-danger-fg",
      )}
    >
      <span className="flex items-start gap-3">
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">{l.ho_ten}</span>
          <span className="num block text-xs text-fg-tertiary">
            {SOURCE[l.nguon] ?? l.nguon} · {l.so_ngay === 0 ? "hôm nay" : `${l.so_ngay} ngày trước`}
          </span>
        </span>
        <ScoreDial score={l.diem} />
      </span>
      <span className="mt-2 line-clamp-2 block text-fg-secondary text-pretty">{l.khoa_quan_tam ?? (l.nhu_cau || "Chưa ghi nhu cầu")}</span>
      <span className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-1.5 text-xs text-fg-secondary">
          {l.ten_phu_trach && <Avatar name={l.ten_phu_trach} size="sm" />}
          <span className="truncate">{l.ten_phu_trach ?? "Chưa phân người"}</span>
        </span>
        {stale && <Badge tone="danger">Chưa gọi {l.so_ngay} ngày</Badge>}
      </span>
    </Link>
  );
}

const PER_COLUMN = 30;

type Counts = { tong: number; theo_trang_thai: Record<string, number>; qua_han_lien_he: number };

/** Một cột của bảng: tự tải theo trang. Máy chủ sắp khách quá hạn liên hệ lên đầu, rồi theo điểm. */
function BoardColumn({ st, i, q }: { st: string; i: number; q: string }) {
  const col = usePaged<Lead>(`/leads?${new URLSearchParams({ trang_thai: st, ...(q ? { q } : {}) })}`, PER_COLUMN);
  const rows = col.items ?? [];
  const [label] = LEAD_STATUS[st];
  return (
    <li className={cx("flex min-w-0 flex-col rounded-2xl p-2", st === "khong_tiep_tuc" ? "bg-surface-muted/50" : "bg-surface-muted")}>
      <div className="flex items-start justify-between gap-2 px-1.5 pt-1 pb-3">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 font-semibold">
            <span className="num grid size-5 place-items-center rounded-full bg-fg text-[0.6875rem] text-surface" aria-hidden>
              {i + 1}
            </span>
            {label}
          </h2>
          <p className="mt-0.5 text-xs text-fg-tertiary">{STAGE_HINT[st]}</p>
        </div>
        <span className="num rounded-full bg-surface px-2 py-0.5 text-xs font-medium shadow-card">
          {col.items ? col.total : "…"}
          <span className="sr-only"> khách</span>
        </span>
      </div>
      {col.error && <ErrorBox error={col.error} onRetry={() => col.mutate()} />}
      <ul className="flex flex-col gap-2">
        {rows.map((l) => (
          <li key={l.id}>
            <LeadCard l={l} />
          </li>
        ))}
        {col.items && rows.length === 0 && (
          <li className="rounded-xl border border-dashed border-line-strong px-3 py-6 text-center text-xs text-fg-tertiary">Chưa có khách ở bước này</li>
        )}
        {col.hasMore && (
          <li className="flex flex-col items-center gap-1.5 px-2 text-xs text-fg-tertiary">
            Còn {col.total - rows.length} khách khác
            <Button size="sm" loading={col.loadingMore} onClick={col.loadMore}>
              Tải thêm
            </Button>
          </li>
        )}
      </ul>
    </li>
  );
}

function Board({ q }: { q: string }) {
  return (
    <div className="relative -mx-4 overflow-x-auto px-4 pb-4 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8" role="region" aria-label="Bảng tuyển sinh theo giai đoạn" tabIndex={0}>
      <ol className="grid min-w-[68rem] grid-cols-[repeat(4,minmax(0,1fr))_minmax(0,0.85fr)] gap-3">
        {STAGES.map((st, i) => (
          <BoardColumn key={st} st={st} i={i} q={q} />
        ))}
      </ol>
    </div>
  );
}

export default function LeadsPage() {
  const { can } = useAuth();
  const [view, setView] = useState<"board" | "list">("board");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [boardKey, setBoardKey] = useState(0);
  const params = new URLSearchParams({ ...(status ? { trang_thai: status } : {}), ...(q ? { q } : {}) });
  const list = usePaged<Lead>(view === "list" ? `/leads?${params}` : null, 100);
  const { data: counts, mutate: mutateCounts } = useSWR<Counts>("/leads/counts");
  const { items: data, error } = list;
  const mutate = () => {
    list.mutate();
    mutateCounts();
  };
  const count = (s: string) => counts?.theo_trang_thai[s] ?? 0;
  const stale = counts?.qua_han_lien_he ?? 0;

  return (
    <>
      <PageHeader
        eyebrow="Tuyển sinh"
        title="Hành trình khách tiềm năng"
        description={
          <>
            Từ lúc khách để lại thông tin tới khi thành học viên. Agent tuyển sinh chấm điểm từng khách
            {stale > 0 && (
              <>
                {" "}
                và đang nhắc <span className="font-medium text-danger-fg">{stale} khách quá 3 ngày chưa ai gọi</span>
              </>
            )}
            .
          </>
        }
        actions={
          can("lead.write") && (
            <Button variant="primary" onClick={() => setOpen(true)}>
              <Plus className="size-4" aria-hidden />
              Thêm khách
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
            { value: "board", label: "Theo giai đoạn", icon: <Columns3 className="size-3.5" aria-hidden /> },
            { value: "list", label: "Danh sách", icon: <List className="size-3.5" aria-hidden /> },
          ]}
        />
        {view === "list" && (
          <Segmented
            label="Lọc theo trạng thái"
            value={status}
            onChange={setStatus}
            options={[
              { value: "", label: "Tất cả", count: counts?.tong },
              ...Object.entries(LEAD_STATUS).map(([k, [v]]) => ({ value: k, label: v, count: count(k) })),
            ]}
          />
        )}
        <div className="relative min-w-56 flex-1 sm:max-w-xs">
          <Search className="pointer-events-none absolute start-3 top-2.5 size-4 text-fg-tertiary" aria-hidden />
          <label htmlFor="lead-q" className="sr-only">
            Tìm khách
          </label>
          <Input id="lead-q" type="search" className="ps-9" placeholder="Tên, số điện thoại, email" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      {view === "board" ? (
        <Board key={boardKey} q={q} />
      ) : error ? (
        <ErrorBox error={error} onRetry={() => mutate()} />
      ) : !data ? (
        <Spinner />
      ) : data.length === 0 ? (
        <Card>
          <EmptyState
            title={q ? `Không có khách khớp “${q}”` : "Chưa có khách nào"}
            description={q ? undefined : "Khách từ form website, Zalo hay Facebook sẽ hiện ở cột Mới."}
            action={q ? <Button onClick={() => setQ("")}>Xoá tìm kiếm</Button> : undefined}
          />
        </Card>
      ) : (
        <Card>
          <Table label="Danh sách khách tiềm năng">
            <thead>
              <tr>
                <th className={th}>Khách</th>
                <th className={th}>Trạng thái</th>
                <th className={`${th} text-end`}>Điểm</th>
                <th className={th}>Quan tâm</th>
                <th className={th}>Phụ trách</th>
                <th className={th}>Ngày tạo</th>
              </tr>
            </thead>
            <tbody>
              {data.map((l) => (
                <tr key={l.id} className="hover:bg-surface-hover">
                  <td className={td}>
                    <Link href={`/leads/${l.id}`} className="font-medium hover:underline">
                      {l.ho_ten}
                    </Link>
                    <p className="num text-fg-tertiary">
                      {l.so_dien_thoai} · {SOURCE[l.nguon] ?? l.nguon}
                    </p>
                  </td>
                  <td className={td}>
                    <div className="flex flex-col items-start gap-1">
                      <StatusBadge map={LEAD_STATUS} value={l.trang_thai} />
                      {isStale(l) && <Badge tone="danger">Quá {l.so_ngay} ngày chưa liên hệ</Badge>}
                    </div>
                  </td>
                  <td className={`${td} num text-end font-medium`}>{l.diem ?? "–"}</td>
                  <td className={`${td} max-w-64`}>
                    <p className="line-clamp-2 text-fg-secondary" title={l.nhu_cau}>
                      {l.khoa_quan_tam ?? l.nhu_cau ?? "–"}
                    </p>
                  </td>
                  <td className={td}>{l.ten_phu_trach ?? "Chưa phân"}</td>
                  <td className={`${td} num`}>{fmtDate(l.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
      {view === "list" && data && (
        <LoadMore shown={data.length} total={list.total} noun="khách" hasMore={list.hasMore} loading={list.loadingMore} onMore={list.loadMore} />
      )}
      <NewLeadDialog
        open={open}
        onClose={() => setOpen(false)}
        onCreated={() => {
          mutate();
          setBoardKey((k) => k + 1);
        }}
      />
    </>
  );
}
