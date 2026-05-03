# Dockerfile
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 防止 Python 生成 .pyc 文件，并让日志直接输出
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安装系统依赖（如果需要）和 Python 依赖
# aiofiles 用于 FastAPI 高效处理静态文件
RUN pip install --no-cache-dir fastapi uvicorn jinja2 aiofiles python-multipart

# 复制当前目录下的所有文件到容器的 /app
COPY . .

# 暴露容器内部端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000","--reload"]