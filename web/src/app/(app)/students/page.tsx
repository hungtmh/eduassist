"use client";

import { BookOpen, MapPin, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Avatar, Badge, EmptyState, ErrorBox, Input, LoadMore, PageHeader, Spinner } from "@/components/ui";
import { fmtDate, vnd } from "@/lib/format";
import { SOURCE } from "@/lib/labels";
import { usePaged } from "@/lib/use-paged";

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
  co_tai_khoan: boolean;
};

export default function StudentsPage() {
  const [q, setQ] = useState("");
  const list = usePaged<Row>(`/students${q ? `?q=${encodeURIComponent(q)}` : ""}`, 60);
  const { items: data, error, mutate } = list;
  return (
    <>
      <PageHeader
        eyebrow="Học vụ"
        title="Danh bạ học viên"
        description={`${list.total ? `${list.total.toLocaleString("vi-VN")} hồ sơ, mới nhất trước. ` : ""}Tìm theo tên, email, số điện thoại hoặc mã học viên.`}
        actions={
          <div className="relative w-full sm:w-80">
            <Search className="pointer-events-none absolute start-3 top-2.5 size-4 text-fg-tertiary" aria-hidden />
            <label htmlFor="stu-q" className="sr-only">
              Tìm học viên
            </label>
            <Input id="stu-q" type="search" className="ps-9" placeholder="Nguyễn Văn An hoặc 0901…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
        }
      />
      {error && <ErrorBox error={error} onRetry={() => mutate()} />}
      {!data ? (
        <Spinner />
      ) : data.length === 0 ? (
        <EmptyState title={`Không có học viên khớp “${q}”`} />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {data.map((s) => (
            <li key={s.id}>
              <Link
                href={`/students/${s.id}`}
                className="flex h-full gap-3 rounded-2xl bg-surface p-4 shadow-card transition-[box-shadow] duration-150 hover:shadow-lift"
              >
                <Avatar name={s.ho_ten} />
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="truncate font-semibold">{s.ho_ten}</span>
                    <span className="shrink-0 font-mono text-xs text-fg-tertiary">HV{String(s.id).padStart(4, "0")}</span>
                  </span>
                  <span className="block truncate text-fg-secondary">{s.email}</span>
                  <span className="num block text-fg-secondary">{s.so_dien_thoai}</span>
                  <span className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-fg-secondary">
                    <span className="inline-flex items-center gap-1">
                      <MapPin className="size-3.5" aria-hidden />
                      {s.thanh_pho}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <BookOpen className="size-3.5" aria-hidden />
                      {s.so_lop_dang_hoc ? `${s.so_lop_dang_hoc} lớp đang học` : "Không có lớp đang học"}
                    </span>
                  </span>
                  <span className="mt-2.5 flex flex-wrap items-center justify-between gap-2 border-t border-dashed border-line-strong pt-2.5 text-xs">
                    <span className="text-fg-tertiary">
                      {SOURCE[s.nguon] ?? s.nguon} · từ {fmtDate(s.ngay_dang_ky)}
                    </span>
                    <span className="flex flex-wrap gap-1.5">
                      {!s.co_tai_khoan && <Badge>Chưa có tài khoản</Badge>}
                      {s.con_no > 0 ? <Badge tone="warning">Còn nợ {vnd(s.con_no)}</Badge> : <Badge tone="success">Đã đóng đủ</Badge>}
                    </span>
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {data && <LoadMore shown={data.length} total={list.total} noun="học viên" hasMore={list.hasMore} loading={list.loadingMore} onMore={list.loadMore} />}
    </>
  );
}
