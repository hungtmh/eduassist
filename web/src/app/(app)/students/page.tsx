"use client";

import { Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { Card, EmptyState, ErrorBox, Input, PageHeader, Spinner, Table, td, th } from "@/components/ui";
import { fmtDate, vnd } from "@/lib/format";
import { SOURCE } from "@/lib/labels";

type Row = {
  id: number;
  ho_ten: string;
  email: string;
  so_dien_thoai: string;
  thanh_pho: string;
  nguon: string;
  ngay_dang_ky: string;
  so_lop_dang_hoc: number;
  con_no: number;
};

export default function StudentsPage() {
  const [q, setQ] = useState("");
  const { data, error, mutate } = useSWR<Row[]>(`/students${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  return (
    <>
      <PageHeader title="Học viên" description="100 hồ sơ gần nhất. Tìm theo tên, email, số điện thoại hoặc mã học viên." />
      <div className="relative mb-4 max-w-sm">
        <Search className="pointer-events-none absolute start-3 top-2.5 size-4 text-fg-tertiary" aria-hidden />
        <label htmlFor="stu-q" className="sr-only">
          Tìm học viên
        </label>
        <Input id="stu-q" type="search" className="ps-9" placeholder="Nguyễn Văn An hoặc 0901…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {error && <ErrorBox error={error} onRetry={() => mutate()} />}
      <Card>
        {!data ? (
          <Spinner />
        ) : data.length === 0 ? (
          <EmptyState title={`Không có học viên khớp “${q}”`} />
        ) : (
          <Table label="Danh sách học viên">
            <thead>
              <tr>
                <th className={th}>Học viên</th>
                <th className={th}>Liên hệ</th>
                <th className={th}>Nguồn</th>
                <th className={`${th} text-end`}>Lớp đang học</th>
                <th className={`${th} text-end`}>Còn nợ</th>
              </tr>
            </thead>
            <tbody>
              {data.map((s) => (
                <tr key={s.id} className="hover:bg-surface-hover">
                  <td className={td}>
                    <Link href={`/students/${s.id}`} className="font-medium hover:underline">
                      {s.ho_ten}
                    </Link>
                    <p className="num text-fg-tertiary">
                      #{s.id} · đăng ký {fmtDate(s.ngay_dang_ky)}
                    </p>
                  </td>
                  <td className={td}>
                    <p className="break-all">{s.email}</p>
                    <p className="num text-fg-tertiary">{s.so_dien_thoai}</p>
                  </td>
                  <td className={td}>
                    {SOURCE[s.nguon] ?? s.nguon} · {s.thanh_pho}
                  </td>
                  <td className={`${td} num text-end`}>{s.so_lop_dang_hoc}</td>
                  <td className={`${td} num text-end ${s.con_no > 0 ? "font-medium" : "text-fg-tertiary"}`}>{vnd(s.con_no)}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </>
  );
}
