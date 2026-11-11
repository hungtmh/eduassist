"use client";

import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { Badge, Card, EmptyState, ErrorBox, PageHeader, Segmented, Spinner, Table, td, th } from "@/components/ui";
import { fmtDateTime } from "@/lib/format";

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

function brief(v: unknown): string {
  if (v == null) return "";
  const s = JSON.stringify(v);
  return s.length > 140 ? `${s.slice(0, 140)}…` : s;
}

export default function AuditPage() {
  const [scope, setScope] = useState<"all" | "agent">("all");
  const { data, error, mutate } = useSWR<Row[]>(`/audit?limit=200${scope === "agent" ? "&chi_agent=true" : ""}`);
  return (
    <>
      <PageHeader title="Nhật ký kiểm toán" description="Ai (người hay agent nào), làm gì, trên đối tượng nào, giá trị trước và sau, vì sao, ai duyệt. Không sửa hay xoá được." />
      <div className="mb-4">
        <Segmented
          label="Phạm vi nhật ký"
          value={scope}
          onChange={setScope}
          options={[
            { value: "all", label: "Tất cả" },
            { value: "agent", label: "Do agent thực hiện" },
          ]}
        />
      </div>
      {error && <ErrorBox error={error} onRetry={() => mutate()} />}
      <Card>
        {!data ? (
          <Spinner />
        ) : data.length === 0 ? (
          <EmptyState title="Chưa có bản ghi nào" />
        ) : (
          <Table label="Nhật ký kiểm toán">
            <thead>
              <tr>
                <th className={th}>Thời điểm</th>
                <th className={th}>Ai</th>
                <th className={th}>Hành động</th>
                <th className={th}>Chi tiết</th>
              </tr>
            </thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.id} className="hover:bg-surface-hover">
                  <td className={`${td} num whitespace-nowrap text-fg-secondary`}>{fmtDateTime(r.created_at)}</td>
                  <td className={td}>
                    <p className="flex flex-wrap items-center gap-1.5 font-medium">
                      {r.actor.replace("agent:", "")}
                      {r.actor.startsWith("agent:") && <Badge tone="agent">agent</Badge>}
                    </p>
                    <p className="text-xs text-fg-tertiary">{r.actor_role}</p>
                  </td>
                  <td className={td}>
                    <p>{r.hanh_dong.replaceAll("_", " ")}</p>
                    <p className="text-xs text-fg-tertiary">
                      {r.doi_tuong}
                      {r.doi_tuong_id ? ` #${r.doi_tuong_id}` : ""}
                    </p>
                  </td>
                  <td className={`${td} max-w-md`}>
                    {r.ly_do && <p className="text-pretty">{r.ly_do}</p>}
                    {r.sau != null && <p className="font-mono text-xs break-all text-fg-secondary">{brief(r.sau)}</p>}
                    {r.de_xuat_id && (
                      <p className="mt-1 text-xs">
                        <Link href={`/inbox?id=${r.de_xuat_id}`} className="text-accent-fg hover:underline">
                          Đề xuất #{r.de_xuat_id}
                        </Link>
                        {r.duyet_boi && <span className="text-fg-tertiary"> · duyệt bởi {r.duyet_boi}</span>}
                      </p>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </>
  );
}
