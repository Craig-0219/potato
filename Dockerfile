# Dockerfile for Potato Bot
FROM python:3.10-slim

# 設置工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    pkg-config \
    default-libmysqlclient-dev \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 複製專案文件
COPY pyproject.toml requirements*.txt ./
COPY bot/ ./bot/
COPY shared/ ./shared/
COPY scripts/ ./scripts/

# 安裝Python依賴
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# 創建非root用戶
RUN useradd --create-home --shell /bin/bash potato && \
    chown -R potato:potato /app
USER potato

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import bot.main; print('OK')" || exit 1

# 預設命令
CMD ["python", "-m", "bot.main"]
