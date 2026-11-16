"use client";

import useSWRInfinite from "swr/infinite";
import { apiPage, type Paged } from "@/lib/api";

/** Danh sách phân trang kiểu "Tải thêm". Đổi path (bộ lọc, ô tìm kiếm) thì quay về trang đầu. */
export function usePaged<T>(path: string | null, pageSize = 100) {
  const sep = path?.includes("?") ? "&" : "?";
  const { data, error, size, setSize, mutate, isValidating } = useSWRInfinite<Paged<T>>(
    (index, prev: Paged<T> | null) => {
      if (!path) return null;
      if (prev && prev.items.length < pageSize) return null; // trang trước đã là trang cuối
      return `${path}${sep}limit=${pageSize}&offset=${index * pageSize}`;
    },
    (key: string) => apiPage<T>(key),
    { revalidateFirstPage: true },
  );
  const items = data?.flatMap((p) => p.items);
  const total = data?.[0]?.total ?? 0;
  return {
    items,
    total,
    error,
    mutate,
    hasMore: !!items && items.length < total,
    loadingMore: isValidating && !!data && size > data.length,
    loadMore: () => setSize(size + 1),
  };
}
