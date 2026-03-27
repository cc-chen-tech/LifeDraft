# ==================== Stage 1: Builder ====================
FROM python:3.9-slim AS builder

# 设置工作目录
WORKDIR /app

# 安装系统依赖（仅构建时需要的）
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 创建虚拟环境并安装依赖
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ==================== Stage 2: Runtime ====================
FROM python:3.9-slim AS runtime

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# 安装运行时依赖（仅需要的最小依赖）
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 复制项目源代码（仅必要文件）
COPY src/ ./src/
COPY config/ ./config/
COPY run_api.py .
COPY start.sh .

# 创建数据目录（用于SQLite数据库和缓存）
RUN mkdir -p /app/data/cache /app/data/presets /app/data/images /app/logs && \
    chmod -R 755 /app/data /app/logs

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/health')" || exit 1

# 启动命令 - FastAPI 后端服务
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
