"use client";

import { Plus, Search } from "lucide-react";
import { useState } from "react";
import useSWR from "swr";
import { useAuth } from "@/components/providers";
import { TempPasswordDialog } from "@/components/temp-password";
import {
  Badge,
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorBox,
  Field,
  Input,
  LoadMore,
  PageHeader,
  Segmented,
  Select,
  Spinner,
  Table,
  td,
  th,
  useToast,
} from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { ROLE, STAFF_ROLES } from "@/lib/labels";
import { usePaged } from "@/lib/use-paged";

type User = {
  username: string;
  role: string;
  display_name: string;
  email: string | null;
  hoc_vien_id: number | null;
  giang_vien_id: number | null;
  active: boolean;
  must_change_password: boolean;
  dang_bi_khoa_tam: boolean;
  last_login_at: string | null;
};
type Teacher = { id: number; ho_ten: string; email: string; username: string | null };
type Issued = { username: string; password: string; note: string };

function StatusCell({ u }: { u: User }) {
  if (!u.active) return <Badge tone="danger">Đã khoá</Badge>;
  if (u.dang_bi_khoa_tam) return <Badge tone="warning">Tạm khoá (sai mật khẩu)</Badge>;
  if (u.must_change_password) return <Badge tone="warning">Chờ đổi mật khẩu</Badge>;
  return <Badge tone="success">Hoạt động</Badge>;
}

function emailNote(r: { da_gui_email: boolean; loi_email: string | null }, sentWhat: string) {
  if (r.da_gui_email) return `Đã gửi ${sentWhat} qua email. Mật khẩu tạm chỉ dùng khi người dùng không nhận được email.`;
  if (r.loi_email) return `Chưa gửi được email (${r.loi_email}). Đưa mật khẩu tạm trực tiếp cho người dùng.`;
  return "Đưa mật khẩu tạm trực tiếp cho người dùng (không gửi qua chat/email công khai).";
}

function CreateDialog({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: (i: Issued) => void }) {
  const { data: teachers } = useSWR<Teacher[]>(open ? "/teachers" : null);
  const [f, setF] = useState({ username: "", display_name: "", role: "consultant", email: "", giang_vien_id: "", gui_email: true });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setF((v) => ({ ...v, [k]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value }));

  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      const r = await api<{ user: User; mat_khau_tam: string; da_gui_email: boolean; loi_email: string | null }>("/users", {
        body: {
          username: f.username.trim().toLowerCase(),
          display_name: f.display_name.trim(),
          role: f.role,
          email: f.email.trim() || null,
          giang_vien_id: f.role === "teacher" && f.giang_vien_id ? Number(f.giang_vien_id) : null,
          gui_email: f.gui_email && !!f.email.trim(),
        },
      });
      onDone({ username: r.user.username, password: r.mat_khau_tam, note: emailNote(r, "link kích hoạt") });
      setF({ username: "", display_name: "", role: "consultant", email: "", giang_vien_id: "", gui_email: true });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Không tạo được tài khoản.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Thêm người dùng"
      description="Tài khoản học viên được cấp từ hồ sơ học viên, không tạo ở đây."
      footer={
        <>
          <Button onClick={onClose}>Huỷ</Button>
          <Button variant="primary" loading={busy} disabled={f.username.trim().length < 3 || f.display_name.trim().length < 2} onClick={submit}>
            Tạo tài khoản
          </Button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Tên đăng nhập" hint="Chữ thường không dấu, số, dấu chấm. VD: lan.nguyen">
          {(p) => <Input {...p} autoCapitalize="none" value={f.username} onChange={set("username")} />}
        </Field>
        <Field label="Tên hiển thị">{(p) => <Input {...p} value={f.display_name} onChange={set("display_name")} />}</Field>
        <Field label="Vai trò">
          {(p) => (
            <Select {...p} value={f.role} onChange={set("role")}>
              {STAFF_ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE[r]}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Email" hint="Dùng cho quên mật khẩu và link kích hoạt">
          {(p) => <Input {...p} type="email" value={f.email} onChange={set("email")} />}
        </Field>
        {f.role === "teacher" && (
          <Field label="Hồ sơ giảng viên" hint="Gắn để giảng viên thấy lớp mình dạy" className="sm:col-span-2">
            {(p) => (
              <Select {...p} value={f.giang_vien_id} onChange={set("giang_vien_id")}>
                <option value="">Chưa gắn</option>
                {teachers
                  ?.filter((t) => !t.username)
                  .map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.ho_ten} · {t.email}
                    </option>
                  ))}
              </Select>
            )}
          </Field>
        )}
        <label className="flex items-center gap-2 sm:col-span-2">
          <input type="checkbox" checked={f.gui_email} onChange={set("gui_email")} disabled={!f.email.trim()} className="size-4 accent-accent-solid" />
          Gửi link kích hoạt qua email
        </label>
      </div>
      {err && (
        <p role="alert" className="mt-4 rounded-lg bg-danger-subtle px-3 py-2 text-danger-fg">
          {err}
        </p>
      )}
    </Dialog>
  );
}

function EditDialog({ user, onClose, onSaved, onIssued }: { user: User | null; onClose: () => void; onSaved: () => void; onIssued: (i: Issued) => void }) {
  const { user: me } = useAuth();
  const toast = useToast();
  const [f, setF] = useState<{ display_name: string; role: string; email: string; active: boolean } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const cur = user && (f ?? { display_name: user.display_name, role: user.role, email: user.email ?? "", active: user.active });
  const isStudent = user?.role === "student";
  const isMe = user?.username === me?.username;

  function close() {
    setF(null);
    setErr(null);
    onClose();
  }

  async function save() {
    if (!user || !cur) return;
    setBusy(true);
    setErr(null);
    try {
      await api(`/users/${encodeURIComponent(user.username)}`, {
        method: "PATCH",
        body: { display_name: cur.display_name, role: isStudent ? null : cur.role, email: cur.email, active: cur.active },
      });
      toast("Đã lưu. Nếu đổi vai trò hoặc khoá, người dùng bị đăng xuất ngay.");
      onSaved();
      close();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Không lưu được.");
    } finally {
      setBusy(false);
    }
  }

  async function resetPassword() {
    if (!user) return;
    if (!window.confirm(`Cấp mật khẩu tạm mới cho ${user.username}? Mọi phiên đăng nhập của người này sẽ kết thúc.`)) return;
    setBusy(true);
    try {
      const r = await api<{ mat_khau_tam: string; da_gui_email: boolean; loi_email: string | null }>(
        `/users/${encodeURIComponent(user.username)}/reset-password`,
        { body: { gui_email: !!user.email } },
      );
      onIssued({ username: user.username, password: r.mat_khau_tam, note: emailNote(r, "link đặt lại mật khẩu") });
      onSaved();
      close();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Không cấp lại được mật khẩu.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={!!user}
      onClose={close}
      title={user ? `Sửa tài khoản ${user.username}` : ""}
      footer={
        <>
          <Button variant="ghost" className="me-auto" disabled={busy} onClick={resetPassword}>
            Cấp lại mật khẩu
          </Button>
          <Button onClick={close}>Huỷ</Button>
          <Button variant="primary" loading={busy} onClick={save}>
            Lưu
          </Button>
        </>
      }
    >
      {cur && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Tên hiển thị">
            {(p) => <Input {...p} value={cur.display_name} onChange={(e) => setF({ ...cur, display_name: e.target.value })} />}
          </Field>
          <Field label="Vai trò" hint={isStudent ? "Tài khoản học viên giữ nguyên vai trò" : isMe ? "Không tự hạ quyền được" : undefined}>
            {(p) => (
              <Select {...p} value={cur.role} disabled={isStudent || isMe} onChange={(e) => setF({ ...cur, role: e.target.value })}>
                {(isStudent ? ["student"] : STAFF_ROLES).map((r) => (
                  <option key={r} value={r}>
                    {ROLE[r]}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Email" className="sm:col-span-2">
            {(p) => <Input {...p} type="email" value={cur.email} onChange={(e) => setF({ ...cur, email: e.target.value })} />}
          </Field>
          <label className="flex items-center gap-2 sm:col-span-2">
            <input
              type="checkbox"
              checked={cur.active}
              disabled={isMe}
              onChange={(e) => setF({ ...cur, active: e.target.checked })}
              className="size-4 accent-accent-solid"
            />
            Cho phép đăng nhập {isMe && <span className="text-fg-tertiary">(không tự khoá được)</span>}
          </label>
        </div>
      )}
      {err && (
        <p role="alert" className="mt-4 rounded-lg bg-danger-subtle px-3 py-2 text-danger-fg">
          {err}
        </p>
      )}
    </Dialog>
  );
}

export default function UsersPage() {
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [issued, setIssued] = useState<Issued | null>(null);
  const qs = new URLSearchParams({ ...(q.trim() && { q: q.trim() }), ...(role && { role }) }).toString();
  const list = usePaged<User>(`/users${qs ? `?${qs}` : ""}`, 50);

  return (
    <>
      <PageHeader
        eyebrow="Quản trị"
        title="Người dùng"
        description="Tạo tài khoản nhân viên, khoá tài khoản, đổi vai trò. Khoá hoặc đổi vai trò có hiệu lực ngay, kể cả với phiên đang mở."
        actions={
          <Button variant="primary" onClick={() => setCreating(true)}>
            <Plus className="size-4" aria-hidden />
            Thêm người dùng
          </Button>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Segmented
          label="Lọc theo vai trò"
          value={role}
          onChange={setRole}
          options={[{ value: "", label: "Tất cả" }, ...[...STAFF_ROLES, "student"].map((r) => ({ value: r, label: ROLE[r] }))]}
        />
        <div className="relative w-full sm:ms-auto sm:w-72">
          <Search className="pointer-events-none absolute start-3 top-2.5 size-4 text-fg-tertiary" aria-hidden />
          <label htmlFor="user-q" className="sr-only">
            Tìm người dùng
          </label>
          <Input id="user-q" type="search" className="ps-9" placeholder="Tên, tên đăng nhập, email" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      {list.error && <ErrorBox error={list.error} onRetry={() => list.mutate()} />}
      {!list.items ? (
        <Spinner />
      ) : list.items.length === 0 ? (
        <EmptyState title="Không có người dùng khớp bộ lọc" />
      ) : (
        <Card>
          <Table label="Danh sách người dùng">
            <thead>
              <tr>
                <th className={th}>Người dùng</th>
                <th className={th}>Vai trò</th>
                <th className={th}>Trạng thái</th>
                <th className={th}>Đăng nhập gần nhất</th>
                <th className={th}>
                  <span className="sr-only">Thao tác</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {list.items.map((u) => (
                <tr key={u.username}>
                  <td className={td}>
                    <p className="font-medium">{u.display_name}</p>
                    <p className="text-xs text-fg-tertiary">
                      <span className="font-mono">{u.username}</span>
                      {u.email && ` · ${u.email}`}
                    </p>
                  </td>
                  <td className={td}>{ROLE[u.role] ?? u.role}</td>
                  <td className={td}>
                    <StatusCell u={u} />
                  </td>
                  <td className={`${td} num text-fg-secondary`}>{u.last_login_at ? fmtDateTime(u.last_login_at) : "Chưa"}</td>
                  <td className={`${td} text-end`}>
                    <Button size="sm" onClick={() => setEditing(u)}>
                      Sửa
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
      {list.items && (
        <LoadMore shown={list.items.length} total={list.total} noun="người dùng" hasMore={list.hasMore} loading={list.loadingMore} onMore={list.loadMore} />
      )}

      <CreateDialog
        open={creating}
        onClose={() => setCreating(false)}
        onDone={(i) => {
          setCreating(false);
          setIssued(i);
          list.mutate();
        }}
      />
      <EditDialog user={editing} onClose={() => setEditing(null)} onSaved={() => list.mutate()} onIssued={setIssued} />
      {issued && <TempPasswordDialog open onClose={() => setIssued(null)} username={issued.username} password={issued.password} emailNote={issued.note} />}
    </>
  );
}
