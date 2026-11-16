# 小宠百问 H5 —— 通用 Docker 镜像
# 适配 Render / Hugging Face Spaces / 任意支持 Docker 的免费平台
# 本地跑：docker build -t xiaochong . && docker run -p 8080:8080 -e PORT=8080 xiaochong
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

# 少数依赖（py-ip2region）在部分架构上要现场编译，装完即卸掉编译链
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY . .

# 平台多以非 root 用户（HF 要求 UID 1000）挂载运行，数据目录必须可写
RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
    CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/api/health'%os.environ.get('PORT','8080'),timeout=4)"

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips=*"]
