FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim

WORKDIR /app

ARG BUILD_COMMIT=unknown
ENV BUILD_COMMIT=${BUILD_COMMIT}
ENV TZ=Asia/Shanghai

# 安装时区数据
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*

# 先复制依赖描述，利用 Docker layer cache 加速构建
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 再复制项目代码
COPY . .

EXPOSE 5000
ENV PORT=5000

CMD ["uv", "run", "--frozen", "run.py"]
