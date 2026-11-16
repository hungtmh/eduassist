import type { MetadataRoute } from "next";
import { type PolicyInfo, type PublicCourse, SITE_URL, pub } from "@/lib/public-api";

export const dynamic = "force-dynamic";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [courses, policies] = await Promise.all([pub<PublicCourse[]>("/public/courses"), pub<PolicyInfo[]>("/public/policies")]);
  const now = new Date();
  const page = (path: string, priority: number, changeFrequency: "daily" | "weekly" | "monthly" = "weekly") => ({
    url: `${SITE_URL}${path}`,
    lastModified: now,
    changeFrequency,
    priority,
  });
  return [
    page("/", 1, "daily"),
    page("/khoa-hoc", 0.9, "daily"),
    page("/lich-khai-giang", 0.9, "daily"),
    page("/dang-ky-tu-van", 0.8, "monthly"),
    page("/gioi-thieu", 0.6, "monthly"),
    page("/chinh-sach", 0.5, "monthly"),
    ...(courses ?? []).map((c) => page(`/khoa-hoc/${c.slug}`, 0.8)),
    ...(policies ?? []).map((p) => page(`/chinh-sach/${p.slug}`, 0.4, "monthly")),
    page("/quyen-rieng-tu", 0.2, "monthly"),
    page("/dieu-khoan", 0.2, "monthly"),
  ];
}
