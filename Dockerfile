# 使用轻量级 Python 镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装必要的系统依赖 (针对 numpy/pandas 等)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目源代码
COPY src/ /app/src/
COPY data/ /app/data/

# 设置 PYTHONPATH 确保模块导入正常
ENV PYTHONPATH=/app

# 暴露 FastAPI 默认端口
EXPOSE 8000

# 启动服务
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
