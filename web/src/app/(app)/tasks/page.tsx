"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { Badge, Button, Card, EmptyState, ErrorBox, PageHeader, Segmented, Spinner, useToast } from "@/components/ui";
import { api } from "@/lib/api";
import { daysFrom, fmtDate } from "@/lib/format";

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

export default function TasksPage() {
  const [mine, setMine] = useState<"1" | "0">("1");
  const { data, error, mutate } = useSWR<Task[]>(`/tasks?mine=${mine === "1"}`);
  const toast = useToast();
  async function done(t: Task) {
    try {
      await api(`/tasks/${t.id}/done`, { method: "POST" });
      toast(`Đã xong: ${t.tieu_de}`);
      mutate();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Không cập nhật được.", "danger");
    }
  }
  return (
    <>
      <PageHeader title="Việc cần làm" description="Việc do agent tuyển sinh giao (khách quá 3 ngày chưa liên hệ) và việc bạn tự tạo." />
      <div className="mb-4">
        <Segmented
          label="Phạm vi"
          value={mine}
          onChange={setMine}
          options={[
            { value: "1", label: "Của tôi" },
            { value: "0", label: "Cả nhóm" },
          ]}
        />
      </div>
      {error && <ErrorBox error={error} onRetry={() => mutate()} />}
      <Card>
        {!data ? (
          <Spinner />
        ) : data.length === 0 ? (
          <EmptyState title="Không còn việc nào" description="Việc mới sẽ xuất hiện khi agent phát hiện khách cần liên hệ." />
        ) : (
          <ul>
            {data.map((t) => {
              const overdue = daysFrom(t.han) < 0;
              return (
                <li key={t.id} className="flex flex-wrap items-start gap-3 border-b border-line px-4 py-3 last:border-0">
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-2 font-medium">
                      {t.loai_doi_tuong === "khach_tiem_nang" && t.doi_tuong_id ? (
                        <Link href={`/leads/${t.doi_tuong_id}`} className="hover:underline">
                          {t.tieu_de}
                        </Link>
                      ) : (
                        t.tieu_de
                      )}
                      {t.created_by.startsWith("agent:") && <Badge tone="agent">agent giao</Badge>}
                      {overdue && <Badge tone="danger">Quá hạn</Badge>}
                    </p>
                    <p className="mt-0.5 text-fg-secondary text-pretty">{t.mo_ta}</p>
                    <p className="num mt-0.5 text-xs text-fg-tertiary">
                      Hạn {fmtDate(t.han)}
                      {mine === "0" && ` · ${t.nguoi_phu_trach ?? "chưa phân"}`}
                    </p>
                  </div>
                  <Button size="sm" onClick={() => done(t)}>
                    <Check className="size-4" aria-hidden />
                    Đánh dấu xong
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </>
  );
}
