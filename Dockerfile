# Một image dùng chung cho api, worker, setup và ui Chainlit cũ (khác nhau ở command trong docker-compose.yml)
FROM python:3.12-slim

# Giờ Việt Nam: lịch agent (DAILY_RUN_HOUR), "hôm nay" của nghiệp vụ và hạn thanh toán đều theo giờ máy chủ
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.33 /uv /uvx /bin/

ENV TZ=Asia/Ho_Chi_Minh \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    FASTEMBED_CACHE_PATH=/opt/fastembed

WORKDIR /app

# Cài dependency trước (layer được cache khi chỉ đổi code)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --group ui --group obs --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev --group ui --group obs

# Tải sẵn model embedding (~200MB) lúc build -> container khởi động không cần internet
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

COPY sql ./sql
COPY migrations ./migrations
COPY alembic.ini ./
COPY data ./data
COPY ui ./ui
COPY .chainlit ./.chainlit
COPY chainlit.md ./

RUN useradd --create-home --uid 1000 app && chown -R app /app /opt/fastembed
USER app

EXPOSE 8000 8001
CMD ["uvicorn", "eduassist.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
