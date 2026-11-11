"use client";

import { Bot } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import useSWR from "swr";
import { ProposalDetail } from "@/components/proposal";
import {
  Badge,
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorBox,
  PageHeader,
  Segmented,
  Select,
  Spinner,
  StatusBadge,
  cx,
  useToast,
} from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { AGENT_LABEL, PROPOSAL_STATUS } from "@/lib/labels";

type Row = {
  id: number;
  agent: string;
  tieu_de: string;
  ten_hanh_dong: string;
  trang_thai: string;
  muc_tu_chu: string;
  created_at: string;
  so_muc: number;
  co_the_duyet: boolean;
  nguoi_duyet: string | null;
};

type Filter = "can_xu_ly" | "da_thuc_hien" | "tu_choi" | "all";

function Inbox() {
  const params = useSearchParams();
  const router = useRouter();
  const toast = useToast();
  const [filter, setFilter] = useState<Filter>("can_xu_ly");
  const [agent, setAgent] = useState("");
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const qs = new URLSearchParams({ trang_thai: filter === "all" ? "" : filter, ...(agent ? { agent } : {}) });
  const { data, error, mutate } = useSWR<Row[]>(`/proposals?${qs}`);
  const selected = Number(params.get("id")) || data?.[0]?.id || null;

  const select = (id: number) => router.replace(`/inbox?id=${id}`, { scroll: false });
  const decidable = data?.filter((r) => r.co_the_duyet) ?? [];

  async function bulkApprove() {
    setBusy(true);
    try {
      const r = await api<{ ok: boolean }[]>("/proposals/bulk", { body: { ids: [...picked], duyet: true } });
      const ok = r.filter((x) => x.ok).length;
      toast(`Đã duyệt ${ok}/${r.length} đề xuất.`, ok === r.length ? "success" : "danger");
      setPicked(new Set());
      setConfirm(false);
      mutate();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Không duyệt được.", "danger");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Hộp duyệt"
        description="Mọi việc agent đề xuất. Việc trong hạn mức L2 đã tự thực hiện và nằm ở đây để xem lại; việc L1 chờ người có quyền quyết định."
        actions={
          picked.size > 0 && (
            <Button variant="primary" onClick={() => setConfirm(true)}>
              Duyệt {picked.size} đề xuất đã chọn
            </Button>
          )
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Segmented
          label="Lọc theo trạng thái"
          value={filter}
          onChange={(v) => {
            setFilter(v);
            setPicked(new Set());
          }}
          options={[
            { value: "can_xu_ly", label: "Cần xử lý" },
            { value: "da_thuc_hien", label: "Đã thực hiện" },
            { value: "tu_choi", label: "Đã từ chối" },
            { value: "all", label: "Tất cả" },
          ]}
        />
        <label className="sr-only" htmlFor="agent-filter">
          Lọc theo agent
        </label>
        <div className="w-full sm:w-56">
        <Select id="agent-filter" value={agent} onChange={(e) => setAgent(e.target.value)}>
          <option value="">Mọi agent</option>
          {Object.entries(AGENT_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </Select>
        </div>
        {decidable.length > 1 && (
          <button
            className="text-[0.8125rem] font-medium text-accent-fg hover:underline"
            onClick={() => setPicked(picked.size === decidable.length ? new Set() : new Set(decidable.map((r) => r.id)))}
          >
            {picked.size === decidable.length ? "Bỏ chọn tất cả" : `Chọn ${decidable.length} đề xuất duyệt được`}
          </button>
        )}
      </div>

      {error && <ErrorBox error={error} onRetry={() => mutate()} />}
      {!data && !error && <Spinner />}
      {data && data.length === 0 && (
        <Card>
          <EmptyState
            title={filter === "can_xu_ly" ? "Không còn việc cần xử lý" : "Không có đề xuất nào"}
            description="Agent chạy nền theo lịch hằng ngày và khi có sự kiện. Bạn có thể chạy ngay một agent ở trang Agent."
          />
        </Card>
      )}
      {data && data.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
          <Card className="overflow-hidden lg:sticky lg:top-20 lg:max-h-[calc(100dvh-7rem)] lg:overflow-y-auto">
            <ul aria-label="Danh sách đề xuất">
              {data.map((r) => (
                <li key={r.id} className="border-b border-line last:border-0">
                  <div className={cx("flex items-start gap-3 px-3 py-3", selected === r.id && "bg-accent-subtle")}>
                    {r.co_the_duyet ? (
                      <input
                        type="checkbox"
                        aria-label={`Chọn đề xuất ${r.tieu_de}`}
                        className="mt-1 size-4 accent-[var(--color-accent-solid)]"
                        checked={picked.has(r.id)}
                        onChange={() => {
                          const n = new Set(picked);
                          if (n.has(r.id)) n.delete(r.id);
                          else n.add(r.id);
                          setPicked(n);
                        }}
                      />
                    ) : (
                      <span className="size-4 shrink-0" aria-hidden />
                    )}
                    <button
                      onClick={() => select(r.id)}
                      aria-current={selected === r.id ? "true" : undefined}
                      className="min-w-0 flex-1 text-start"
                    >
                      <span className="flex flex-wrap items-center gap-1.5">
                        <Badge tone="agent">
                          <Bot className="size-3" aria-hidden />
                          {AGENT_LABEL[r.agent] ?? r.agent}
                        </Badge>
                        <StatusBadge map={PROPOSAL_STATUS} value={r.trang_thai} />
                      </span>
                      <span className="mt-1.5 block font-medium text-pretty">{r.tieu_de}</span>
                      <span className="mt-0.5 block text-xs text-fg-tertiary">
                        {r.ten_hanh_dong} · {fmtDateTime(r.created_at)}
                      </span>
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
          <Card className="p-5">
            {selected ? <ProposalDetail id={selected} onChanged={() => mutate()} /> : <EmptyState title="Chọn một đề xuất để xem" />}
          </Card>
        </div>
      )}

      <Dialog
        open={confirm}
        onClose={() => setConfirm(false)}
        title={`Duyệt ${picked.size} đề xuất?`}
        description="Mỗi đề xuất được thực hiện ngay sau khi duyệt (gửi email, tạm dừng học, tạo voucher…) và ghi vào nhật ký với tên bạn. Email đã gửi không thu hồi được."
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirm(false)}>
              Huỷ
            </Button>
            <Button variant="primary" loading={busy} onClick={bulkApprove}>
              Duyệt {picked.size} đề xuất
            </Button>
          </>
        }
      >
        <ul className="flex list-disc flex-col gap-1 ps-5 text-fg-secondary">
          {data
            ?.filter((r) => picked.has(r.id))
            .slice(0, 8)
            .map((r) => <li key={r.id}>{r.tieu_de}</li>)}
          {picked.size > 8 && <li>… và {picked.size - 8} đề xuất khác</li>}
        </ul>
      </Dialog>
    </>
  );
}

export default function InboxPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <Inbox />
    </Suspense>
  );
}
