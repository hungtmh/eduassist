"use client";

import { Lock, Play } from "lucide-react";
import { useState } from "react";
import useSWR from "swr";
import { useAuth } from "@/components/providers";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  ErrorBox,
  Input,
  PageHeader,
  Select,
  Spinner,
  StatusBadge,
  Table,
  td,
  th,
  useToast,
} from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDateTime, pct } from "@/lib/format";
import { AGENT_LABEL, LEVEL } from "@/lib/labels";

type Agent = {
  name: string;
  label: string;
  role_label: string;
  schedule: string;
  events: string[];
  description: string;
  last_run: { bat_dau: string; trang_thai: string; so_de_xuat: number; so_tu_dong: number; tom_tat: string | null; loi: string | null } | null;
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

const EVENT = {
  "lead.created": "khách mới",
  "class.schedule_changed": "đổi lịch lớp",
  "class.created": "mở lớp",
  "attendance.marked": "điểm danh",
  "grade.recorded": "nhập điểm",
} as Record<string, string>;

function PolicyRow({ p, editable, onSaved }: { p: Policy; editable: boolean; onSaved: () => void }) {
  const toast = useToast();
  const [level, setLevel] = useState(p.muc);
  const [limit, setLimit] = useState(String(p.han_muc_ngay));
  const [busy, setBusy] = useState(false);
  const dirty = level !== p.muc || Number(limit) !== p.han_muc_ngay;
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
  const locked = p.khoa_cung || !editable;
  return (
    <tr className="hover:bg-surface-hover">
      <td className={td}>
        <p className="font-medium">{p.ten}</p>
        <p className="max-w-[48ch] text-fg-tertiary text-pretty">{p.mo_ta}</p>
      </td>
      <td className={td}>
        {locked ? (
          <span className="inline-flex items-center gap-1.5">
            <StatusBadge map={LEVEL} value={p.muc} />
            {p.khoa_cung && <Lock className="size-3.5 text-fg-tertiary" aria-label="Cố định, không cấu hình được" />}
          </span>
        ) : (
          <>
            <label htmlFor={`lv-${p.loai_hanh_dong}`} className="sr-only">
              Mức tự chủ cho {p.ten}
            </label>
            <div className="w-44">
            <Select id={`lv-${p.loai_hanh_dong}`} value={level} onChange={(e) => setLevel(e.target.value)} disabled={p.chi_canh_bao}>
              <option value="L0">L0 · Gợi ý</option>
              {!p.chi_canh_bao && <option value="L1">L1 · Chờ duyệt</option>}
              {!p.chi_canh_bao && <option value="L2">L2 · Tự động</option>}
            </Select>
            </div>
          </>
        )}
      </td>
      <td className={`${td} num`}>
        {level === "L2" && !locked ? (
          <>
            <label htmlFor={`lim-${p.loai_hanh_dong}`} className="sr-only">
              Hạn mức mỗi ngày cho {p.ten}
            </label>
            <div className="w-24">
              <Input id={`lim-${p.loai_hanh_dong}`} inputMode="numeric" value={limit} onChange={(e) => setLimit(e.target.value)} />
            </div>
          </>
        ) : p.muc === "L2" ? (
          p.han_muc_ngay
        ) : (
          "–"
        )}
        {p.muc === "L2" && <p className="mt-1 text-xs text-fg-tertiary">Hôm nay đã dùng {p.dung_hom_nay}</p>}
      </td>
      <td className={`${td} text-end`}>
        {!locked && dirty && (
          <Button size="sm" variant="primary" loading={busy} onClick={save}>
            Lưu
          </Button>
        )}
      </td>
    </tr>
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
      const r = await api<{ tom_tat?: string; loi?: string; de_xuat?: number; tu_dong?: number }>(`/agents/${a.name}/run`, { method: "POST" });
      if (r.loi) toast(`Agent ${a.label} lỗi: ${r.loi}`, "danger");
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
        title="Agent & mức tự chủ"
        description="Mỗi agent là một nhân viên số có vai trò riêng, chịu cùng luật và phân quyền với nhân viên cùng vai trò. Mức tự chủ đặt theo từng loại thao tác."
      />
      {error && <ErrorBox error={error} onRetry={() => mutate()} />}
      {!agents ? (
        <Spinner />
      ) : (
        <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {agents.map((a) => (
            <li key={a.name}>
              <Card as="article" className="flex h-full flex-col p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="font-semibold">Agent {a.label.toLowerCase()}</h2>
                    <p className="text-xs text-fg-tertiary">
                      Vai trò {a.role_label.toLowerCase()} · {a.schedule === "weekly" ? "hằng tuần" : "hằng ngày"}
                      {a.events.length > 0 && ` · khi ${a.events.map((e) => EVENT[e] ?? e).join(", ")}`}
                    </p>
                  </div>
                  {can("agent.run") && (
                    <Button size="sm" loading={running === a.name} onClick={() => run(a)}>
                      <Play className="size-3.5" aria-hidden />
                      Chạy ngay
                    </Button>
                  )}
                </div>
                <p className="mt-2 text-fg-secondary text-pretty">{a.description}</p>
                <div className="mt-auto pt-3">
                  {a.last_run ? (
                    <div className="rounded-lg bg-surface-muted px-3 py-2">
                      <p className="flex flex-wrap items-center gap-2 text-xs text-fg-tertiary">
                        Lần chạy gần nhất {fmtDateTime(a.last_run.bat_dau)}
                        {a.last_run.trang_thai === "loi" && <Badge tone="danger">Lỗi</Badge>}
                      </p>
                      <p className="mt-0.5 text-pretty">{a.last_run.loi ?? a.last_run.tom_tat}</p>
                    </div>
                  ) : (
                    <p className="text-xs text-fg-tertiary">Chưa chạy lần nào.</p>
                  )}
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}

      {stats && stats.length > 0 && (
        <Card className="mt-6">
          <CardHeader title="Hiệu quả 30 ngày" description="Tỉ lệ duyệt không sửa đo mức người duyệt tin đề xuất của agent." />
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
                  <td className={td}>{AGENT_LABEL[s.agent] ?? s.agent}</td>
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

      <Card className="mt-6">
        <CardHeader
          title="Mức tự chủ theo loại thao tác"
          description={
            can("autonomy.write")
              ? "L0 chỉ báo, L1 chờ người duyệt, L2 tự làm trong hạn mức mỗi ngày (vượt hạn mức thì chuyển sang chờ duyệt). Mức Cấm cố định trong code."
              : "Chỉ quản lý đổi được mức tự chủ."
          }
        />
        {!policies ? (
          <Spinner />
        ) : (
          <Table label="Mức tự chủ">
            <thead>
              <tr>
                <th className={th}>Thao tác</th>
                <th className={th}>Mức</th>
                <th className={th}>Hạn mức / ngày</th>
                <th className={th}>
                  <span className="sr-only">Lưu</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {policies.map((p) => (
                <PolicyRow key={p.loai_hanh_dong} p={p} editable={can("autonomy.write")} onSaved={() => mutatePolicies()} />
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </>
  );
}
