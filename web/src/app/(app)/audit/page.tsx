"use client";

import Link from "next/link";
import { useState } from "react";
import { Avatar, Badge, EmptyState, ErrorBox, PageHeader, Segmented, Spinner, LoadMore } from "@/components/ui";
import { usePaged } from "@/lib/use-paged";
import { fmtWeekday } from "@/lib/format";

type Row = {
  id: number;
  actor: string;
  actor_role: string;
  hanh_dong: string;
  doi_tuong: string;
  doi_tuong_id: string | null;
  truoc: unknown;
  sau: unknown;
  ly_do: string | null;
  de_xuat_id: number | null;
  duyet_boi: string | null;
  created_at: string;
};

const time = new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit" });

function brief(v: unknown): string {
  if (v == null) return "";
  const s = JSON.stringify(v);
  return s.length > 160 ? `${s.slice(0, 160)}…` : s;
}

function Entry({ r }: { r: Row }) {
  const agent = r.actor.startsWith("agent:");
  const who = r.actor.replace("agent:", "");
  return (
    <li className="relative grid grid-cols-[3.25rem_2.25rem_minmax(0,1fr)] gap-x-3 pb-5">
      <time dateTime={r.created_at} className="num pt-2 text-end font-mono text-xs text-fg-tertiary">
        {time.format(new Date(r.created_at))}
      </time>
      <span className="relative z-10 flex justify-center pt-0.5">
        <Avatar name={who} agent={agent} size="sm" className="ring-4 ring-canvas" />
      </span>
      <div className="min-w-0 rounded-xl bg-surface px-3.5 py-2.5 shadow-card">
        <p className="text-pretty">
          <span className="font-semibold">{who}</span>
          {agent && (
            <Badge tone="agent" className="mx-1.5 align-middle">
              agent
            </Badge>
          )}{" "}
          <span className="text-fg-secondary">{r.hanh_dong.replaceAll("_", " ")}</span>{" "}
          <span className="font-mono text-xs">
            {r.doi_tuong}
            {r.doi_tuong_id ? `#${r.doi_tuong_id}` : ""}
          </span>
        </p>
        {r.ly_do && <p className="mt-1 text-pretty">“{r.ly_do}”</p>}
        {(r.truoc != null || r.sau != null) && (
          <div className="mt-2 flex flex-col gap-0.5 rounded-lg bg-surface-muted px-2.5 py-1.5 font-mono text-[0.75rem] leading-relaxed break-all">
            {r.truoc != null && (
              <p className="text-danger-fg">
                <span aria-hidden>− </span>
                <span className="sr-only">Trước: </span>
                {brief(r.truoc)}
              </p>
            )}
            {r.sau != null && (
              <p className="text-success-fg">
                <span aria-hidden>+ </span>
                <span className="sr-only">Sau: </span>
                {brief(r.sau)}
              </p>
            )}
          </div>
        )}
        <p className="mt-1.5 text-xs text-fg-tertiary">
          Vai trò {r.actor_role}
          {r.de_xuat_id && (
            <>
              {" · "}
              <Link href={`/inbox?id=${r.de_xuat_id}`} className="font-medium text-accent-fg hover:underline">
                Đề xuất #{r.de_xuat_id}
              </Link>
            </>
          )}
          {r.duyet_boi && ` · duyệt bởi ${r.duyet_boi}`}
        </p>
      </div>
    </li>
  );
}

export default function AuditPage() {
  const [scope, setScope] = useState<"all" | "agent">("all");
  const list = usePaged<Row>(`/audit${scope === "agent" ? "?chi_agent=true" : ""}`, 100);
  const { items: data, error, mutate } = list;
  const days = new Map<string, Row[]>();
  for (const r of data ?? []) {
    const k = r.created_at.slice(0, 10);
    days.set(k, [...(days.get(k) ?? []), r]);
  }
  return (
    <>
      <PageHeader
        eyebrow="Quản trị"
        title="Nhật ký kiểm toán"
        description="Ai làm gì, trên đối tượng nào, giá trị trước và sau, vì sao, ai duyệt. Chỉ ghi thêm, không sửa hay xoá được."
        actions={
          <Segmented
            label="Phạm vi nhật ký"
            value={scope}
            onChange={setScope}
            options={[
              { value: "all", label: "Tất cả" },
              { value: "agent", label: "Chỉ agent" },
            ]}
          />
        }
      />
      {error && <ErrorBox error={error} onRetry={() => mutate()} />}
      {!data ? (
        <Spinner />
      ) : data.length === 0 ? (
        <EmptyState title="Chưa có bản ghi nào" />
      ) : (
        <div className="mx-auto max-w-4xl">
          {[...days.entries()].map(([day, rows]) => (
            <section key={day} className="mb-2">
              <h2 className="font-display sticky top-14 z-20 -mx-2 mb-3 bg-canvas/95 px-2 py-2 text-lg font-medium backdrop-blur">
                {fmtWeekday(day)}
                <span className="num ms-2 font-sans text-xs font-normal text-fg-tertiary">
                  <span className="sr-only">, </span>
                  {rows.length} thao tác
                </span>
              </h2>
              <ol className="relative before:absolute before:inset-y-0 before:start-[calc(3.25rem+0.75rem+1.125rem-1px)] before:w-0.5 before:bg-line">
                {rows.map((r) => (
                  <Entry key={r.id} r={r} />
                ))}
              </ol>
            </section>
          ))}
        </div>
      )}
      {data && (
        <LoadMore shown={data.length} total={list.total} noun="thao tác" hasMore={list.hasMore} loading={list.loadingMore} onMore={list.loadMore} />
      )}
    </>
  );
}
