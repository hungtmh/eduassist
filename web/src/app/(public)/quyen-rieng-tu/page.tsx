import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Chính sách quyền riêng tư",
  description: "Trung tâm Ánh Dương thu thập, sử dụng và bảo vệ thông tin cá nhân của khách và học viên như thế nào.",
  alternates: { canonical: "/quyen-rieng-tu" },
};

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 pt-12 sm:px-6">
      <p role="note" className="rounded-xl bg-warning-subtle px-4 py-3 text-warning-fg text-pretty">
        Bản mẫu cho dự án demo. Trước khi dùng cho trung tâm thật, nội dung cần được người có chuyên môn pháp lý rà soát theo quy định
        hiện hành của Việt Nam về bảo vệ dữ liệu cá nhân.
      </p>
      <h1 className="font-display mt-8 text-4xl font-medium text-balance">Chính sách quyền riêng tư</h1>
      <div className="prose-doc mt-6">
        <h2>1. Thông tin trung tâm thu thập</h2>
        <ul>
          <li>Khi bạn đăng ký tư vấn: họ tên, số điện thoại, email (nếu có), khoá học quan tâm và nhu cầu bạn ghi.</li>
          <li>Khi bạn ghi danh: thêm năm sinh, thành phố, thông tin thanh toán học phí, điểm danh và kết quả học tập.</li>
          <li>Khi bạn dùng khung chat tư vấn: nội dung câu hỏi. Trung tâm không lưu lịch sử chat của khách chưa đăng nhập.</li>
        </ul>
        <h2>2. Mục đích sử dụng</h2>
        <ul>
          <li>Liên hệ tư vấn, sắp xếp học thử, xếp lớp, nhắc lịch học và học phí.</li>
          <li>Hỏi thăm khi bạn vắng học hoặc cần hỗ trợ thêm, cấp chứng nhận hoàn thành khoá học.</li>
          <li>Thống kê nội bộ để cải thiện chất lượng đào tạo (số liệu tổng hợp, không nêu tên).</li>
        </ul>
        <h2>3. Trợ lý AI và nhà cung cấp dịch vụ</h2>
        <p>
          Trung tâm dùng trợ lý AI để trả lời câu hỏi trên website và hỗ trợ nhân viên soạn tin. Câu hỏi bạn gõ vào khung chat được gửi tới
          nhà cung cấp mô hình ngôn ngữ (có máy chủ ở nước ngoài) để tạo câu trả lời. Trung tâm che email và số điện thoại trong dữ liệu
          nội bộ trước khi gửi cho AI, nhưng không che được nội dung bạn tự gõ: vui lòng không nhập thông tin cá nhân vào khung chat.
        </p>
        <p>Email được gửi qua nhà cung cấp dịch vụ email. Các nhà cung cấp chỉ xử lý dữ liệu để thực hiện dịch vụ cho trung tâm.</p>
        <h2>4. Thời gian lưu trữ</h2>
        <p>
          Thông tin đăng ký tư vấn được lưu trong thời gian trung tâm còn liên hệ tư vấn với bạn. Hồ sơ học viên được lưu trong thời gian
          học và theo thời hạn pháp luật yêu cầu với chứng từ học phí.
        </p>
        <h2>5. Quyền của bạn</h2>
        <ul>
          <li>Yêu cầu xem, sửa thông tin của mình.</li>
          <li>Rút lại đồng ý, yêu cầu ngừng liên hệ hoặc xoá thông tin đăng ký tư vấn.</li>
          <li>Từ chối nhận email giới thiệu khoá học bất cứ lúc nào.</li>
        </ul>
        <p>
          Gửi yêu cầu tới <a href="mailto:tuvan@anhduong.example">tuvan@anhduong.example</a> hoặc gọi 1900 0000. Trung tâm phản hồi trong
          thời hạn pháp luật quy định.
        </p>
        <h2>6. Bảo mật</h2>
        <p>
          Dữ liệu được truyền qua kết nối mã hoá (HTTPS), chỉ nhân viên có vai trò phù hợp mới xem được, mọi thao tác thay đổi dữ liệu đều
          được ghi nhật ký. Mật khẩu được lưu ở dạng băm, nhân viên trung tâm cũng không xem được.
        </p>
      </div>
    </div>
  );
}
