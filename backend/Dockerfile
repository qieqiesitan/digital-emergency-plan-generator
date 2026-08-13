FROM python:3.12-slim

WORKDIR /app

# Playwright Chromium 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libnss3 libnspr4 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2t64 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
ENV PIP_DEFAULT_TIMEOUT=300 PIP_RETRIES=10
RUN pip install --no-cache-dir -r requirements.txt
# rapidocr 依赖会带入 opencv-python（GUI 版），与 headless 并存会破坏 cv2 包：卸载并用 headless 重建
RUN pip uninstall -y opencv-python \
    && pip install --no-deps --force-reinstall "opencv-python-headless>=4.10,<5"

# 安装 Chromium 浏览器
RUN playwright install chromium --with-deps

COPY . .

RUN mkdir -p exports uploads

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
