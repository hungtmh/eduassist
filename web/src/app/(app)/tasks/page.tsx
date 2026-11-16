"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Avatar, Badge, ErrorBox, PageHeader, Segmented, Spinner, cx, useToast, LoadMore } from "@/components/ui";
import { api } from "@/lib/api";
import { usePaged } from "@/lib/use-paged";
import { daysFrom, fmtWeekday } from "@/lib/format";

type Task = {
  id: number;
  tieu_de: string;
  mo_ta: string;
  han: string;
  nguoi_phu_trach: string | null;
  loai_doi_tuong: string | null;
  doi_tuong_id: number | null;
  created_by: string;
};

const GROUPS = [
  { key: "late", title: "Đã quá hạn", test: (d: number) => d < 0 },
  { key: "today", title: "Hôm nay", test: (d: number) => d === 0 },
  { key: "soon", title: "Sắp tới", test: (d: number) => d > 0 },
] as const;

function TaskLine({ t, showOwner, onDone }: { t: Task; showOwner: boolean; onDone: (t: Task) => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [checked, setChecked] = useState(false);
  const late = daysFrom(t.han) < 0;
  const byAgent = t.created_by.startsWith("agent:");
  return (
    <li className={cx("flex items-start gap-4 border-b border-line py-3.5 last:border-0", checked && "opacity-50")}>
      <button
        type="button"
        aria-label={`Đánh dấu xong: ${t.tieu_de}`}
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setChecked(true);
          try {
            await onDone(t);
          } catch {
            setChecked(false);
          } finally {
            setBusy(false);
          }
        }}
        className={cx(
          "pressable relative mt-0.5 grid size-6 shrink-0 place-items-center rounded-full border-2 after:absolute after:-inset-2.5",
          checked ? "border-success-fg bg-success-fg text-surface" : late ? "border-danger-fg hover:bg-danger-subtle" : "border-control-border hover:bg-surface-hover",
        )}
      >
        <Check className={cx("size-3.5", !checked && "opacity-0")} strokeWidth={3} aria-hidden />
      </button>
      <div className="min-w-0 flex-1">
        <p className={cx("font-medium text-pretty", checked && "line-through")}>
          {t.loai_doi_tuong === "khach_tiem_nang" && t.doi_tuong_id ? (
            <Link href={`/leads/${t.doi_tuong_id}`} className="hover:underline">
              {t.tieu_de}
            </Link>
          ) : (
            t.tieu_de
          )}
        </p>
        {t.mo_ta && <p className="mt-0.5 text-fg-secondary text-pretty">{t.mo_ta}</p>}
        <p className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-fg-tertiary">
          <span className={cx("num", late && "font-medium text-danger-fg")}>Hạn {fmtWeekday(t.han)}</span>
          {byAgent && <Badge tone="agent">Agent giao</Badge>}
          {showOwner && (
            <span className="inline-flex items-center gap-1">
              {t.nguoi_phu_trach && <Avatar name={t.nguoi_phu_trach} size="sm" />}
              {t.nguoi_phu_trach ?? "Chưa phân"}
            </span>
          )}
        </p>
      </div>
    </li>
  );
}

export default function TasksPage() {
  const [mine, setMine] = useState<"1" | "0">("1");
  const list = usePaged<Task>(`/tasks?mine=${mine === "1"}`, 100);
  const { items: data, error, mutate } = list;
  const toast = useToast();
  async function done(t: Task) {
    try {
      await api(`/tasks/${t.id}/done`, { method: "POST" });
      toast(`Đã xong: ${t.tieu_de}`);
      mutate();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Không cập nhật được.", "danger");
      throw e;
    }
  }
  return (
    <>
      <PageHeader
        eyebrow="Vận hành"
        title="Sổ việc"
        description="Việc agent tuyển sinh giao khi khách quá 3 ngày chưa ai liên hệ, cùng việc bạn tự ghi. Đánh dấu xong để agent biết đã có người lo."
        actions={
          <Segmented
            label="Phạm vi"
            value={mine}
            onChange={setMine}
            options={[
              { value: "1", label: "Của tôi" },
              { value: "0", label: "Cả nhóm" },
            ]}
          />
        }
      />
      {error && <ErrorBox error={error} onRetry={() => mutate()} />}
      {!data ? (
        <Spinner />
      ) : data.length === 0 ? (
        <div className="mx-auto max-w-3xl rounded-2xl bg-surface px-6 py-14 text-center shadow-card">
          <p className="font-display text-2xl">Sổ trống trơn.</p>
          <p className="mt-1 text-fg-secondary">Việc mới sẽ hiện ở đây khi agent phát hiện khách cần liên hệ.</p>
        </div>
      ) : (
        <div className="mx-auto max-w-3xl overflow-hidden rounded-2xl bg-surface shadow-card">
          {/* gáy sổ */}
          <div className="h-2 bg-[repeating-linear-gradient(90deg,var(--color-line-strong)_0_0.5rem,transparent_0.5rem_1.25rem)]" aria-hidden />
          <div className="px-5 py-4 sm:ps-16 sm:pe-8">
            {GROUPS.map((g) => {
              const rows = data.filter((t) => g.test(daysFrom(t.han)));
              if (!rows.length) return null;
              return (
                <section key={g.key} className="mb-4 last:mb-0">
                  <h2 className={cx("font-display mt-2 flex items-baseline gap-2 text-lg font-medium", g.key === "late" && "text-danger-fg")}>
                    {g.title}
                    <span className="num font-sans text-xs font-normal text-fg-tertiary">{rows.length} việc</span>
                  </h2>
                  <ul>
                    {rows.map((t) => (
                      <TaskLine key={t.id} t={t} showOwner={mine === "0"} onDone={done} />
                    ))}
                  </ul>
                </section>
              );
            })}
          </div>
        </div>
      )}
      {data && (
        <LoadMore shown={data.length} total={list.total} noun="việc" hasMore={list.hasMore} loading={list.loadingMore} onMore={list.loadMore} />
      )}
    </>
  );
}
