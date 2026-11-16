import type { Metadata } from "next";
import { Shell } from "@/components/shell";

// Bàn làm việc nội bộ: không lập chỉ mục tìm kiếm
export const metadata: Metadata = { title: "EduAssist", robots: { index: false, follow: false } };

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <Shell>{children}</Shell>;
}
