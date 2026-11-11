"""Agent chạy nền: tự chạy theo lịch hoặc khi có sự kiện (outbox), không cần ai hỏi.

Mỗi agent là một "nhân viên số" có vai trò (AGENTS[...].role): đề xuất của nó đi qua proposals.submit,
tức là qua mức tự chủ của từng loại thao tác, và khi thực thi thì gọi đúng hàm của tầng Service.
"""
