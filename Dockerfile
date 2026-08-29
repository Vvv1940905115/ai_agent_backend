# ============ AI Agent 业务后端 Dockerfile ============
FROM python:3.11-slim

# pip 镜像源（默认阿里云；清华源在本机实测会出现 SSL 握手失败，故改用阿里源）
# 如需换源，构建时覆盖：
#   docker build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple -t ai-agent-backend:1.0.0 .
# 海外服务器可设为 https://pypi.org/simple
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL}

WORKDIR /app

# 先装依赖层（利用构建缓存）
COPY requirements.txt .
# 先按 PIP_INDEX_URL 安装；若因镜像源证书/网络问题失败，自动回退 PyPI 官方源重试
RUN pip install --no-cache-dir -r requirements.txt \
    || pip install --no-cache-dir -i https://pypi.org/simple -r requirements.txt

# 拷贝源码
COPY . .

# 向量库等持久化目录
RUN mkdir -p /app/data/vector_store /app/logs

# 以非 root 运行，提升安全性
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 容器健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000"]
