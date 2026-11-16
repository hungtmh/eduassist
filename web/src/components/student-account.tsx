"use client";

import { useState } from "react";
import useSWR from "swr";
import { useAuth } from "@/components/providers";
import { Badge, Button, Card, CardHeader, useToast } from "@/components/ui";
import { TempPasswordDialog } from "@/components/temp-password";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

type Account = { username: string; active: boolean; must_change_password: boolean; last_login_at: string | null } | null;
type Created = { user: { username: string }; mat_khau_tam: string; da_gui_email: boolean; loi_email: string | null };

/** Thẻ "Tài khoản cổng học viên" trong hồ sơ học viên: xem trạng thái, cấp tài khoản + gửi link kích hoạt. */
export function StudentAccountCard({ studentId, email }: { studentId: number; email: string | null }) {
  const { can } = useAuth();
  const toast = useToast();
  const { data, mutate } = useSWR<{ account: Account }>(`/students/${studentId}/account`);
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<Created | null>(null);
  const acc = data?.account;

  async function create() {
    setBusy(true);
    try {
      const r = await api<Created>(`/students/${studentId}/account`, { body: { gui_email: !!email } });
      setCreated(r);
      mutate();
      toast(r.da_gui_email ? "Đã cấp tài khoản và gửi link kích hoạt qua email." : "Đã cấp tài khoản.");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Không cấp được tài khoản.", "danger");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader title="Tài khoản cổng học viên" />
      <div className="px-4 pb-4">
        {data === undefined ? (
          <p className="text-fg-secondary">Đang tải…</p>
        ) : acc ? (
          <div className="flex flex-col gap-2">
            <p>
              Tên đăng nhập <span className="font-mono font-medium">{acc.username}</span>
            </p>
            <p className="flex flex-wrap gap-2">
              {!acc.active ? (
                <Badge tone="danger">Đã khoá</Badge>
              ) : acc.must_change_password ? (
                <Badge tone="warning">Chưa kích hoạt</Badge>
              ) : (
                <Badge tone="success">Đang dùng</Badge>
              )}
            </p>
            <p className="text-xs text-fg-tertiary">
              {acc.last_login_at ? `Đăng nhập gần nhất ${fmtDateTime(acc.last_login_at)}` : "Chưa đăng nhập lần nào"}
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-start gap-3">
            <p className="text-fg-secondary text-pretty">
              Học viên chưa có tài khoản để xem lịch học, học phí và gửi yêu cầu.
              {email ? " Hệ thống gửi link tự đặt mật khẩu tới email của học viên." : " Học viên chưa có email: bạn sẽ nhận mật khẩu tạm để đưa trực tiếp."}
            </p>
            {can("student.account") && (
              <Button variant="primary" size="sm" loading={busy} onClick={create}>
                Cấp tài khoản
              </Button>
            )}
          </div>
        )}
      </div>
      {created && (
        <TempPasswordDialog
          open
          onClose={() => setCreated(null)}
          username={created.user.username}
          password={created.mat_khau_tam}
          emailNote={
            created.da_gui_email
              ? "Đã gửi link kích hoạt tới email học viên. Chỉ dùng mật khẩu tạm này nếu học viên không nhận được email."
              : created.loi_email
                ? `Chưa gửi được email (${created.loi_email}). Đưa mật khẩu tạm này cho học viên.`
                : "Đưa mật khẩu tạm này cho học viên. Học viên phải đổi mật khẩu ở lần đăng nhập đầu."
          }
        />
      )}
    </Card>
  );
}
