import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Điều khoản sử dụng",
  description: "Điều khoản sử dụng website và cổng học viên của Trung tâm Ánh Dương.",
  alternates: { canonical: "/dieu-khoan" },
};

export default function TermsPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 pt-12 sm:px-6">
      <p role="note" className="rounded-xl bg-warning-subtle px-4 py-3 text-warning-fg text-pretty">
        Bản mẫu cho dự án demo. Trước khi dùng cho trung tâm thật, nội dung cần được người có chuyên môn pháp lý rà soát.
      </p>
      <h1 className="font-display mt-8 text-4xl font-medium text-balance">Điều khoản sử dụng</h1>
      <div className="prose-doc mt-6">
        <h2>1. Thông tin trên website</h2>
        <p>
          Học phí, lịch khai giảng và số chỗ trống được cập nhật từ hệ thống quản lý của trung tâm. Thông tin chính thức cho từng lớp là
          thông tin trên phiếu ghi danh của bạn.
        </p>
        <h2>2. Trợ lý tư vấn AI</h2>
        <p>
          Câu trả lời của trợ lý được tạo tự động từ tài liệu của trung tâm và có thể chưa đầy đủ. Với quyết định về học phí, hoàn phí,
          bảo lưu, vui lòng xác nhận với tư vấn viên hoặc xem <Link href="/chinh-sach">chính sách</Link>.
        </p>
        <h2>3. Tài khoản cổng học viên</h2>
        <ul>
          <li>Tài khoản do trung tâm cấp cho học viên đã ghi danh. Bạn tự đặt mật khẩu qua link kích hoạt gửi về email.</li>
          <li>Không chia sẻ mật khẩu. Nếu nghi tài khoản bị lộ, đổi mật khẩu và chọn "Đăng xuất mọi thiết bị".</li>
        </ul>
        <h2>4. Hành vi không được phép</h2>
        <p>Gửi thông tin giả mạo, dùng công cụ tự động gửi form hàng loạt, cố truy cập dữ liệu không thuộc về mình.</p>
        <h2>5. Liên hệ</h2>
        <p>
          Hotline 1900 0000 · <a href="mailto:tuvan@anhduong.example">tuvan@anhduong.example</a>
        </p>
      </div>
    </div>
  );
}
