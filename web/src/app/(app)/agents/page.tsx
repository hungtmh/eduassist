"use client";

import { CalendarClock, Lock, Play, Zap } from "lucide-react";
import { useState } from "react";
import useSWR from "swr";
import { useAuth } from "@/components/providers";
import { Avatar, Badge, Button, Card, CardHeader, ErrorBox, Input, PageHeader, Spinner, Table, cx, td, th, useToast } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDateTime, pct } from "@/lib/format";
import { AGENT_LABEL } from "@/lib/labels";

type Agent = {
  name: string;
  label: string;
  role_label: string;
  schedule: string;
  events: string[];
  description: string;
  last_run: { bat_dau: string; trang_thai: string; so_de_xuat: number; so_tu_dong: number; tom_tat: string | null; loi: string | null } | null;
};
type RunRequest = {
  yeu_cau_id: number;
  trang_thai: "cho" | "dang_chay" | "xong" | "loi" | "bo_qua";
  tom_tat?: string | null;
  loi?: string | null;
  de_xuat?: number;
  tu_dong?: number;
};
type Policy = {
  loai_hanh_dong: string;
  ten: string;
  muc: string;
  han_muc_ngay: number;
  mo_ta: string;
  khoa_cung: boolean;
  chi_canh_bao: boolean;
  dung_hom_nay: number;
  updated_by: string;
};
type StatRow = { agent: string; tong: number; tu_dong: number; da_duyet: number; duyet_khong_sua: number; tu_choi: number; cho_duyet: number; that_bai: number };

const EVENT: Record<string, string> = {
  "lead.created": "có khách mới",
  "class.schedule_changed": "đổi lịch lớp",
  "class.created": "mở lớp",
  "attendance.marked": "điểm danh",
  "grade.recorded": "nhập điểm",
};

const LEVELS = [
  { v: "L0", name: "Gợi ý", hint: "Chỉ báo cho người" },
  { v: "L1", name: "Chờ duyệt", hint: "Người duyệt rồi mới làm" },
  { v: "L2", name: "Tự động", hint: "Tự làm trong hạn mức" },
] as const;

/** Thang 3 bậc bằng radio thật: phím mũi tên đổi bậc, trình đọc màn hình đọc đúng "1 trong 3". */
function LevelScale({ id, value, onChange, disabled, onlyL0 }: { id: string; value: string; onChange: (v: string) => void; disabled?: boolean; onlyL0?: boolean }) {
  return (
    <div role="radiogroup" aria-labelledby={`${id}-label`} className="grid grid-cols-3 gap-1 rounded-xl bg-surface-hover p-1">
      {LEVELS.map((l) => {
        const off = disabled || (onlyL0 && l.v !== "L0");
        const on = value === l.v;
        return (
          <label
            key={l.v}
            className={cx(
              "relative flex cursor-pointer flex-col rounded-lg px-2.5 py-1.5 transition-[background-color,color,box-shadow] duration-150 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus",
              on ? "bg-surface shadow-card" : "text-fg-secondary hover:text-fg",
              off && !on && "cursor-not-allowed opacity-50 hover:text-fg-secondary",
            )}
          >
            <input type="radio" name={id} value={l.v} checked={on} disabled={off} onChange={() => onChange(l.v)} className="sr-only" />
            <span className="flex items-center gap-1.5 text-[0.8125rem] font-semibold">
              <span
                aria-hidden
                className={cx(
                  "size-2 rounded-full",
                  on ? (l.v === "L2" ? "bg-success-fg" : l.v === "L1" ? "bg-warning-fg" : "bg-fg-secondary") : "bg-line-strong",
                )}
              />
              {l.v} · {l.name}
            </span>
            <span className="hidden text-[0.6875rem] text-fg-tertiary sm:block">{l.hint}</span>
          </label>
        );
      })}
    </div>
  );
}

function PolicyItem({ p, editable, onSaved }: { p: Policy; editable: boolean; onSaved: () => void }) {
  const toast = useToast();
  const [level, setLevel] = useState(p.muc);
  const [limit, setLimit] = useState(String(p.han_muc_ngay));
  const [busy, setBusy] = useState(false);
  const dirty = level !== p.muc || Number(limit) !== p.han_muc_ngay;
  const id = `lv-${p.loai_hanh_dong}`;
  async function save() {
    setBusy(true);
    try {
      await api(`/autonomy/${p.loai_hanh_dong}`, { method: "PUT", body: { muc: level, han_muc_ngay: Number(limit) } });
      toast(`Đã đặt “${p.ten}” ở mức ${level}.`);
      onSaved();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Không lưu được.", "danger");
    } finally {
      setBusy(false);
    }
  }
  if (p.khoa_cung) {
    return (
      <li className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3 last:border-0">
        <div className="min-w-0 flex-1">
          <p className="font-medium">{p.ten}</p>
          <p className="max-w-[60ch] text-fg-tertiary text-pretty">{p.mo_ta}</p>
        </div>
        <span className="inline-flex -rotate-2 items-center gap-1.5 rounded-md border-2 border-danger-fg px-2 py-0.5 text-xs font-bold tracking-[0.05em] text-danger-fg uppercase">
          <Lock className="size-3.5" aria-hidden />
          Cấm vĩnh viễn
        </span>
      </li>
    );
  }
  return (
    <li className="grid gap-3 border-b border-line px-4 py-3 last:border-0 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)_7rem] lg:items-center">
      <div className="min-w-0">
        <p id={`${id}-label`} className="font-medium">
          {p.ten}
        </p>
        <p className="max-w-[60ch] text-fg-tertiary text-pretty">{p.mo_ta}</p>
        {p.chi_canh_bao && <p className="mt-1 text-xs text-fg-secondary">Thao tác này chỉ được ở mức gợi ý.</p>}
      </div>
      <LevelScale id={id} value={level} onChange={setLevel} disabled={!editable} onlyL0={p.chi_canh_bao} />
      <div className="flex items-center gap-2 lg:flex-col lg:items-end">
        {level === "L2" ? (
          editable ? (
            <span className="flex items-center gap-1.5">
              <label htmlFor={`lim-${p.loai_hanh_dong}`} className="text-xs text-fg-secondary">
                Tối đa/ngày
              </label>
              <Input id={`lim-${p.loai_hanh_dong}`} inputMode="numeric" className="w-16" value={limit} onChange={(e) => setLimit(e.target.value)} />
            </span>
          ) : (
            <span className="num text-xs text-fg-secondary">Tối đa {p.han_muc_ngay}/ngày</span>
          )
        ) : null}
        {p.muc === "L2" && <span className="num text-xs text-fg-tertiary">Hôm nay dùng {p.dung_hom_nay}/{p.han_muc_ngay}</span>}
        {editable && dirty && (
          <Button size="sm" variant="primary" loading={busy} onClick={save}>
            Lưu
          </Button>
        )}
      </div>
    </li>
  );
}

function AgentBadge({ a, canRun, running, onRun }: { a: Agent; canRun: boolean; running: boolean; onRun: () => void }) {
  const r = a.last_run;
  return (
    <article className="flex h-full flex-col overflow-hidden rounded-2xl bg-surface shadow-card">
      {/* dải trên như dây đeo thẻ nhân viên */}
      <div className="flex items-center justify-between gap-2 bg-side px-4 py-2 text-side-fg-secondary">
        <span className="text-[0.6875rem] font-medium tracking-[0.05em] uppercase">Nhân viên số</span>
        <span className="font-mono text-[0.6875rem]">agent:{a.name}</span>
      </div>
      <div className="flex flex-1 flex-col p-4">
        <div className="flex items-start gap-3">
          <Avatar name={a.label} agent size="lg" />
          <div className="min-w-0 flex-1">
            <h2 className="font-display text-xl leading-tight font-medium">{a.label}</h2>
            <p className="text-fg-secondary">Quyền như {a.role_label.toLowerCase()}</p>
          </div>
        </div>
        <p className="mt-3 text-fg-secondary text-pretty">{a.description}</p>
        <ul className="mt-3 flex flex-wrap gap-1.5 text-xs">
          <li className="inline-flex items-center gap-1 rounded-full bg-surface-hover px-2 py-0.5">
            <CalendarClock className="size-3.5" aria-hidden />
            {a.schedule === "weekly" ? "Chạy hằng tuần" : "Chạy hằng ngày"}
          </li>
          {a.events.map((e) => (
            <li key={e} className="inline-flex items-center gap-1 rounded-full bg-surface-hover px-2 py-0.5">
              <Zap className="size-3.5" aria-hidden />
              Khi {EVENT[e] ?? e}
            </li>
          ))}
        </ul>
        <div className="mt-auto pt-4">
          <div className="border-s-2 border-agent-fg/40 ps-3">
            {r ? (
              <>
                <p className="flex flex-wrap items-center gap-2 text-xs text-fg-tertiary">
                  Ca gần nhất {fmtDateTime(r.bat_dau)}
                  {r.trang_thai === "loi" && <Badge tone="danger">Lỗi</Badge>}
                </p>
                <p className="mt-0.5 text-pretty">{r.loi ?? r.tom_tat}</p>
                <p className="num mt-1 text-xs text-fg-secondary">
                  {r.so_de_xuat} đề xuất · {r.so_tu_dong} việc tự làm
                </p>
              </>
            ) : (
              <p className="text-xs text-fg-tertiary">Chưa chạy ca nào.</p>
            )}
          </div>
          {canRun && (
            <Button className="mt-4 w-full" loading={running} onClick={onRun}>
              <Play className="size-3.5" aria-hidden />
              Chạy ca ngay
            </Button>
          )}
        </div>
      </div>
    </article>
  );
}

export default function AgentsPage() {
  const { can } = useAuth();
  const toast = useToast();
  const { data: agents, error, mutate } = useSWR<Agent[]>("/agents");
  const { data: policies, mutate: mutatePolicies } = useSWR<Policy[]>("/autonomy");
  const { data: stats } = useSWR<StatRow[]>(can("report.read") ? "/agents/stats" : null);
  const [running, setRunning] = useState<string | null>(null);

  async function run(a: Agent) {
    setRunning(a.name);
    try {
      // API chỉ xếp yêu cầu vào hàng; worker chạy trong vài giây. Hỏi lại trạng thái tới khi xong (tối đa 3 phút).
      const req = await api<RunRequest>(`/agents/${a.name}/run`, { method: "POST" });
      let r = req;
      for (let i = 0; i < 90 && (r.trang_thai === "cho" || r.trang_thai === "dang_chay"); i++) {
        await new Promise((ok) => setTimeout(ok, 2000));
        r = await api<RunRequest>(`/agents/requests/${req.yeu_cau_id}`);
      }
      if (r.trang_thai === "cho" || r.trang_thai === "dang_chay")
        toast(`${a.label} vẫn đang chạy. Kết quả sẽ hiện ở thẻ agent khi xong.`);
      else if (r.trang_thai === "bo_qua") toast(`${a.label}: ${r.loi}`);
      else if (r.loi) toast(`Agent ${a.label} lỗi: ${r.loi}`, "danger");
      else toast(`${a.label}: ${r.tom_tat} (${r.de_xuat} đề xuất mới, ${r.tu_dong} việc tự thực hiện)`);
      mutate();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Không chạy được agent.", "danger");
    } finally {
      setRunning(null);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Agent & quản trị"
        title="Đội nhân viên số"
        description="Mỗi agent có vai trò riêng và chịu cùng luật, cùng phân quyền với nhân viên cùng vai trò. Bạn quyết định agent được tự làm tới đâu cho từng loại thao tác."
      />
      {error && <ErrorBox error={error} onRetry={() => mutate()} />}
      {!agents ? (
        <Spinner />
      ) : (
        <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {agents.map((a) => (
            <li key={a.name}>
              <AgentBadge a={a} canRun={can("agent.run")} running={running === a.name} onRun={() => run(a)} />
            </li>
          ))}
        </ul>
      )}

      <Card className="mt-8">
        <CardHeader
          title="Agent được tự làm tới đâu"
          description={
            can("autonomy.write")
              ? "Chọn bậc cho từng loại thao tác. Ở L2, vượt hạn mức trong ngày thì việc tự chuyển sang chờ duyệt. Các thao tác bị cấm cố định trong code, không ai mở được."
              : "Chỉ quản lý đổi được mức tự chủ."
          }
        />
        {!policies ? (
          <Spinner />
        ) : (
          <ul className="border-t border-line">
            {policies.map((p) => (
              <PolicyItem key={p.loai_hanh_dong} p={p} editable={can("autonomy.write")} onSaved={() => mutatePolicies()} />
            ))}
          </ul>
        )}
      </Card>

      {stats && stats.length > 0 && (
        <Card className="mt-6">
          <CardHeader title="Bảng chấm công 30 ngày" description="Tỉ lệ duyệt không sửa cho thấy người duyệt tin đề xuất của agent tới đâu." />
          <Table label="Thống kê đề xuất theo agent">
            <thead>
              <tr>
                <th className={th}>Agent</th>
                <th className={`${th} text-end`}>Đề xuất</th>
                <th className={`${th} text-end`}>Tự động (L2)</th>
                <th className={`${th} text-end`}>Được duyệt</th>
                <th className={`${th} text-end`}>Duyệt không sửa</th>
                <th className={`${th} text-end`}>Từ chối</th>
                <th className={`${th} text-end`}>Đang chờ</th>
              </tr>
            </thead>
            <tbody className="num">
              {stats.map((s) => (
                <tr key={s.agent}>
                  <td className={td}>
                    <span className="flex items-center gap-2">
                      <Avatar name={AGENT_LABEL[s.agent] ?? s.agent} agent size="sm" />
                      {AGENT_LABEL[s.agent] ?? s.agent}
                    </span>
                  </td>
                  <td className={`${td} text-end`}>{s.tong}</td>
                  <td className={`${td} text-end`}>{s.tu_dong}</td>
                  <td className={`${td} text-end`}>{s.da_duyet}</td>
                  <td className={`${td} text-end`}>{s.da_duyet ? pct(s.duyet_khong_sua / s.da_duyet) : "–"}</td>
                  <td className={`${td} text-end`}>{s.tu_choi}</td>
                  <td className={`${td} text-end`}>{s.cho_duyet}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </>
  );
}
