"""Cấu hình đọc từ biến môi trường / file .env (có kiểm tra kiểu)."""
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    groq_api_key: SecretStr = SecretStr("")
    llm_model: str = "openai/gpt-oss-120b"
    llm_fallback_model: str = "llama-3.3-70b-versatile"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # Database: app_rw = chủ sở hữu schema; agent_ro = chỉ SELECT (dùng cho Text-to-SQL)
    database_url: str = "postgresql://app_rw:app_rw_dev_pw@localhost:5433/eduassist"
    agent_ro_url: str = "postgresql://agent_ro:agent_ro_dev_pw@localhost:5433/eduassist"
    agent_ro_password: SecretStr = SecretStr("agent_ro_dev_pw")

    # API
    jwt_secret: SecretStr = SecretStr("dev-only-change-me")
    jwt_ttl_minutes: int = 8 * 60
    rate_limit_per_minute: int = 20

    # Email
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "tuvan@anhduong.example"

    # Langfuse (tuỳ chọn)
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_host: str = "https://cloud.langfuse.com"

    # Giới hạn an toàn cho agent
    sql_row_limit: int = 200
    sql_timeout_ms: int = 5000
    max_tool_calls_per_turn: int = 12

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
