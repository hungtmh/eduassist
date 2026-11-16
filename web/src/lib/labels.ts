// Nhãn hiển thị cho mã trạng thái của backend. Một mã - một nhãn - một tông màu, dùng thống nhất mọi màn hình.
export type Tone = "neutral" | "accent" | "success" | "warning" | "danger" | "agent";

type Label = [string, Tone];

export const LEAD_STATUS: Record<string, Label> = {
  moi: ["Mới", "accent"],
  da_lien_he: ["Đã liên hệ", "neutral"],
  hen_hoc_thu: ["Hẹn học thử", "warning"],
  da_ghi_danh: ["Đã ghi danh", "success"],
  khong_tiep_tuc: ["Không tiếp tục", "neutral"],
};

export const ENROLL_STATUS: Record<string, Label> = {
  cho_thanh_toan: ["Chờ thanh toán", "warning"],
  dang_hoc: ["Đang học", "success"],
  bao_luu: ["Bảo lưu", "neutral"],
  tam_dung: ["Tạm dừng", "danger"],
  hoan_thanh: ["Hoàn thành", "neutral"],
  da_huy: ["Đã huỷ", "neutral"],
};

export const INVOICE_STATUS: Record<string, Label> = {
  chua_thanh_toan: ["Chưa thanh toán", "warning"],
  thanh_toan_mot_phan: ["Đóng một phần", "warning"],
  da_thanh_toan: ["Đã thanh toán", "success"],
  da_huy: ["Đã huỷ", "neutral"],
  da_hoan_tien: ["Đã hoàn tiền", "neutral"],
};

export const INSTALLMENT_STATUS: Record<string, Label> = {
  chua_thanh_toan: ["Chưa đóng", "neutral"],
  da_thanh_toan: ["Đã đóng", "success"],
  qua_han: ["Quá hạn", "danger"],
  da_huy: ["Đã huỷ", "neutral"],
};

export const CLASS_STATUS: Record<string, Label> = {
  sap_khai_giang: ["Sắp khai giảng", "accent"],
  dang_hoc: ["Đang học", "success"],
  da_ket_thuc: ["Đã kết thúc", "neutral"],
  da_huy: ["Đã huỷ", "neutral"],
};

export const PROPOSAL_STATUS: Record<string, Label> = {
  goi_y: ["Gợi ý", "accent"],
  da_xem: ["Đã xem", "neutral"],
  cho_duyet: ["Chờ duyệt", "warning"],
  da_duyet: ["Đã duyệt", "accent"],
  da_thuc_hien: ["Đã thực hiện", "success"],
  that_bai: ["Thất bại", "danger"],
  tu_choi: ["Đã từ chối", "neutral"],
  het_han: ["Hết hạn", "neutral"],
};

export const REQUEST_STATUS: Record<string, Label> = {
  moi: ["Mới", "accent"],
  dang_xu_ly: ["Đang xử lý", "warning"],
  da_xu_ly: ["Đã xử lý", "success"],
  tu_choi: ["Từ chối", "neutral"],
};

export const ATTENDANCE: Record<string, Label> = {
  co_mat: ["Có mặt", "success"],
  di_tre: ["Đi trễ", "warning"],
  vang: ["Vắng", "danger"],
  vang_co_phep: ["Vắng có phép", "neutral"],
};

export const LEVEL: Record<string, Label> = {
  L0: ["L0 · Gợi ý", "neutral"],
  L1: ["L1 · Cần duyệt", "warning"],
  L2: ["L2 · Tự động", "success"],
  cam: ["Cấm", "danger"],
};

export const AGENT_LABEL: Record<string, string> = {
  cong_no: "Công nợ",
  tuyen_sinh: "Tuyển sinh",
  giao_vu: "Giáo vụ",
  cham_soc: "Chăm sóc",
  bao_cao: "Báo cáo",
  van_hanh: "Vận hành (chat)",
};

export const SHIFT: Record<string, string> = { sang: "Sáng", chieu: "Chiều", toi: "Tối" };
export const SOURCE: Record<string, string> = {
  facebook: "Facebook",
  zalo: "Zalo",
  gioi_thieu: "Giới thiệu",
  website: "Website",
  tiktok: "TikTok",
  walk_in: "Đến trực tiếp",
};
export const REQUEST_KIND: Record<string, string> = {
  bao_luu: "Bảo lưu",
  hoan_phi: "Hoàn phí",
  chuyen_lop: "Chuyển lớp",
  khac: "Khác",
};
export const PAY_METHOD: Record<string, string> = { chuyen_khoan: "Chuyển khoản", tien_mat: "Tiền mặt", the: "Thẻ" };

export const label = (map: Record<string, Label>, key: string): Label => map[key] ?? [key, "neutral"];

export const ROLE: Record<string, string> = {
  student: "Học viên",
  consultant: "Tư vấn viên",
  academic: "Giáo vụ",
  accountant: "Kế toán",
  teacher: "Giảng viên",
  manager: "Quản lý",
};
export const STAFF_ROLES = ["consultant", "academic", "accountant", "teacher", "manager"] as const;
