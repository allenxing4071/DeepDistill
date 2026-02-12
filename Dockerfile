# DeepDistill 后端 Dockerfile
# 多源内容深度蒸馏引擎 — API + 管线处理

FROM python:3.11-slim

WORKDIR /app

# 系统依赖（ffmpeg 用于视频/音频处理）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 创建数据目录
RUN mkdir -p data/output data/uploads

# 暴露端口
EXPOSE 8000

# 启动服务
CMD ["uvicorn", "deepdistill.api:app", "--host", "0.0.0.0", "--port", "8000"]
