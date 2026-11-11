"use client";

import { Bot, Check, ExternalLink, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import useSWR, { mutate as refresh } from "swr";
import { Badge, Button, Field, Input, StatusBadge, Textarea, cx, useToast } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, fmtDateTime, vnd } from "@/lib/format";
import { AGENT_LABEL, LEVEL, PROPOSAL_STATUS } from "@/lib/labels";

export type Proposal = {
  id: number;
  agent: string;
  loai_hanh_dong: string;
  ten_hanh_dong: string;
  tieu_de: string;
  tom_tat: string;
  muc_tu_chu: string;
  trang_thai: string;
  nguoi_yeu_cau: string;
  nguoi_duyet: string | null;
  da_sua: boolean;
  ket_qua: string | null;
  ly_do_tu_choi?: string | null;
  du_lieu: Record<string, unknown> & { items?: Record<string, unknown>[] };
  can_cu: (string | Record<string, unknown>)[];
  truong_sua_duoc: string[];
  khoa_muc: string | null;
  co_the_duyet: boolean;
  created_at: string;
  decided_at: string | null;
  het_han_luc: string | null;
};

const FIELD_LABEL: Record<string, string> = {
  subject: "Tiêu đề email",
  body: "Nội dung email",
  loi_nhan_them: "Lời nhắn thêm (không bắt buộc)",
  phan_tram: "Mức giảm (%)",
  so_ngay: "Hiệu lực (ngày)",
};
const LONG = new Set(["body", "loi_nhan_them"]);

/** Một dòng dễ đọc cho mỗi mục trong danh sách của đề xuất (dữ liệu do code tính). */
function itemLine(it: Record<string, unknown>): string {
  const parts = [String(it.ho_ten ?? `#${it.khach_id ?? it.hoc_vien_id ?? ""}`)];
  if (it.ma_lop) parts.push(`lớp ${it.ma_lop}`);
  if (typeof it.so_tien_dot === "number") parts.push(`đợt ${it.so_thu_tu}: ${vnd(it.so_tien_dot)}`);
  else if (typeof it.con_no === "number") parts.push(`còn nợ ${vnd(it.con_no)}`);
  if (it.han) parts.push(`hạn ${fmtDate(String(it.han))}`);
  if (it.ly_do) parts.push(String(it.ly_do));
  return parts.join(" · ");
}

// Chỉ các trường có nghĩa với người duyệt; khoá kỹ thuật (id, username) không hiện
const DATA_LABEL: Record<string, [string, (v: unknown) => string]> = {
  ho_ten: ["Học viên / khách", String],
  email: ["Email", String],
  ma_lop: ["Lớp", String],
  lop_dich: ["Gộp vào lớp", String],
  so_hoc_vien: ["Số học viên", String],
  si_so: ["Sĩ số hiện tại", String],
  toi_thieu: ["Sĩ số tối thiểu", String],
  chuyen_can: ["Chuyên cần", (v) => `${Math.round(Number(v) * 100)}%`],
  so_buoi_vang_lien_tiep: ["Vắng liên tiếp", (v) => `${v} buổi`],
  so_ngay_qua_han: ["Quá hạn", (v) => `${v} ngày`],
  han: ["Hạn", (v) => fmtDate(String(v))],
  con_no: ["Còn nợ", (v) => vnd(Number(v))],
  phan_tram: ["Mức giảm", (v) => `${v}%`],
  so_ngay: ["Hiệu lực", (v) => `${v} ngày`],
  ly_do: ["Lý do", String],
  recipients: ["Người nhận", (v) => (Array.isArray(v) ? v.join(", ") : String(v))],
  lop_goi_y: ["Lớp gợi ý", (v) => (Array.isArray(v) ? v.join(", ") : String(v))],
};

function DataPreview({ p, showEmail }: { p: Proposal; showEmail: boolean }) {
  const d = p.du_lieu;
  const rows = Object.entries(DATA_LABEL).filter(([k]) => d[k] != null && d[k] !== "");
  return (
    <div className="flex flex-col gap-3">
      {typeof d.noi_dung === "string" && (
        <pre className="rounded-lg bg-surface-muted p-3 font-sans whitespace-pre-wrap text-pretty">{d.noi_dung}</pre>
      )}
      {showEmail && typeof d.subject === "string" && (
        <div className="rounded-lg bg-surface-muted p-3">
          <p className="font-medium">{d.subject}</p>
          <p className="mt-2 whitespace-pre-line text-fg-secondary text-pretty">{String(d.body ?? "")}</p>
        </div>
      )}
      {rows.length > 0 && (
        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-6 gap-y-1.5">
          {rows.map(([k, [label, fmt]]) => (
            <div key={k} className="contents">
              <dt className="text-fg-tertiary">{label}</dt>
              <dd className="num break-words">{fmt(d[k])}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

export function ProposalDetail({ id, onChanged }: { id: number; onChanged?: () => void }) {
  const { data: p, mutate } = useSWR<Proposal>(`/proposals/${id}`);
  const toast = useToast();
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [keep, setKeep] = useState<Set<unknown> | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [confirmReject, setConfirmReject] = useState(false);

  useEffect(() => {
    setEdits({});
    setKeep(null);
    setReason("");
    setConfirmReject(false);
  }, [id]);

  const items = p?.du_lieu.items;
  const keepSet = useMemo(
    () => keep ?? new Set(items?.map((i) => i[p?.khoa_muc ?? "id"]) ?? []),
    [keep, items, p?.khoa_muc],
  );

  if (!p) return <p className="p-4 text-fg-secondary">Đang tải đề xuất…</p>;

  const editable = p.truong_sua_duoc.filter((f) => f !== "keep_items");
  const changed = Object.entries(edits).filter(([k, v]) => String(p.du_lieu[k] ?? "") !== v);

  async function approve() {
    if (!p) return;
    const body: Record<string, unknown> = {};
    for (const [k, v] of changed) body[k] = k === "phan_tram" || k === "so_ngay" ? Number(v) : v;
    if (items && keepSet.size !== items.length) body.keep_items = [...keepSet];
    setBusy("approve");
    try {
      const r = await api<Proposal>(`/proposals/${p.id}/approve`, { body: { edits: Object.keys(body).length ? body : null } });
      toast(r.trang_thai === "that_bai" ? `Đã duyệt nhưng không thực hiện được: ${r.ket_qua}` : r.ket_qua ?? "Đã duyệt.",
        r.trang_thai === "that_bai" ? "danger" : "success");
      await mutate(r, { revalidate: true });
      onChanged?.();
      refresh("/proposals/counts");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Không duyệt được.", "danger");
    } finally {
      setBusy(null);
    }
  }

  async function reject() {
    if (!p) return;
    setBusy("reject");
    try {
      const r = await api<Proposal>(`/proposals/${p.id}/reject`, { body: { ly_do: reason } });
      toast("Đã từ chối đề xuất. Agent sẽ không đề xuất lại việc này.");
      await mutate(r, { revalidate: true });
      onChanged?.();
      refresh("/proposals/counts");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Không từ chối được.", "danger");
    } finally {
      setBusy(null);
    }
  }

  async function dismiss() {
    if (!p) return;
    await api(`/proposals/${p.id}/dismiss`, { method: "POST" });
    await mutate();
    onChanged?.();
    refresh("/proposals/counts");
  }

  return (
    <article className="flex flex-col gap-5">
      <header>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="agent">
            <Bot className="size-3.5" aria-hidden />
            {AGENT_LABEL[p.agent] ?? p.agent}
          </Badge>
          <StatusBadge map={PROPOSAL_STATUS} value={p.trang_thai} />
          <StatusBadge map={LEVEL} value={p.muc_tu_chu} />
          <span className="text-xs text-fg-tertiary">#{p.id} · {fmtDateTime(p.created_at)}</span>
        </div>
        <h2 className="mt-2 text-base font-semibold text-balance">{p.tieu_de}</h2>
        <p className="mt-1 text-fg-secondary text-pretty">{p.tom_tat}</p>
        <p className="mt-1 text-xs text-fg-tertiary">
          Loại thao tác: {p.ten_hanh_dong} · Yêu cầu bởi{" "}
          {p.nguoi_yeu_cau.startsWith("agent:") ? `agent ${(AGENT_LABEL[p.agent] ?? p.agent).toLowerCase()}` : p.nguoi_yeu_cau}
        </p>
      </header>

      {p.ket_qua && (
        <div
          className={cx(
            "rounded-lg px-3 py-2",
            p.trang_thai === "that_bai" ? "bg-danger-subtle text-danger-fg" : "bg-success-subtle text-success-fg",
          )}
        >
          <p className="font-medium">Kết quả</p>
          <p className="text-pretty">{p.ket_qua}</p>
          {p.nguoi_duyet && (
            <p className="mt-1 text-xs opacity-90">
              {p.nguoi_duyet === "auto:L2" ? "Tự thực hiện trong hạn mức L2" : `Duyệt bởi ${p.nguoi_duyet}`}
              {p.da_sua && " · đã sửa trước khi duyệt"}
            </p>
          )}
        </div>
      )}
      {p.trang_thai === "tu_choi" && (
        <p className="rounded-lg bg-surface-muted px-3 py-2 text-fg-secondary">
          Từ chối bởi {p.nguoi_duyet}
          {p.ly_do_tu_choi ? `: ${p.ly_do_tu_choi}` : "."}
        </p>
      )}

      {p.can_cu.length > 0 && (
        <section>
          <h3 className="mb-1.5 font-medium">Căn cứ</h3>
          <ul className="flex list-disc flex-col gap-1 ps-5 text-fg-secondary marker:text-fg-tertiary">
            {p.can_cu.slice(0, 12).map((c, i) => (
              <li key={i} className="text-pretty">
                {typeof c === "string" ? c : JSON.stringify(c)}
              </li>
            ))}
            {p.can_cu.length > 12 && <li>… và {p.can_cu.length - 12} căn cứ khác</li>}
          </ul>
        </section>
      )}

      {items && (
        <section>
          <div className="mb-1.5 flex items-center justify-between gap-3">
            <h3 className="font-medium">
              Sẽ thực hiện cho <span className="num">{keepSet.size}</span>/<span className="num">{items.length}</span> mục
            </h3>
            {p.co_the_duyet && keepSet.size !== items.length && (
              <button className="text-[0.8125rem] font-medium text-accent-fg hover:underline" onClick={() => setKeep(null)}>
                Chọn lại tất cả
              </button>
            )}
          </div>
          <ul className="max-h-72 overflow-y-auto overscroll-contain rounded-lg border border-line">
            {items.map((it) => {
              const key = it[p.khoa_muc ?? "id"];
              const checked = keepSet.has(key);
              return (
                <li key={String(key)} className="border-b border-line last:border-0">
                  <label className={cx("flex items-start gap-3 px-3 py-2", p.co_the_duyet && "cursor-pointer hover:bg-surface-hover")}>
                    {p.co_the_duyet && (
                      <input
                        type="checkbox"
                        className="mt-0.5 size-4 accent-[var(--color-accent-solid)]"
                        checked={checked}
                        onChange={() => {
                          const next = new Set(keepSet);
                          if (checked) next.delete(key);
                          else next.add(key);
                          setKeep(next);
                        }}
                      />
                    )}
                    <span className={cx("num min-w-0 break-words", !checked && "text-fg-tertiary line-through")}>
                      {itemLine(it)}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {!items && <DataPreview p={p} showEmail={!(p.co_the_duyet && p.truong_sua_duoc.includes("body"))} />}

      {p.co_the_duyet && editable.length > 0 && (
        <section className="flex flex-col gap-3">
          <h3 className="font-medium">Sửa trước khi duyệt</h3>
          {editable.map((f) => (
            <Field key={f} label={FIELD_LABEL[f] ?? f}>
              {(fp) =>
                LONG.has(f) ? (
                  <Textarea
                    {...fp}
                    rows={f === "body" ? 8 : 2}
                    value={edits[f] ?? String(p.du_lieu[f] ?? "")}
                    onChange={(e) => setEdits({ ...edits, [f]: e.target.value })}
                  />
                ) : (
                  <Input
                    {...fp}
                    inputMode={f === "phan_tram" || f === "so_ngay" ? "numeric" : undefined}
                    value={edits[f] ?? String(p.du_lieu[f] ?? "")}
                    onChange={(e) => setEdits({ ...edits, [f]: e.target.value })}
                  />
                )
              }
            </Field>
          ))}
        </section>
      )}

      {p.co_the_duyet && (
        <footer className="flex flex-col gap-3 border-t border-line pt-4">
          {confirmReject ? (
            <div className="flex flex-col gap-3 rounded-lg bg-surface-muted p-3">
              <Field label="Lý do từ chối (agent sẽ không đề xuất lại việc này)">
                {(fp) => (
                  <Input {...fp} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Đã gọi điện trực tiếp" />
                )}
              </Field>
              <div className="flex flex-wrap justify-end gap-3">
                <Button variant="ghost" onClick={() => setConfirmReject(false)}>
                  Quay lại
                </Button>
                <Button variant="danger" loading={busy === "reject"} onClick={reject}>
                  <X className="size-4" aria-hidden />
                  Từ chối đề xuất
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap items-center justify-end gap-3">
              <Button variant="ghost" onClick={() => setConfirmReject(true)}>
                Từ chối
              </Button>
              <Button variant="primary" loading={busy === "approve"} onClick={approve}>
                <Check className="size-4" aria-hidden />
                {changed.length || (items && keepSet.size !== items.length) ? "Duyệt bản đã sửa" : "Duyệt và thực hiện"}
              </Button>
            </div>
          )}
          {p.het_han_luc && <p className="text-end text-xs text-fg-tertiary">Hết hạn duyệt lúc {fmtDateTime(p.het_han_luc)}</p>}
        </footer>
      )}
      {p.trang_thai === "goi_y" && (
        <footer className="flex justify-end border-t border-line pt-4">
          <Button onClick={dismiss}>Đánh dấu đã xem</Button>
        </footer>
      )}
    </article>
  );
}

/** Thẻ gọn hiện trong Copilot khi agent vận hành vừa tạo đề xuất. */
export function ProposalInline({ id }: { id: number }) {
  const { data: p, mutate } = useSWR<Proposal>(`/proposals/${id}`);
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  if (!p) return null;
  const decide = async (ok: boolean) => {
    setBusy(true);
    try {
      const r = await api<Proposal>(`/proposals/${id}/${ok ? "approve" : "reject"}`, { body: ok ? { edits: null } : { ly_do: "" } });
      await mutate(r, { revalidate: false });
      refresh("/proposals/counts");
      toast(ok ? r.ket_qua ?? "Đã duyệt." : "Đã từ chối.", r.trang_thai === "that_bai" ? "danger" : "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Không xử lý được.", "danger");
    } finally {
      setBusy(false);
    }
  };
  const n = p.du_lieu.items?.length;
  return (
    <div className="rounded-xl border border-line bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="agent">Đề xuất #{p.id}</Badge>
        <StatusBadge map={PROPOSAL_STATUS} value={p.trang_thai} />
      </div>
      <p className="mt-2 font-medium text-pretty">{p.tieu_de}</p>
      <p className="mt-0.5 text-fg-secondary text-pretty">
        {p.tom_tat}
        {n ? ` (${n} mục)` : ""}
      </p>
      {p.ket_qua && <p className="mt-2 text-success-fg text-pretty">{p.ket_qua}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {p.co_the_duyet && (
          <>
            <Button size="sm" variant="primary" loading={busy} onClick={() => decide(true)}>
              Duyệt và thực hiện
            </Button>
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => decide(false)}>
              Từ chối
            </Button>
          </>
        )}
        <Link href={`/inbox?id=${p.id}`} className="ms-auto inline-flex items-center gap-1 text-[0.8125rem] font-medium text-accent-fg hover:underline">
          Xem chi tiết trong Hộp duyệt
          <ExternalLink className="size-3.5" aria-hidden />
        </Link>
      </div>
    </div>
  );
}
