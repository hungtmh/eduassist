import type { Metadata } from "next";
import { Be_Vietnam_Pro, Fraunces, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";

const sans = Be_Vietnam_Pro({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-be-vietnam",
  display: "swap",
});
// Serif cho tiêu đề: trục opsz giúp chữ lớn thanh mảnh, chữ nhỏ vẫn chắc
const display = Fraunces({
  subsets: ["latin", "vietnamese"],
  axes: ["opsz", "SOFT"],
  variable: "--font-fraunces",
  display: "swap",
});
const mono = JetBrains_Mono({ subsets: ["latin", "vietnamese"], weight: ["400", "500"], variable: "--font-jetbrains", display: "swap" });

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: { default: "Trung tâm Đào tạo Ánh Dương", template: "%s · Trung tâm Ánh Dương" },
  description: "Khoá học ngoại ngữ, tin học, lập trình, phân tích dữ liệu và kỹ năng mềm. Học thử miễn phí, trả góp học phí.",
  openGraph: { siteName: "Trung tâm Đào tạo Ánh Dương", locale: "vi_VN", type: "website" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi" className={`${sans.variable} ${display.variable} ${mono.variable}`}>
      <body className="min-h-dvh text-sm">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
