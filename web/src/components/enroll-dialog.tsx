"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { Button, Dialog, Field, Input, Select } from "@/components/ui";
import { useToast } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, vnd } from "@/lib/format";

type Quote = {
  ma_lop: string;
  khoa_hoc: string;
  hoc_phi_goc: number;
  giam_gia: number;
  giam_gia_ghi_chu: string;
  thanh_tien: number;
  cho_trong: number;
  dot: { so_tien: number; han: string }[];
  loi: string[];
};

const PROMOS = [
  ["", "Không áp dụng"],
  ["dang_ky_som", "Đăng ký sớm (10%)"],
  ["nhom", "Nhóm từ 3 người (7%)"],
  ["hoc_vien_cu", "Học viên cũ (5%)"],
  ["hssv", "Học sinh, sinh viên (5%)"],
];

export function EnrollDialog({
  open,
  onClose,
  onDone,
  studentId,
  classId,
  leadId,
}: {
  open: boolean;
  onClose: () => void;
  onDone: () => void;
  studentId?: number;
  classId?: number;
  leadId?: number;
}) {
  const toast = useToast();
  const [student, setStudent] = useState(studentId ? String(studentId) : "");
  const [cls, setCls] = useState(classId ? String(classId) : "");
  const [q, setQ] = useState("");
  const [installments, setInstallments] = useState(false);
  const [promo, setPromo] = useState("");
  const [voucher, setVoucher] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: classes } = useSWR<{ id: number; ma_lop: string; khoa_hoc: string; si_so: number; si_so_toi_da: number; trang_thai: string }[]>(
    open && !classId ? "/classes?con_mo=true" : null,
  );
  const { data: students } = useSWR<{ id: number; ho_ten: string; email: string }[]>(
    open && !studentId && q.length >= 2 ? `/students?q=${encodeURIComponent(q)}` : null,
  );

  useEffect(() => {
    if (!open || !student || !cls) {
      setQuote(null);
      return;
    }
    const t = setTimeout(() => {
      api<Quote>("/enrollments/quote", {
        body: { hoc_vien_id: Number(student), lop_hoc_id: Number(cls), tra_gop: installments, uu_dai: promo || null, voucher: voucher || null },
      })
        .then((r) => {
          setQuote(r);
          setErr(null);
        })
        .catch((e) => setErr(e.message));
    }, 250);
    return () => clearTimeout(t);
  }, [open, student, cls, installments, promo, voucher]);

  async function submit() {
    setBusy(true);
    try {
      const r = await api<{ don_hang_id: number }>("/enrollments", {
        body: {
          hoc_vien_id: Number(student),
          lop_hoc_id: Number(cls),
          tra_gop: installments,
          uu_dai: promo || null,
          voucher: voucher || null,
          khach_id: leadId ?? null,
        },
      });
      toast(`Đã ghi danh vào lớp ${quote?.ma_lop}. Hoá đơn #${r.don_hang_id} và các đợt thanh toán đã được tạo.`);
      onDone();
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Không ghi danh được.");
    } finally {
      setBusy(false);
    }
  }

  const openClasses = classes?.filter((c) => c.trang_thai === "sap_khai_giang" || c.trang_thai === "dang_hoc");

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Ghi danh vào lớp"
      description="Hệ thống kiểm tra sĩ số, điều kiện trả góp và ưu đãi trước khi tạo hoá đơn."
      wide
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Huỷ
          </Button>
          <Button variant="primary" loading={busy} disabled={!quote || quote.loi.length > 0} onClick={submit}>
            Ghi danh và tạo hoá đơn
          </Button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {!studentId && (
          <div className="flex flex-col gap-3 sm:col-span-2">
            <Field label="Tìm học viên">
              {(p) => <Input {...p} type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tên, email hoặc mã học viên" />}
            </Field>
            {students && (
              <Field label="Học viên">
                {(p) => (
                  <Select {...p} value={student} onChange={(e) => setStudent(e.target.value)}>
                    <option value="">Chọn học viên ({students.length} kết quả)</option>
                    {students.map((s) => (
                      <option key={s.id} value={s.id}>
                        #{s.id} {s.ho_ten} · {s.email}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            )}
          </div>
        )}
        {!classId && (
          <Field label="Lớp" className="sm:col-span-2">
            {(p) => (
              <Select {...p} value={cls} onChange={(e) => setCls(e.target.value)}>
                <option value="">Chọn lớp đang nhận học viên</option>
                {openClasses?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.ma_lop} · {c.khoa_hoc} · {c.si_so}/{c.si_so_toi_da}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}
        <Field label="Ưu đãi" hint="Các ưu đãi không cộng dồn; cộng với voucher tối đa 15%">
          {(p) => (
            <Select {...p} value={promo} onChange={(e) => setPromo(e.target.value)}>
              {PROMOS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Mã voucher (nếu có)">
          {(p) => <Input {...p} value={voucher} onChange={(e) => setVoucher(e.target.value.toUpperCase())} placeholder="AD-1A2B3C" autoCapitalize="characters" />}
        </Field>
        <label className="flex items-start gap-3 sm:col-span-2">
          <input type="checkbox" className="mt-0.5 size-4 accent-[var(--color-accent-solid)]" checked={installments} onChange={(e) => setInstallments(e.target.checked)} />
          <span>
            <span className="font-medium">Trả góp 2 đợt</span>
            <span className="block text-fg-secondary">Chỉ cho khoá từ 5.000.000đ: 50% khi đăng ký, phần còn lại trước buổi học thứ 10.</span>
          </span>
        </label>
      </div>

      {quote && (
        <div className="mt-5 rounded-xl bg-surface-muted p-4">
          <p className="font-medium">
            {quote.khoa_hoc} · lớp {quote.ma_lop} · còn {quote.cho_trong} chỗ
          </p>
          <dl className="num mt-3 grid grid-cols-[minmax(0,1fr)_auto] gap-y-1">
            <dt className="text-fg-secondary">Học phí niêm yết</dt>
            <dd className="text-end">{vnd(quote.hoc_phi_goc)}</dd>
            <dt className="text-fg-secondary">Giảm ({quote.giam_gia_ghi_chu})</dt>
            <dd className="text-end">−{vnd(quote.giam_gia)}</dd>
            <dt className="font-medium">Phải trả</dt>
            <dd className="text-end font-semibold">{vnd(quote.thanh_tien)}</dd>
          </dl>
          <ul className="mt-3 flex flex-col gap-1 border-t border-line pt-3">
            {quote.dot.map((d, i) => (
              <li key={i} className="num flex justify-between">
                <span className="text-fg-secondary">Đợt {i + 1} · hạn {fmtDate(d.han)}</span>
                <span>{vnd(d.so_tien)}</span>
              </li>
            ))}
          </ul>
          {quote.loi.length > 0 && (
            <ul role="alert" className="mt-3 flex flex-col gap-1 rounded-lg bg-danger-subtle px-3 py-2 text-danger-fg">
              {quote.loi.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          )}
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
