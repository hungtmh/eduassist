"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Button, Dialog } from "@/components/ui";

/** Hiện mật khẩu tạm MỘT lần (máy chủ không lưu bản rõ, đóng hộp thoại là không xem lại được). */
export function TempPasswordDialog({
  open,
  onClose,
  username,
  password,
  emailNote,
}: {
  open: boolean;
  onClose: () => void;
  username: string;
  password: string;
  emailNote?: string;
}) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(`Tên đăng nhập: ${username}\nMật khẩu tạm: ${password}`);
      setCopied(true);
    } catch {
      /* trình duyệt chặn clipboard: người dùng tự chép */
    }
  }
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Mật khẩu tạm"
      description="Chỉ hiện một lần. Người dùng phải đổi mật khẩu ở lần đăng nhập đầu."
      footer={
        <Button variant="primary" onClick={onClose}>
          Đã ghi lại
        </Button>
      }
    >
      <dl className="grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-2 rounded-lg bg-surface-muted px-4 py-3">
        <dt className="text-fg-secondary">Tên đăng nhập</dt>
        <dd className="font-mono font-medium">{username}</dd>
        <dt className="text-fg-secondary">Mật khẩu tạm</dt>
        <dd className="font-mono text-base font-semibold tracking-wide select-all">{password}</dd>
      </dl>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        {emailNote && <p className="min-w-0 flex-1 text-fg-secondary text-pretty">{emailNote}</p>}
        <Button size="sm" onClick={copy}>
          {copied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />}
          {copied ? "Đã chép" : "Chép"}
        </Button>
      </div>
    </Dialog>
  );
}
