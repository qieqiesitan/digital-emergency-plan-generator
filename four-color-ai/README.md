# four-color-ai

四色分布图识别独立服务（无状态）。识别管线/OCR/CLIP 复用主仓库
`backend/app/services/four_color_recognizer.py` 与 `vision_helpers.py`，
模型资产位于 `models/`（不入库，需从 `backend/models/` 复制）。

## 本地运行

```powershell
$env:FOUR_COLOR_API_KEY='dev-key'
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

## 测试

```powershell
backend\.venv\Scripts\python.exe -m pytest tests -q
```

## Docker 部署

```powershell
docker build -t four-color-ai .
docker run -d --name four-color-ai -p 8000:8000 -e FOUR_COLOR_API_KEY=your-key four-color-ai
```

默认使用官方 PyPI 源；国内网络构建缓慢时可自行在 Dockerfile 中配置清华镜像
（`pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple`）。

## 接口

- `GET /healthz`：健康检查（无需鉴权）
- `POST /api/v1/four-color/analyze`：识别（需 `X-API-Key` 头）
- 接口文档（OpenAPI）：启动后访问 `/docs`，供 Java 调用方与前后端核对契约

请求：`{"image_base64": "<图片 base64>", "options": {"canvas_width": 1600, "canvas_height": 1000}}`
响应：`code=0` 时 `data` 含 `zones / texts / excluded / warnings / preview_png_base64 / canvas_width / canvas_height`。
错误：400 `INVALID_IMAGE` / 422 `NO_ZONE_DETECTED` / 500 `INTERNAL` / 503 `MODEL_UNAVAILABLE`。
完整契约见 `docs/superpowers/specs/2026-08-07-four-color-ai-microservice-design.md` 第 5 节。
