"use client";

import { ArrowUp, BookText, Database, Loader2, Square, ThumbsDown, ThumbsUp, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ProposalInline } from "@/components/proposal";
import { useAuth } from "@/components/providers";
import { IconButton, cx, useToast } from "@/components/ui";
import { api, streamSSE } from "@/lib/api";

type Step = { kind: string; text: string };
type Msg = {
  role: "user" | "assistant";
  text: string;
  steps: Step[];
  sources: string[];
  proposals: number[];
  runId?: string;
  error?: string;
  done?: boolean;
  rated?: 1 | -1;
};

const AGENT = { advisor: "agent tư vấn", analytics: "agent phân tích", action: "agent vận hành" } as Record<string, string>;
const STARTERS: Record<string, string[]> = {
  student: ["Mình đang học những lớp nào, còn nợ bao nhiêu?", "Nghỉ giữa chừng có được hoàn tiền không?"],
  teacher: ["Chính sách học bù như thế nào?", "Học viên cần bao nhiêu % chuyên cần để được cấp chứng nhận?"],
  default: [
    "Doanh thu tháng này theo từng khoá?",
    "Lớp nào sắp khai giảng còn thiếu học viên?",
    "Gửi nhắc nợ cho tất cả học viên đang nợ, hạn sau 7 ngày",
  ],
};

function stepText(ev: Record<string, unknown>): Step | null {
  switch (ev.step) {
    case "agent_start":
      return { kind: "agent", text: `Giao cho ${AGENT[String(ev.agent)] ?? ev.agent}` };
    case "sql":
      return ev.status === "running" ? null : { kind: "sql", text: ev.status === "ok" ? `Chạy SQL chỉ đọc · ${ev.rows} dòng` : `SQL bị chặn hoặc lỗi, agent tự sửa` };
    case "retrieval":
      return { kind: "doc", text: `Tra tài liệu: “${ev.query}”` };
    case "courses":
      return { kind: "doc", text: "Tra danh sách khoá học và lớp sắp mở" };
    case "memory":
      return { kind: "agent", text: "Ghi nhớ thông tin của bạn cho lần sau" };
    default:
      return null;
  }
}

export function Copilot({ onClose }: { onClose: () => void }) {
  const { user } = useAuth();
  const toast = useToast();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const conv = useRef<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [msgs]);

  const patchLast = (fn: (m: Msg) => Msg) => setMsgs((xs) => [...xs.slice(0, -1), fn(xs[xs.length - 1])]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    setInput("");
    setBusy(true);
    setMsgs((xs) => [
      ...xs,
      { role: "user", text: message, steps: [], sources: [], proposals: [] },
      { role: "assistant", text: "", steps: [], sources: [], proposals: [] },
    ]);
    abort.current = new AbortController();
    try {
      await streamSSE(
        "/chat",
        { message, conversation_id: conv.current },
        (type, ev) => {
          if (type === "meta") {
            conv.current = String(ev.conversation_id);
            patchLast((m) => ({ ...m, runId: String(ev.run_id) }));
          } else if (type === "token") {
            patchLast((m) => ({ ...m, text: m.text + String(ev.text) }));
          } else if (type === "step") {
            if (ev.step === "proposal") {
              patchLast((m) => ({ ...m, proposals: [...new Set([...m.proposals, Number(ev.id)])] }));
              return;
            }
            const s = stepText(ev);
            if (s) patchLast((m) => ({ ...m, steps: [...m.steps, s] }));
          } else if (type === "done") {
            patchLast((m) => ({ ...m, done: true, sources: (ev.sources as string[]) ?? [], text: m.text || String(ev.answer ?? "") }));
          } else if (type === "error") {
            patchLast((m) => ({ ...m, done: true, error: String(ev.message) }));
          }
        },
        abort.current.signal,
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        patchLast((m) => ({ ...m, done: true, error: e instanceof Error ? e.message : "Không gửi được câu hỏi." }));
      } else {
        patchLast((m) => ({ ...m, done: true }));
      }
    } finally {
      setBusy(false);
      abort.current = null;
    }
  }

  async function rate(i: number, score: 1 | -1) {
    const m = msgs[i];
    if (!m.runId || !conv.current) return;
    try {
      const r = await api<{ promoted_sql_examples: string[] }>("/feedback", {
        body: { conversation_id: conv.current, run_id: m.runId, score },
      });
      setMsgs((xs) => xs.map((x, j) => (j === i ? { ...x, rated: score } : x)));
      toast(r.promoted_sql_examples.length ? "Cảm ơn bạn. Câu SQL này được thêm vào kho ví dụ để agent học lại." : "Cảm ơn bạn đã đánh giá.");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Không gửi được đánh giá.", "danger");
    }
  }

  const starters = STARTERS[user?.role ?? ""] ?? STARTERS.default;

  return (
    <aside
      id="copilot"
      aria-label="Copilot"
      className="fixed inset-0 z-40 flex flex-col bg-surface lg:sticky lg:top-14 lg:z-auto lg:h-[calc(100dvh-3.5rem)] lg:w-[26rem] lg:shrink-0 lg:border-s lg:border-line"
    >
      <div className="flex items-center gap-2 border-b border-line px-4 py-3">
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold">Copilot</h2>
          <p className="truncate text-xs text-fg-tertiary">Hỏi số liệu, chính sách, hoặc ra lệnh bằng tiếng Việt</p>
        </div>
        {msgs.length > 0 && (
          <IconButton
            label="Bắt đầu cuộc trò chuyện mới"
            onClick={() => {
              setMsgs([]);
              conv.current = null;
            }}
          >
            <Trash2 className="size-4" aria-hidden />
          </IconButton>
        )}
        <IconButton label="Đóng Copilot" onClick={onClose}>
          <X className="size-4" aria-hidden />
        </IconButton>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4" aria-live="polite" aria-busy={busy}>
        {msgs.length === 0 && (
          <div className="flex flex-col gap-3">
            <p className="text-fg-secondary text-pretty">
              Copilot dùng chung luật và quyền với vai trò của bạn. Thao tác như gửi email hay cấp voucher sẽ thành đề xuất để bạn duyệt trước.
            </p>
            <div className="flex flex-col gap-2">
              {starters.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="pressable rounded-lg border border-line px-3 py-2 text-start hover:bg-surface-hover"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        <ol className="flex flex-col gap-5">
          {msgs.map((m, i) =>
            m.role === "user" ? (
              <li key={i} className="ms-8 self-end rounded-2xl bg-accent-subtle px-3.5 py-2 text-pretty">
                {m.text}
              </li>
            ) : (
              <li key={i} className="flex flex-col gap-2">
                {m.steps.length > 0 && (
                  <ul className="flex flex-col gap-1 text-xs text-fg-tertiary">
                    {m.steps.map((s, k) => (
                      <li key={k} className="flex items-center gap-1.5">
                        {s.kind === "sql" ? <Database className="size-3.5" aria-hidden /> : <BookText className="size-3.5" aria-hidden />}
                        {s.text}
                      </li>
                    ))}
                  </ul>
                )}
                {!m.text && !m.done && (
                  <p className="flex items-center gap-2 text-fg-secondary">
                    <Loader2 className="size-4 animate-spin motion-reduce:animate-none" aria-hidden />
                    Đang xử lý…
                  </p>
                )}
                {m.text && (
                  <div className="prose-chat min-w-0 break-words">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
                  </div>
                )}
                {m.proposals.map((id) => (
                  <ProposalInline key={id} id={id} />
                ))}
                {m.sources.length > 0 && (
                  <div className="text-xs text-fg-secondary">
                    <p className="font-medium">Nguồn đã kiểm chứng</p>
                    <ul className="mt-1 flex flex-col gap-0.5">
                      {m.sources.map((s) => (
                        <li key={s}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {m.error && (
                  <p role="alert" className="rounded-lg bg-danger-subtle px-3 py-2 text-danger-fg">
                    {m.error}
                  </p>
                )}
                {m.done && !m.error && m.runId && (
                  <div className="flex gap-1">
                    <IconButton
                      label="Câu trả lời hữu ích"
                      aria-pressed={m.rated === 1}
                      onClick={() => rate(i, 1)}
                      className={cx("size-8", m.rated === 1 && "text-success-fg")}
                    >
                      <ThumbsUp className="size-4" aria-hidden />
                    </IconButton>
                    <IconButton
                      label="Câu trả lời chưa đúng"
                      aria-pressed={m.rated === -1}
                      onClick={() => rate(i, -1)}
                      className={cx("size-8", m.rated === -1 && "text-danger-fg")}
                    >
                      <ThumbsDown className="size-4" aria-hidden />
                    </IconButton>
                  </div>
                )}
              </li>
            ),
          )}
        </ol>
        <div ref={endRef} />
      </div>

      <form
        className="border-t border-line p-3"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <label htmlFor="copilot-input" className="sr-only">
          Câu hỏi cho Copilot
        </label>
        <div className="flex items-end gap-2 rounded-xl border border-control-border bg-surface p-1.5 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-[var(--color-focus)]">
          <textarea
            id="copilot-input"
            ref={inputRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                send(input);
              }
            }}
            placeholder="Học viên nào nợ quá hạn nhiều nhất?"
            className="max-h-40 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 text-base outline-none sm:text-sm"
          />
          {busy ? (
            <IconButton type="button" label="Dừng trả lời" onClick={() => abort.current?.abort()} className="bg-surface-hover">
              <Square className="size-4" aria-hidden />
            </IconButton>
          ) : (
            <IconButton type="submit" label="Gửi câu hỏi" disabled={!input.trim()} className="bg-accent-solid text-white hover:bg-accent-solid-hover hover:text-white disabled:opacity-40">
              <ArrowUp className="size-4" aria-hidden />
            </IconButton>
          )}
        </div>
        <p className="mt-1.5 px-1 text-xs text-fg-tertiary">Enter để gửi · Shift+Enter xuống dòng</p>
      </form>
    </aside>
  );
}
