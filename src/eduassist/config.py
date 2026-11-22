"""Cấu hình đọc từ biến môi trường / file .env (có kiểm tra kiểu)."""

import os
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Giá trị chỉ dùng khi phát triển trên máy. Chạy production mà còn giá trị nào trong đây -> từ chối khởi động.
# Số luồng chừa cho các bước đồng bộ ngắn của chat (kiểm tra đăng nhập, đọc hội thoại) - xem _admission_fits_thread_pool
STREAM_THREAD_RESERVE = 16

DEV_SECRETS = {"dev-only-change-me", "app_rw_dev_pw", "agent_ro_dev_pw", ""}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # development: chạy trên máy. production: bắt buộc khoá bí mật mạnh, tắt /docs.
    app_env: Literal["development", "production"] = "development"
    # Dữ liệu giả lập + tài khoản demo (mật khẩu demo123) + nút đăng nhập nhanh. Production đặt DEMO_MODE=false.
    demo_mode: bool = True
    # Địa chỉ web người dùng mở (dùng để tạo link đặt lại mật khẩu trong email)
    public_web_url: str = "http://localhost:3000"

    # LLM
    groq_api_key: SecretStr = SecretStr("")
    llm_model: str = "openai/gpt-oss-120b"
    llm_fallback_model: str = "openai/gpt-oss-20b"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # Database: app_rw = chủ sở hữu schema; agent_ro = chỉ SELECT (dùng cho Text-to-SQL)
    database_url: str = "postgresql://app_rw:app_rw_dev_pw@localhost:5433/eduassist"
    agent_ro_url: str = "postgresql://agent_ro:agent_ro_dev_pw@localhost:5433/eduassist"
    agent_ro_password: SecretStr = SecretStr("agent_ro_dev_pw")

    # API
    jwt_secret: SecretStr = SecretStr("dev-only-change-me")
    jwt_ttl_minutes: int = 8 * 60
    rate_limit_per_minute: int = 20

    # Đăng nhập: giới hạn theo IP + khoá tạm tài khoản sau nhiều lần sai
    login_rate_per_minute: int = 10
    login_max_failures: int = 5
    login_lockout_minutes: int = 15
    password_reset_minutes: int = 30
    account_activation_days: int = 7

    # Web công khai: form tư vấn và chat cho khách chưa đăng nhập
    public_chat_enabled: bool = True
    public_chat_per_minute: int = 6  # mỗi IP
    public_chat_global_per_minute: int = 60  # tổng mọi khách (chặn đốt hạn mức LLM)
    public_lead_per_minute: int = 3  # mỗi IP

    # Email
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "tuvan@anhduong.example"
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    # starttls: cổng 587 · ssl: cổng 465 · none: Mailpit khi dev
    smtp_security: Literal["none", "starttls", "ssl"] = "none"

    # Theo dõi lỗi (tuỳ chọn). Cần cài nhóm dependency obs.
    sentry_dsn: str = ""

    # Langfuse (tuỳ chọn)
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")
    # Nhận cả hai tên: SDK Langfuse và trang hướng dẫn của Langfuse dùng LANGFUSE_BASE_URL, bản cũ dùng LANGFUSE_HOST
    langfuse_host: str = Field(
        "https://cloud.langfuse.com", validation_alias=AliasChoices("LANGFUSE_HOST", "LANGFUSE_BASE_URL")
    )

    # Kết nối database (mỗi tiến trình). Tổng mọi tiến trình phải nhỏ hơn max_connections của Postgres
    # (mặc định 100) - khi chạy nhiều bản API hãy đặt PgBouncer phía trước, xem docs/SCALING_PLAN.md.
    db_pool_size: int = 10  # pool chính (app_rw) cho nghiệp vụ
    db_auth_pool_size: int = 4  # pool riêng cho bước kiểm tra đăng nhập của mỗi request
    db_async_pool_size: int = 10  # pool async của chat (lưu trạng thái hội thoại LangGraph)
    db_pool_timeout: float = 5.0  # chờ kết nối tối đa (giây), quá thì trả 503 thay vì treo
    db_statement_timeout_ms: int = 15000  # một câu SQL chạy quá lâu thì Postgres tự huỷ
    # Kết nối đang mở transaction mà đứng im quá lâu (code treo giữa transaction) -> Postgres đóng, nhả khoá dòng
    db_idle_in_transaction_timeout_ms: int = 60000
    # Chờ khoá (dòng / bảng đang bị transaction khác giữ) tối đa chừng này rồi báo lỗi -> 503. Ngắn hơn
    # statement_timeout:
    # diễn tập khoá một bảng cho thấy request chờ khoá 15 giây chiếm hết chỗ chạy, làm MỌI trang khác lỗi theo.
    db_lock_timeout_ms: int = 5000
    # Đi qua PgBouncer chế độ transaction: không gửi tham số khởi tạo phiên (PgBouncer không chuyển tiếp được, hai
    # timeout trên khi đó đặt bằng ALTER ROLE lúc chạy setup).
    db_via_pgbouncer: bool = False
    # PgBouncer >= 1.21 có max_prepared_statements: giữ prepared statement (rẻ CPU cho Postgres). Bản cũ: false.
    db_pgbouncer_prepared: bool = True
    # Bản sao chỉ đọc (tuỳ chọn): trang công khai và báo cáo đọc từ đây. Trống = đọc từ DATABASE_URL.
    database_read_url: str = ""

    # Redis (tuỳ chọn khi chạy 1 tiến trình, BẮT BUỘC khi chạy nhiều tiến trình / nhiều máy API): giới hạn lượt gọi,
    # giới hạn số lượt chat LLM toàn hệ thống, cache tài khoản. Trống = lưu trong RAM của từng tiến trình.
    redis_url: str = ""
    redis_timeout: float = 0.25  # giây chờ mỗi lệnh Redis; lỗi thì tạm dùng RAM 5 giây (eduassist/cache.py)
    redis_max_connections: int = 50
    # Kiểm soát cửa vào của mỗi tiến trình API (eduassist.api.overload). Bắt buộc:
    #   max_concurrent_requests + STREAM_THREAD_RESERVE < thread_pool_size
    # để luôn còn luồng trống cho request đang giữ kết nối DB chạy tiếp (nếu không sẽ kẹt khi tải cao).
    # Luồng chỉ được tạo khi cần và tự thoát sau 10 giây rảnh (anyio), nên số dư không tốn gì khi không dùng.
    thread_pool_size: int = 100  # số luồng chạy hàm def thường (FastAPI mặc định 40)
    max_concurrent_requests: int = 32  # request thường chạy cùng lúc; 0 = tắt kiểm soát
    max_queued_requests: int = 500  # xếp hàng trên event loop (không tốn luồng); hàng đầy -> 503
    queue_timeout_seconds: float = 3.0  # chờ trong hàng quá lâu -> 503
    max_concurrent_streams: int = 200  # chat SSE (async, không giữ luồng) chạy cùng lúc mỗi tiến trình, ngăn riêng

    # Chat LLM
    chat_turn_timeout_seconds: float = 45  # tổng thời gian tối đa một câu trả lời, kể cả các lần thử lại
    llm_max_concurrent: int = 30  # số lượt chat đang gọi LLM cùng lúc trên TOÀN hệ thống (cần Redis khi nhiều bản)
    llm_request_timeout_seconds: float = 25  # một lần gọi LLM
    chat_tool_threads: int = 64  # luồng chạy tool lá (SQL, RAG) của chat async, mỗi tiến trình

    # GET /metrics (Prometheus). Đặt token thì phải gửi Authorization: Bearer <token>.
    metrics_token: SecretStr = SecretStr("")

    # Giới hạn an toàn cho agent
    sql_row_limit: int = 200
    sql_timeout_ms: int = 5000
    max_tool_calls_per_turn: int = 12
    # Che email / số điện thoại trước khi đưa dữ liệu cho LLM (nhà cung cấp LLM ở nước ngoài)
    llm_mask_pii: bool = True

    # Web (Next.js) gọi API từ trình duyệt -> cần CORS. Nhiều origin cách nhau bằng dấu phẩy.
    cors_origins: str = "http://localhost:3000"

    # Agent chạy nền
    background_llm: bool = True  # False: chỉ dùng bản mẫu do code soạn (mô phỏng, đánh giá, khi hết hạn mức LLM)
    background_llm_timeout_seconds: float = 15  # một lần soạn lời văn; quá thì dùng bản mẫu
    worker_poll_seconds: int = 5
    # Nhịp tim của worker (eduassist-worker-alive, liveness probe trên K8s). Trống = thư mục tạm của hệ điều hành.
    worker_heartbeat_file: str = ""
    # Một vòng được phép chạy lâu chừng này (agent theo lịch có gọi LLM) trước khi bị coi là treo
    worker_heartbeat_grace_seconds: int = 600
    daily_run_hour: int = 7  # sau giờ này mỗi ngày, worker chạy các agent đến lịch

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @model_validator(mode="after")
    def _admission_fits_thread_pool(self) -> "Settings":
        # Chat đã async: luồng chat chỉ mượn luồng vài mili-giây ở bước kiểm tra đăng nhập, nên chỉ ngăn request
        # thường cần chừa chỗ. Chừa thêm STREAM_THREAD_RESERVE luồng cho các bước ngắn đó của chat.
        if self.max_concurrent_requests and (
            self.max_concurrent_requests + STREAM_THREAD_RESERVE >= self.thread_pool_size
        ):
            raise ValueError(
                f"MAX_CONCURRENT_REQUESTS + {STREAM_THREAD_RESERVE} phải nhỏ hơn THREAD_POOL_SIZE, "
                "nếu không API có thể kẹt cứng khi tải cao (xem eduassist/api/overload.py)."
            )
        return self

    @model_validator(mode="after")
    def _production_guard(self) -> "Settings":
        if not self.is_production:
            return self
        problems = []
        jwt = self.jwt_secret.get_secret_value()
        if jwt in DEV_SECRETS or len(jwt) < 32:
            problems.append("JWT_SECRET phải là chuỗi ngẫu nhiên dài ít nhất 32 ký tự")
        if self.agent_ro_password.get_secret_value() in DEV_SECRETS:
            problems.append("AGENT_RO_PASSWORD đang là giá trị mặc định")
        for name, url in (("DATABASE_URL", self.database_url), ("AGENT_RO_URL", self.agent_ro_url)):
            if any(f":{pw}@" in url for pw in DEV_SECRETS if pw):
                problems.append(f"{name} đang dùng mật khẩu mặc định")
        if "*" in self.cors_origins:
            problems.append("CORS_ORIGINS không được là *")
        if self.smtp_security == "none" and self.smtp_host not in ("localhost", "mailpit"):
            problems.append("SMTP_SECURITY=none chỉ dùng cho Mailpit; máy chủ email thật cần starttls hoặc ssl")
        workers = int(os.environ.get("WEB_CONCURRENCY") or 1)
        if workers > 1 and not self.redis_url:
            problems.append(
                f"WEB_CONCURRENCY={workers} cần REDIS_URL: không có Redis thì mỗi tiến trình tự đếm giới hạn đăng nhập"
                " (kẻ dò mật khẩu được thử gấp nhiều lần)"
            )
        if problems:
            raise ValueError("Cấu hình chưa an toàn cho production:\n- " + "\n- ".join(problems))
        return self

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
