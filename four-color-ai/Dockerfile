FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
ENV PIP_DEFAULT_TIMEOUT=300 PIP_RETRIES=10
RUN pip install --no-cache-dir -r requirements.txt
# rapidocr 依赖会带入 opencv-python（GUI 版），与 headless 并存会破坏 cv2 包：卸载并用 headless 重建
RUN pip uninstall -y opencv-python \
    && pip install --no-deps --force-reinstall "opencv-python-headless>=4.10,<5"

COPY app ./app
COPY models ./models

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
