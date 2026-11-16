import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/public-api";

// Trang nội bộ (bàn làm việc, cổng học viên, tài khoản) không đưa lên công cụ tìm kiếm
const PRIVATE = [
  "/login",
  "/portal",
  "/dashboard",
  "/hom-nay",
  "/inbox",
  "/tasks",
  "/leads",
  "/classes",
  "/lich",
  "/students",
  "/finance",
  "/requests",
  "/agents",
  "/catalog",
  "/users",
  "/audit",
  "/doi-mat-khau",
  "/dat-mat-khau",
  "/quen-mat-khau",
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: PRIVATE }],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
