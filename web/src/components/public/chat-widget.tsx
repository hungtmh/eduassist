"use client";

import { MessageCircle, Send, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { IconButton, SunMark, cx } from "@/components/ui";
import { API_URL } from "@/lib/api";

type Msg = { role: "user" | "assistant"; content: string };
const SUGGEST = ["Khoá IELTS nào hợp với người mất gốc?", "Có cho trả góp học phí không?", "Lớp Excel buổi tối khai giảng khi nào?"];

/** Trợ lý tư vấn cho khách vãng lai. Chỉ tra tài liệu chính sách và danh sách khoá học; không lưu hội thoại. */
export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);
  // Thân hàm phải có ngoặc: Chrome mới trả Promise từ scrollIntoView, React sẽ coi đó là hàm dọn dẹp và báo lỗi
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [msgs]);
  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [open]);

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    const history: Msg[] = [...msgs, { role: "user", content: q }];
    setMsgs([...history, { role: "assistant", content: "" }]);
    setInput("");
    setBusy(true);
    const append = (t: string) => setMsgs((xs) => [...xs.slice(0, -1), { role: "assistant", content: xs[xs.length - 1].content + t }]);
    const replace = (t: string) => setMsgs((xs) => [...xs.slice(0, -1), { role: "assistant", content: t }]);
    try {
      const res = await fetch(`${API_URL}/public/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history.slice(-10) }),
      });
      if (!res.ok || !res.body) {
        const body = res.headers.get("content-type")?.includes("json") ? await res.json() : null;
        replace(typeof body?.detail === "string" ? body.detail : "Trợ lý đang bận. Bạn thử lại sau ít phút hoặc gọi 1900 0000.");
        return;
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let i: number;
        while ((i = buf.indexOf("\n\n")) >= 0) {
          const block = buf.slice(0, i);
          buf = buf.slice(i + 2);
          const type = block.match(/^event: (.+)$/m)?.[1];
          const data = block.match(/^data: (.+)$/m)?.[1];
          if (!data) continue;
          const ev = JSON.parse(data);
          if (type === "token") append(ev.text);
          else if (type === "done" && ev.answer) replace(ev.answer);
          else if (type === "error") replace(ev.message);
        }
      }
    } catch {
      replace("Không kết nối được. Bạn kiểm tra mạng rồi thử lại.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="pressable fixed end-4 bottom-4 z-40 inline-flex h-12 items-center gap-2 rounded-full bg-accent-solid ps-4 pe-5 font-medium text-white shadow-pop hover:bg-accent-solid-hover sm:end-6 sm:bottom-6"
        >
          <MessageCircle className="size-5" aria-hidden />
          Hỏi tư vấn
        </button>
      )}
      {open && (
        <section
          role="dialog"
          aria-label="Trợ lý tư vấn"
          className="fade-in fixed inset-x-2 bottom-2 z-50 flex h-[min(36rem,calc(100dvh-1rem))] flex-col overflow-hidden rounded-2xl bg-surface shadow-pop sm:inset-x-auto sm:end-6 sm:bottom-6 sm:w-96"
        >
          <header className="flex items-center gap-3 bg-side px-4 py-3 text-side-fg">
            <SunMark className="size-8" />
            <div className="min-w-0 flex-1">
              <p className="font-semibold">Trợ lý tư vấn Ánh Dương</p>
              <p className="text-xs text-side-fg-secondary">Trả lời tự động bằng AI · tra từ tài liệu của trung tâm</p>
            </div>
            <IconButton label="Đóng trợ lý" onClick={() => setOpen(false)} className="text-side-fg-secondary hover:bg-side-active hover:text-side-fg">
              <X className="size-4" aria-hidden />
            </IconButton>
          </header>
          <div className="flex-1 overflow-y-auto overscroll-contain px-4 py-4" aria-live="polite">
            {msgs.length === 0 ? (
              <div className="flex flex-col gap-3">
                <p className="text-fg-secondary text-pretty">
                  Chào bạn! Mình trả lời về khoá học, học phí, lịch khai giảng và chính sách của trung tâm. Bạn muốn hỏi gì?
                </p>
                {SUGGEST.map((s) => (
                  <button key={s} onClick={() => send(s)} className="rounded-xl bg-surface-muted px-3 py-2 text-start hover:bg-surface-hover">
                    {s}
                  </button>
                ))}
              </div>
            ) : (
              <ul className="flex flex-col gap-3">
                {msgs.map((m, i) => (
                  <li key={i} className={cx("max-w-[88%] rounded-2xl px-3.5 py-2.5", m.role === "user" ? "self-end bg-accent-solid text-white" : "self-start bg-surface-muted")}>
                    {m.role === "assistant" ? (
                      m.content ? (
                        <div className="prose-chat">
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              a: ({ href, children }) =>
                                href?.startsWith("/") ? (
                                  <Link href={href} className="font-medium text-accent-fg underline" onClick={() => setOpen(false)}>
                                    {children}
                                  </Link>
                                ) : (
                                  <a href={href} className="underline" target="_blank" rel="noopener noreferrer">
                                    {children}
                                  </a>
                                ),
                            }}
                          >
                            {m.content}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        <span className="text-fg-tertiary">Đang tra cứu…</span>
                      )
                    ) : (
                      m.content
                    )}
                  </li>
                ))}
              </ul>
            )}
            <div ref={endRef} />
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex items-end gap-2 border-t border-line p-3"
          >
            <label htmlFor="public-chat-input" className="sr-only">
              Câu hỏi của bạn
            </label>
            <textarea
              id="public-chat-input"
              ref={inputRef}
              rows={1}
              maxLength={1000}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              placeholder="Nhập câu hỏi…"
              className="max-h-28 min-h-10 flex-1 resize-none rounded-lg border border-control-border bg-surface px-3 py-2 outline-none focus-visible:border-accent-solid"
            />
            <IconButton label="Gửi" type="submit" disabled={busy || !input.trim()} className="bg-accent-solid text-white hover:bg-accent-solid-hover disabled:opacity-50">
              <Send className="size-4" aria-hidden />
            </IconButton>
          </form>
          <p className="px-3 pb-2 text-center text-[0.6875rem] text-fg-tertiary">
            Đừng nhập thông tin cá nhân vào khung chat. Muốn được gọi lại? <Link href="/dang-ky-tu-van" className="underline">Đăng ký tư vấn</Link>
          </p>
        </section>
      )}
    </>
  );
}
