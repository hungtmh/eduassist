// Gọi API công khai từ server component (SEO: trang được render sẵn nội dung).
// Trong Docker, server web gọi API qua mạng nội bộ (API_INTERNAL_URL=http://api:8000); trình duyệt dùng NEXT_PUBLIC_API_URL.
import "server-only";

const BASE = process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class PublicNotFound extends Error {}

/** Dữ liệu được cache 5 phút (ISR). Trả null nếu API tạm lỗi để trang vẫn hiện khung, không sập. */
export async function pub<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${BASE}${path}`, { next: { revalidate: 300 } });
    if (res.status === 404) throw new PublicNotFound(path);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch (e) {
    if (e instanceof PublicNotFound) throw e;
    return null;
  }
}

export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(/\/$/, "");

export type PublicCourse = {
  id: number;
  slug: string;
  ma: string;
  ten: string;
  danh_muc: string;
  trinh_do: string;
  hoc_phi: number;
  so_buoi: number;
  mo_ta_ngan: string;
  khai_giang_gan_nhat?: string | null;
  so_lop_sap_mo?: number;
  hinh_thuc?: string[] | null;
};

export type PublicClass = {
  id: number;
  ma_lop: string;
  slug: string;
  khoa_hoc: string;
  danh_muc: string;
  hoc_phi: number;
  ngay_khai_giang: string;
  ca_hoc: "sang" | "chieu" | "toi";
  lich_hoc: string;
  hinh_thuc: "online" | "offline";
  co_so: string | null;
  giang_vien: string | null;
  cho_trong: number;
};

export type CourseDetail = PublicCourse & {
  mo_ta: string;
  doi_tuong: string | null;
  ket_qua: string | null;
  lo_trinh: { ten: string; noi_dung: string }[];
  lop_sap_mo: PublicClass[];
  giang_vien: { ho_ten: string; chuyen_mon: string; tieu_su: string | null }[];
  tra_gop: boolean;
  lien_quan: PublicCourse[];
};

export type Center = {
  so_khoa: number;
  so_hoc_vien: number;
  so_lop: number;
  so_giang_vien: number;
  co_so: { ten: string; dia_chi: string }[];
  giang_vien: { ho_ten: string; chuyen_mon: string; tieu_su: string | null }[];
  danh_muc: { danh_muc: string; so_khoa: number; hoc_phi_tu: number }[];
};

export type PolicyInfo = { slug: string; tieu_de: string; muc: string[] };
export type Policy = PolicyInfo & { noi_dung: string };
