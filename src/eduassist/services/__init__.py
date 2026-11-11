"""Tầng Service: MỘT chỗ duy nhất chứa luật nghiệp vụ.

API cho giao diện web, tool của agent hội thoại và agent chạy nền đều gọi các hàm ở đây, nên agent
chịu đúng luật và đúng phân quyền như một nhân viên cùng vai trò - kể cả khi LLM bị dẫn dắt sai.

Quy ước:
- Mọi hàm nhận `conn` (psycopg, dict_row) làm tham số đầu. Người gọi quyết định ranh giới transaction
  (API: một transaction mỗi request) -> thay đổi dữ liệu, audit và sự kiện outbox cùng commit hoặc cùng huỷ.
- Mọi hàm ghi nhận `actor` và tự kiểm tra quyền (require), không tin vào việc người gọi đã kiểm tra.
- Vi phạm luật -> raise RuleViolation với thông điệp tiếng Việt đọc được (hiện thẳng cho người dùng / LLM).
"""
