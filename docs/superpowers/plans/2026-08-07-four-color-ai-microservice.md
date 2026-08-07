# 四色分布图识别微服务抽取 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 把四色分布图识别模块抽取为无状态独立 Python 服务（`four-color-ai/`），并提供 SpringCloud 调用方参考工程（`four-color-ai-java/`），原系统功能不受影响。

**架构：** 独立 FastAPI 服务只暴露 `POST /api/v1/four-color/analyze`（base64 入参、`X-API-Key` 鉴权、无状态），识别管线/OCR/CLIP 原样搬运自 `backend/`；Java 参考工程用 Feign + Resilience4j 调用，控制器返回 `CompletableFuture` 异步释放 Tomcat 线程，预览图由 `PreviewStorageService` 存盘转 URL 保持前端契约不变。

**技术栈：** Python 3.12 / FastAPI / OpenCV / RapidOCR / ONNX Runtime（服务侧，本机 backend/.venv 可完整验证）；Java 17 / Spring Boot 3.3.5 / Spring Cloud 2023.0.3 / OpenFeign / Resilience4j（参考工程，本机无 JDK，验证委托公司 Java 环境）。

**执行前环境事实（2026-08-07 实测）：**
- 本机无 JDK/Maven/Gradle → Java 任务中的 `mvn` 命令在公司 Java 环境执行，本地步骤只写代码与测试，**不得声称 Java 测试已通过**。
- `backend\.venv\Scripts\python.exe` 为 Python 3.12.8，已装 fastapi 0.115.0、pytest、httpx 0.27.2、cv2 4.14.0、rapidocr_onnxruntime、onnxruntime 1.28.0 → Python 侧全部验证用该解释器。
- `backend/models/clip_vision.onnx`（351MB）与 `clip_prompts.npz` 已存在，需复制到新服务（不入库）。
- 工作区他人改动（TASKS.md、chroma.sqlite3、backend/uploads/enterprises/）保持原样，不触碰。

---

## 文件结构

### 新建：`four-color-ai/`（独立 Python 识别服务）

| 文件 | 职责 |
|---|---|
| `app/__init__.py` | 包标记（空文件） |
| `app/main.py` | FastAPI 应用：`/healthz`、`X-API-Key` 依赖、`POST /api/v1/four-color/analyze` 全实现 |
| `app/services/__init__.py` | 包标记（空文件） |
| `app/services/four_color_recognizer.py` | 自 `backend/app/services/` 原样复制，识别管线（不改一行算法） |
| `app/services/vision_helpers.py` | 自 `backend/app/services/` 原样复制，RapidOCR + CLIP（不改一行） |
| `models/` | 复制自 `backend/models/`（CLIP 资产，.gitignore 排除，不入库） |
| `tests/__init__.py` | 包标记（空文件） |
| `tests/conftest.py` | sys.path bootstrap，任意目录可跑 pytest |
| `tests/test_four_color_recognizer.py` | 自 `backend/tests/` 原样复制，识别器单测 |
| `tests/test_main.py` | 服务级测试：healthz/鉴权/analyze 全分支 |
| `requirements.txt` | 运行时依赖（锁定版本） |
| `requirements-dev.txt` | 测试依赖（pytest、httpx） |
| `Dockerfile` | python:3.12-slim，打包 app + models |
| `.dockerignore` | 排除 .venv/__pycache__/tests/.git |
| `README.md` | 启动/测试/部署/接口/环境变量说明 |

### 新建：`four-color-ai-java/`（SpringCloud 调用方参考工程）

| 文件 | 职责 |
|---|---|
| `pom.xml` | Spring Boot 3.3.5 parent + Spring Cloud 2023.0.3 BOM + web/openfeign/circuitbreaker-resilience4j/starter-test |
| `src/main/resources/application.yml` | Feign 超时、Resilience4j 配置、Jackson SNAKE_CASE、AI 服务地址/密钥 |
| `src/main/java/com/example/fourcolorai/FourColorAiApplication.java` | 启动类 + `@EnableFeignClients` |
| `.../common/ApiResponse.java` | 统一响应包装 `{code,message,data}` |
| `.../dto/FourColorAnalyzeRequest.java` | 请求体（image_base64 + options） |
| `.../dto/FourColorAnalyzeResult.java` | 响应 data（zones/texts/excluded/preview 等） |
| `.../dto/FrontendAnalyzeResponse.java` | 前端契约响应（preview_url + 透传字段） |
| `.../exception/FourColorAiException.java` | 通用调用异常 |
| `.../exception/FourColorParseException.java` | 业务错误（422），不重试不熔断 |
| `.../exception/FourColorAiUnavailableException.java` | 基础设施错误（5xx/超时），触发重试熔断 |
| `.../client/FourColorAiClient.java` | Feign Client 接口 |
| `.../client/FourColorAiFeignConfig.java` | ErrorDecoder（422→Parse、5xx→Unavailable）+ X-API-Key 拦截器 |
| `.../config/AsyncConfig.java` | `@EnableAsync` + aiCallExecutor 线程池 |
| `.../config/PreviewWebConfig.java` | `/api/risk-management/previews/**` 静态资源映射到存储目录 |
| `.../service/FourColorAiFacade.java` | `@Retry` + `@CircuitBreaker` + fallback |
| `.../service/FourColorAiAsyncService.java` | `@Async` 包装，返回 `CompletableFuture` |
| `.../service/PreviewStorageService.java` | 存储接口 |
| `.../service/LocalPreviewStorageService.java` | 本地磁盘实现（base64 → 文件 → URL，路径清洗） |
| `.../web/FourColorController.java` | multipart 接收 → 异步调用 → 存储转换 → 前端契约 |
| `src/test/java/.../client/FourColorAiFeignConfigTest.java` | ErrorDecoder 映射单测 |
| `src/test/java/.../service/FourColorAiFacadeTest.java` | Facade 映射单测（Mockito） |
| `src/test/java/.../service/LocalPreviewStorageServiceTest.java` | 存储实现单测 |

### 修改：根目录 `.gitignore`

追加 `four-color-ai/models/`（模型资产不入库）。

---

## 任务 0：环境与骨架准备

**文件：**
- 创建：`four-color-ai/`（目录）、`app/__init__.py`、`app/services/__init__.py`、`tests/__init__.py`、`tests/conftest.py`
- 复制：`backend/app/services/four_color_recognizer.py`、`backend/app/services/vision_helpers.py`、`backend/tests/test_four_color_recognizer.py`、`backend/models/clip_vision.onnx`、`backend/models/clip_prompts.npz`
- 创建：`four-color-ai/requirements.txt`、`four-color-ai/requirements-dev.txt`
- 修改：`.gitignore`

- [ ] **步骤 1：创建目录并复制代码资产**

```powershell
New-Item -ItemType Directory -Force four-color-ai\app\services, four-color-ai\tests, four-color-ai\models | Out-Null
New-Item -ItemType File -Force four-color-ai\app\__init__.py, four-color-ai\app\services\__init__.py, four-color-ai\tests\__init__.py | Out-Null
Copy-Item backend\app\services\four_color_recognizer.py four-color-ai\app\services\
Copy-Item backend\app\services\vision_helpers.py four-color-ai\app\services\
Copy-Item backend\tests\test_four_color_recognizer.py four-color-ai\tests\
Copy-Item backend\models\clip_vision.onnx, backend\models\clip_prompts.npz four-color-ai\models\
```

预期：`four-color-ai\app\services\` 下两个 .py、`four-color-ai\models\` 下两个模型文件均存在。

- [ ] **步骤 2：写 conftest.py（任意目录可导入 app 包）**

`four-color-ai/tests/conftest.py`：

```python
"""Pytest bootstrap: make the four-color-ai package importable from any invocation directory."""
import os
import sys

SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)
```

- [ ] **步骤 3：写 requirements 文件**

`four-color-ai/requirements.txt`：

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
Pillow>=10.0.0
opencv-python-headless>=4.10,<5
numpy>=1.26
rapidocr_onnxruntime>=1.3.0
onnxruntime>=1.17
```

`four-color-ai/requirements-dev.txt`：

```
-r requirements.txt
pytest>=8.0
httpx>=0.27
```

- [ ] **步骤 4：更新 .gitignore（模型不入库）**

在根目录 `.gitignore` 的 `backend/models/` 行后追加：

```
four-color-ai/models/
```

- [ ] **步骤 5：跑现有识别器测试验证复制无破坏**

运行：

```powershell
backend\.venv\Scripts\python.exe -m pytest four-color-ai\tests\test_four_color_recognizer.py -q
```

预期：全部 PASS（现有识别器测试原样通过；若某用例依赖 backend 专属 fixture 除外，则按报错修复 import 路径，不改算法）。

- [ ] **步骤 6：Commit**

```powershell
git add four-color-ai .gitignore
git commit -m "chore(four-color-ai): scaffold standalone service with recognizer assets"
```

---

## 任务 1：FastAPI 应用骨架（/healthz + X-API-Key）

**文件：**
- 创建：`four-color-ai/app/main.py`
- 测试：`four-color-ai/tests/test_main.py`

- [ ] **步骤 1：编写失败的测试（healthz 与鉴权）**

`four-color-ai/tests/test_main.py`：

```python
"""四色识别服务服务级测试：healthz、鉴权、analyze 各分支。"""
import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import app

client = TestClient(app)

API_KEY = "test-key"


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    monkeypatch.setenv("FOUR_COLOR_API_KEY", API_KEY)


def _four_rect_png(width=600, height=450) -> bytes:
    img = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(img)
    for x0, y0, x1, y1, color in [
        (40, 40, 280, 180, (255, 0, 0)),
        (320, 40, 560, 180, (255, 127, 0)),
        (40, 230, 280, 410, (255, 255, 0)),
        (320, 230, 560, 410, (0, 0, 255)),
    ]:
        d.rectangle([x0, y0, x1, y1], fill=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_healthz_returns_200():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_analyze_requires_api_key():
    resp = client.post("/api/v1/four-color/analyze", json={})
    assert resp.status_code == 401


def test_analyze_rejects_wrong_api_key():
    resp = client.post(
        "/api/v1/four-color/analyze",
        headers={"X-API-Key": "wrong"},
        json={"image_base64": base64.b64encode(_four_rect_png()).decode("ascii")},
    )
    assert resp.status_code == 401
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```powershell
backend\.venv\Scripts\python.exe -m pytest four-color-ai\tests\test_main.py -v
```

预期：FAIL，报错 `ModuleNotFoundError: No module named 'app'`（main.py 尚未创建）。

- [ ] **步骤 3：编写最少实现代码**

`four-color-ai/app/main.py`：

```python
"""四色分布图识别独立服务：无状态推理，X-API-Key 鉴权。"""
import os

from fastapi import Depends, FastAPI, Header, HTTPException

API_KEY_ENV = "FOUR_COLOR_API_KEY"

app = FastAPI(title="four-color-ai", version="1.0.0")


def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    expected = os.environ.get(API_KEY_ENV, "")
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid api key")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/api/v1/four-color/analyze")
def analyze(_body: dict, _: None = Depends(require_api_key)) -> dict:
    raise HTTPException(status_code=501, detail="not implemented yet")
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```powershell
backend\.venv\Scripts\python.exe -m pytest four-color-ai\tests\test_main.py -v
```

预期：3 个测试全 PASS。

- [ ] **步骤 5：Commit**

```powershell
git add four-color-ai\app\main.py four-color-ai\tests\test_main.py
git commit -m "feat(four-color-ai): add FastAPI skeleton with healthz and api key auth"
```

---

## 任务 2：analyze 接口完整实现（TDD）

**文件：**
- 修改：`four-color-ai/app/main.py`（analyze 全实现）
- 修改：`four-color-ai/tests/test_main.py`（追加测试）

- [ ] **步骤 1：编写失败的测试（analyze 各分支）**

在 `four-color-ai/tests/test_main.py` 末尾追加：

```python
def _analyze_payload(png: bytes, options: dict | None = None) -> dict:
    return {
        "image_base64": base64.b64encode(png).decode("ascii"),
        "options": options or {},
    }


def test_analyze_happy_path_with_canvas_options():
    png = _four_rect_png()
    resp = client.post(
        "/api/v1/four-color/analyze",
        headers={"X-API-Key": API_KEY},
        json=_analyze_payload(png, {"canvas_width": 800, "canvas_height": 600}),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["canvas_width"] == 800
    assert data["canvas_height"] == 600
    assert len(data["zones"]) == 4
    assert data["preview_png_base64"].startswith("iVBOR")
    for zone in data["zones"]:
        for poly in zone["polygons"]:
            for point in poly["points"]:
                assert 0 <= point["x"] <= 100
                assert 0 <= point["y"] <= 100


def test_analyze_invalid_base64_returns_400():
    resp = client.post(
        "/api/v1/four-color/analyze",
        headers={"X-API-Key": API_KEY},
        json={"image_base64": "!!!not-base64!!!", "options": {}},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_IMAGE"


def test_analyze_no_zone_returns_422():
    white = Image.new("RGB", (300, 200), "white")
    buf = io.BytesIO()
    white.save(buf, format="PNG")
    resp = client.post(
        "/api/v1/four-color/analyze",
        headers={"X-API-Key": API_KEY},
        json=_analyze_payload(buf.getvalue()),
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "NO_ZONE_DETECTED"


def test_analyze_pipeline_error_returns_500(monkeypatch):
    def boom(_data):
        raise ValueError("pipeline boom")

    monkeypatch.setattr("app.main.recognize_from_bytes", boom)
    resp = client.post(
        "/api/v1/four-color/analyze",
        headers={"X-API-Key": API_KEY},
        json=_analyze_payload(_four_rect_png()),
    )
    assert resp.status_code == 500
    assert resp.json()["detail"]["code"] == "INTERNAL"


def test_analyze_model_unavailable_returns_503(monkeypatch):
    def no_model(_data):
        raise RuntimeError("缺少 opencv-python-headless 依赖")

    monkeypatch.setattr("app.main.recognize_from_bytes", no_model)
    resp = client.post(
        "/api/v1/four-color/analyze",
        headers={"X-API-Key": API_KEY},
        json=_analyze_payload(_four_rect_png()),
    )
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "MODEL_UNAVAILABLE"
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```powershell
backend\.venv\Scripts\python.exe -m pytest four-color-ai\tests\test_main.py -v
```

预期：新增 5 个测试 FAIL（analyze 返回 501），原有 3 个 PASS。

- [ ] **步骤 3：实现 analyze 完整逻辑（替换任务 1 的占位实现）**

`four-color-ai/app/main.py` 的 analyze 路由替换为：

```python
import base64
from uuid import uuid4

from pydantic import BaseModel, Field

from app.services.four_color_recognizer import build_output_image, recognize_from_bytes


class Options(BaseModel):
    max_zones: int = 200
    canvas_width: int = 1600
    canvas_height: int = 1000
    enable_ocr: bool = True
    enable_clip: bool = True


class AnalyzeRequest(BaseModel):
    image_base64: str
    options: Options = Field(default_factory=Options)


@app.post("/api/v1/four-color/analyze")
def analyze(body: AnalyzeRequest, _: None = Depends(require_api_key)) -> dict:
    try:
        raw = base64.b64decode(body.image_base64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail={"code": "INVALID_IMAGE", "message": "图片 base64 解码失败"})
    try:
        result = recognize_from_bytes(raw)
    except RuntimeError:
        raise HTTPException(status_code=503, detail={"code": "MODEL_UNAVAILABLE", "message": "识别模型未加载"})
    except Exception:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL", "message": "识别管线异常"})
    if not result.zones:
        raise HTTPException(status_code=422, detail={"code": "NO_ZONE_DETECTED", "message": "未识别到红/橙/黄/蓝色块"})
    if result.processed_image is None:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL", "message": "识别管线未产出预览图"})
    png_bytes, cw, ch = build_output_image(
        result.processed_image,
        result.width,
        result.height,
        max_size=(body.options.canvas_width, body.options.canvas_height),
    )
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "request_id": uuid4().hex,
            "width": result.width,
            "height": result.height,
            "canvas_width": cw,
            "canvas_height": ch,
            "preview_png_base64": base64.b64encode(png_bytes).decode("ascii"),
            "zones": result.zones,
            "texts": result.texts,
            "excluded": result.excluded,
            "warnings": result.warnings,
        },
    }
```

实现说明：`Options.max_zones/enable_ocr/enable_clip` 为契约预留（识别器阈值为常量），首版不透传；`canvas_width/canvas_height` 真实生效（传给 `build_output_image` 的 `max_size`）。

- [ ] **步骤 4：运行测试验证通过**

运行：

```powershell
backend\.venv\Scripts\python.exe -m pytest four-color-ai\tests\test_main.py -v
```

预期：8 个测试全 PASS（真实识别 + OCR/CLIP 均在 backend/.venv 可用）。

- [ ] **步骤 5：跑全量服务测试确认无回归**

运行：

```powershell
backend\.venv\Scripts\python.exe -m pytest four-color-ai\tests -q
```

预期：识别器单测 + 服务级测试全 PASS。

- [ ] **步骤 6：Commit**

```powershell
git add four-color-ai\app\main.py four-color-ai\tests\test_main.py
git commit -m "feat(four-color-ai): implement analyze endpoint with error contract"
```

---

## 任务 3：Dockerfile + .dockerignore + README

**文件：**
- 创建：`four-color-ai/Dockerfile`、`four-color-ai/.dockerignore`、`four-color-ai/README.md`

- [ ] **步骤 1：写 Dockerfile（复用 backend 镜像的 opencv 冲突规避）**

`four-color-ai/Dockerfile`：

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_DEFAULT_TIMEOUT=300 PIP_RETRIES=10
RUN pip install --no-cache-dir -r requirements.txt
# rapidocr 依赖会带入 opencv-python（GUI 版），与 headless 并存会破坏 cv2 包：卸载并用 headless 重建
RUN pip uninstall -y opencv-python \
    && pip install --no-deps --force-reinstall "opencv-python-headless>=4.10,<5"

COPY app ./app
COPY models ./models

ENV FOUR_COLOR_API_KEY=change-me
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **步骤 2：写 .dockerignore**

`four-color-ai/.dockerignore`：

```
__pycache__/
*.pyc
.venv/
tests/
.git/
.pytest_cache/
```

注意：**不要**排除 `models/`（构建镜像必须打包模型资产）。

- [ ] **步骤 3：写 README.md**

`four-color-ai/README.md`：

```markdown
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

## 接口

- `GET /healthz`：健康检查（无需鉴权）
- `POST /api/v1/four-color/analyze`：识别（需 `X-API-Key` 头）
- 接口文档（OpenAPI）：启动后访问 `/docs`，供 Java 调用方与前后端核对契约

请求：`{"image_base64": "<图片 base64>", "options": {"canvas_width": 1600, "canvas_height": 1000}}`
响应：`code=0` 时 `data` 含 `zones / texts / excluded / warnings / preview_png_base64 / canvas_width / canvas_height`。
错误：400 `INVALID_IMAGE` / 422 `NO_ZONE_DETECTED` / 500 `INTERNAL` / 503 `MODEL_UNAVAILABLE`。
完整契约见 `docs/superpowers/specs/2026-08-07-four-color-ai-microservice-design.md` 第 5 节。
```

- [ ] **步骤 4：构建镜像并验证容器可启动**

运行：

```powershell
docker build -t four-color-ai .
docker run -d --name four-color-ai-test -p 8011:8000 -e FOUR_COLOR_API_KEY=dev-key four-color-ai
Start-Sleep -Seconds 5
Invoke-RestMethod http://127.0.0.1:8011/healthz
docker rm -f four-color-ai-test
```

预期：healthz 返回 `status=ok`；构建失败时按报错修复 Dockerfile（最常见原因：pip 超时，已配清华源 + 300s 超时兜底）。

- [ ] **步骤 5：Commit**

```powershell
git add four-color-ai\Dockerfile four-color-ai\.dockerignore four-color-ai\README.md
git commit -m "build(four-color-ai): add docker image and service readme"
```

---

## 任务 4：Java 工程骨架（pom、配置、DTO、异常）

**文件：**
- 创建：`four-color-ai-java/pom.xml`、`src/main/resources/application.yml`、`FourColorAiApplication.java`、`common/ApiResponse.java`、`dto/FourColorAnalyzeRequest.java`、`dto/FourColorAnalyzeResult.java`、`dto/FrontendAnalyzeResponse.java`、三个异常类

- [ ] **步骤 1：写 pom.xml**

`four-color-ai-java/pom.xml`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.3.5</version>
        <relativePath/>
    </parent>
    <groupId>com.example</groupId>
    <artifactId>four-color-ai-client</artifactId>
    <version>1.0.0-SNAPSHOT</version>
    <name>four-color-ai-client</name>
    <description>四色分布图识别 AI 服务调用方参考工程</description>
    <properties>
        <java.version>17</java.version>
        <spring-cloud.version>2023.0.3</spring-cloud.version>
    </properties>
    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>org.springframework.cloud</groupId>
                <artifactId>spring-cloud-dependencies</artifactId>
                <version>${spring-cloud.version}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
        </dependencies>
    </dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-starter-openfeign</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-starter-circuitbreaker-resilience4j</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
```

- [ ] **步骤 2：写 application.yml（含 Jackson SNAKE_CASE，对接 AI 服务下划线字段）**

`four-color-ai-java/src/main/resources/application.yml`：

```yaml
server:
  port: 8080

spring:
  application:
    name: four-color-ai-client
  jackson:
    property-naming-strategy: SNAKE_CASE
  cloud:
    openfeign:
      client:
        config:
          four-color-ai:
            connectTimeout: 3000
            readTimeout: 30000

ai-service:
  four-color:
    base-url: http://localhost:8000
    api-key: change-me

app:
  preview-storage:
    dir: ${java.io.tmpdir}/four-color-previews

resilience4j:
  timelimiter:
    instances:
      fourColorAi:
        timeoutDuration: 35s
        cancelRunningFuture: true
  circuitbreaker:
    instances:
      fourColorAi:
        slidingWindowSize: 10
        failureRateThreshold: 50
        waitDurationInOpenState: 15s
        permittedNumberOfCallsInHalfOpenState: 3
        slidingWindowType: COUNT_BASED
        recordExceptions:
          - com.example.fourcolorai.exception.FourColorAiUnavailableException
          - feign.FeignException$ServiceUnavailable
  retry:
    instances:
      fourColorAi:
        maxAttempts: 3
        waitDuration: 1s
        retryExceptions:
          - com.example.fourcolorai.exception.FourColorAiUnavailableException
          - java.net.SocketTimeoutException
        ignoreExceptions:
          - com.example.fourcolorai.exception.FourColorParseException
          - feign.FeignException$BadRequest
```

关键点：AI 服务返回 `canvas_width` 等下划线字段，必须用 `SNAKE_CASE` 策略映射到 Java record 的驼峰字段，否则反序列化全为 null。

- [ ] **步骤 3：写启动类、统一响应、DTO、异常**

`FourColorAiApplication.java`：

```java
package com.example.fourcolorai;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.openfeign.EnableFeignClients;

@SpringBootApplication
@EnableFeignClients
public class FourColorAiApplication {
    public static void main(String[] args) {
        SpringApplication.run(FourColorAiApplication.class, args);
    }
}
```

`common/ApiResponse.java`：

```java
package com.example.fourcolorai.common;

public record ApiResponse<T>(int code, String message, T data) {
    public static <T> ApiResponse<T> ok(T data) {
        return new ApiResponse<>(0, "ok", data);
    }

    public boolean ok() {
        return code == 0;
    }
}
```

`dto/FourColorAnalyzeRequest.java`：

```java
package com.example.fourcolorai.dto;

public record FourColorAnalyzeRequest(String imageBase64, Options options) {
    public record Options(int maxZones, int canvasWidth, int canvasHeight,
                          boolean enableOcr, boolean enableClip) {
        public static Options defaults() {
            return new Options(200, 1600, 1000, true, true);
        }
    }
}
```

`dto/FourColorAnalyzeResult.java`（与 AI 服务 `data` 字段一一对应）：

```java
package com.example.fourcolorai.dto;

import java.util.List;

public record FourColorAnalyzeResult(
        String requestId,
        int width,
        int height,
        int canvasWidth,
        int canvasHeight,
        String previewPngBase64,
        List<Zone> zones,
        List<TextItem> texts,
        List<ExcludedItem> excluded,
        List<String> warnings) {

    public record Point(double x, double y) {}

    public record Polygon(String id, String label, List<Point> points) {}

    public record Zone(String clientId, String name, String riskLevel, String color,
                       boolean suspected, String suggestedName, String aiHint,
                       List<Polygon> polygons) {}

    public record TextItem(List<Point> points, String text, double confidence) {}

    public record ExcludedItem(String color, String reason, List<Polygon> polygons) {}
}
```

`dto/FrontendAnalyzeResponse.java`（前端契约：preview_url + 透传字段）：

```java
package com.example.fourcolorai.dto;

import java.util.List;

public record FrontendAnalyzeResponse(
        String previewUrl,
        int canvasWidth,
        int canvasHeight,
        List<FourColorAnalyzeResult.Zone> zones,
        List<String> warnings,
        List<FourColorAnalyzeResult.ExcludedItem> excluded,
        List<FourColorAnalyzeResult.TextItem> texts) {

    public static FrontendAnalyzeResponse from(FourColorAnalyzeResult result, String previewUrl) {
        return new FrontendAnalyzeResponse(
                previewUrl,
                result.canvasWidth(),
                result.canvasHeight(),
                result.zones(),
                result.warnings(),
                result.excluded(),
                result.texts());
    }
}
```

`exception/FourColorAiException.java`：

```java
package com.example.fourcolorai.exception;

public class FourColorAiException extends RuntimeException {
    public FourColorAiException(String message) {
        super(message);
    }
}
```

`exception/FourColorParseException.java`：

```java
package com.example.fourcolorai.exception;

public class FourColorParseException extends RuntimeException {
    public FourColorParseException(String message) {
        super(message);
    }
}
```

`exception/FourColorAiUnavailableException.java`：

```java
package com.example.fourcolorai.exception;

public class FourColorAiUnavailableException extends RuntimeException {
    public FourColorAiUnavailableException(String message) {
        super(message);
    }

    public FourColorAiUnavailableException(String message, Throwable cause) {
        super(message, cause);
    }
}
```

- [ ] **步骤 4：编译验证（公司 Java 环境）**

运行（在具备 JDK 17 + Maven 3.9 的机器上）：

```bash
cd four-color-ai-java
mvn -q -DskipTests compile
```

预期：BUILD SUCCESS。本机无 JDK，此步骤不在本地执行；如本地环境后续装了 JDK 可补跑。

- [ ] **步骤 5：Commit**

```powershell
git add four-color-ai-java
git commit -m "feat(four-color-ai-java): add spring cloud skeleton with dtos and resilience config"
```

---

## 任务 5：Feign Client + ErrorDecoder + 单测

**文件：**
- 创建：`client/FourColorAiClient.java`、`client/FourColorAiFeignConfig.java`
- 测试：`src/test/java/com/example/fourcolorai/client/FourColorAiFeignConfigTest.java`

- [ ] **步骤 1：编写失败的测试（ErrorDecoder 映射）**

`four-color-ai-java/src/test/java/com/example/fourcolorai/client/FourColorAiFeignConfigTest.java`：

```java
package com.example.fourcolorai.client;

import static org.assertj.core.api.Assertions.assertThat;

import com.example.fourcolorai.exception.FourColorAiException;
import com.example.fourcolorai.exception.FourColorAiUnavailableException;
import com.example.fourcolorai.exception.FourColorParseException;
import feign.Request;
import feign.Response;
import java.util.Collections;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class FourColorAiFeignConfigTest {

    private FourColorAiFeignConfig config;

    @BeforeEach
    void setUp() {
        config = new FourColorAiFeignConfig();
    }

    private Response response(int status) {
        return Response.builder()
                .status(status)
                .reason("reason")
                .request(Request.create(Request.HttpMethod.POST,
                        "http://localhost/api/v1/four-color/analyze",
                        Collections.emptyMap(), new byte[0], null))
                .headers(Collections.emptyMap())
                .build();
    }

    @Test
    void maps422ToParseException() {
        Object decoded = config.fourColorErrorDecoder()
                .decode("FourColorAiClient#analyze(FourColorAnalyzeRequest)", response(422));
        assertThat(decoded).isInstanceOf(FourColorParseException.class);
    }

    @Test
    void maps503ToUnavailableException() {
        Object decoded = config.fourColorErrorDecoder()
                .decode("FourColorAiClient#analyze(FourColorAnalyzeRequest)", response(503));
        assertThat(decoded).isInstanceOf(FourColorAiUnavailableException.class);
    }

    @Test
    void mapsOtherStatusToGenericException() {
        Object decoded = config.fourColorErrorDecoder()
                .decode("FourColorAiClient#analyze(FourColorAnalyzeRequest)", response(404));
        assertThat(decoded).isInstanceOf(FourColorAiException.class);
    }
}
```

- [ ] **步骤 2：运行测试验证失败（公司 Java 环境）**

运行：

```bash
cd four-color-ai-java
mvn -q -Dtest=FourColorAiFeignConfigTest test
```

预期：编译失败，报 `FourColorAiFeignConfig` 不存在。

- [ ] **步骤 3：实现 Feign Client 与配置**

`client/FourColorAiClient.java`：

```java
package com.example.fourcolorai.client;

import com.example.fourcolorai.common.ApiResponse;
import com.example.fourcolorai.dto.FourColorAnalyzeRequest;
import com.example.fourcolorai.dto.FourColorAnalyzeResult;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

@FeignClient(
        name = "four-color-ai",
        url = "${ai-service.four-color.base-url}",
        configuration = FourColorAiFeignConfig.class)
public interface FourColorAiClient {

    @PostMapping(value = "/api/v1/four-color/analyze",
                 consumes = MediaType.APPLICATION_JSON_VALUE)
    ApiResponse<FourColorAnalyzeResult> analyze(@RequestBody FourColorAnalyzeRequest request);
}
```

`client/FourColorAiFeignConfig.java`：

```java
package com.example.fourcolorai.client;

import com.example.fourcolorai.exception.FourColorAiException;
import com.example.fourcolorai.exception.FourColorAiUnavailableException;
import com.example.fourcolorai.exception.FourColorParseException;
import feign.RequestInterceptor;
import feign.codec.ErrorDecoder;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class FourColorAiFeignConfig {

    @Bean
    public ErrorDecoder fourColorErrorDecoder() {
        return (methodKey, response) -> {
            if (response.status() == 422) {
                return new FourColorParseException("图片解析失败（业务错误，不重试不熔断）");
            }
            if (response.status() >= 500) {
                return new FourColorAiUnavailableException(
                        "四色图识别服务异常，status=" + response.status());
            }
            return new FourColorAiException(
                    "四色图识别服务调用失败，status=" + response.status());
        };
    }

    @Bean
    public RequestInterceptor fourColorApiKeyInterceptor(
            @Value("${ai-service.four-color.api-key}") String apiKey) {
        return template -> template.header("X-API-Key", apiKey);
    }
}
```

- [ ] **步骤 4：运行测试验证通过（公司 Java 环境）**

运行：

```bash
cd four-color-ai-java
mvn -q -Dtest=FourColorAiFeignConfigTest test
```

预期：3 个测试 PASS。

- [ ] **步骤 5：Commit**

```powershell
git add four-color-ai-java/src/main/java/com/example/fourcolorai/client four-color-ai-java/src/test
git commit -m "feat(four-color-ai-java): add feign client with error decoder and api key interceptor"
```

---

## 任务 6：Facade（@Retry + @CircuitBreaker）+ 单测

**文件：**
- 创建：`service/FourColorAiFacade.java`
- 测试：`src/test/java/com/example/fourcolorai/service/FourColorAiFacadeTest.java`

- [ ] **步骤 1：编写失败的测试（Facade 映射逻辑）**

`four-color-ai-java/src/test/java/com/example/fourcolorai/service/FourColorAiFacadeTest.java`：

```java
package com.example.fourcolorai.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.example.fourcolorai.client.FourColorAiClient;
import com.example.fourcolorai.common.ApiResponse;
import com.example.fourcolorai.dto.FourColorAnalyzeResult;
import com.example.fourcolorai.exception.FourColorAiException;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class FourColorAiFacadeTest {

    private FourColorAiClient client;
    private FourColorAiFacade facade;

    @BeforeEach
    void setUp() {
        client = mock(FourColorAiClient.class);
        facade = new FourColorAiFacade(client);
    }

    @Test
    void returnsDataWhenCodeZero() {
        FourColorAnalyzeResult expected = new FourColorAnalyzeResult(
                "rid", 600, 450, 600, 450, "png",
                List.of(), List.of(), List.of(), List.of());
        when(client.analyze(any())).thenReturn(new ApiResponse<>(0, "ok", expected));

        assertThat(facade.analyze("base64")).isEqualTo(expected);
    }

    @Test
    void throwsBusinessExceptionWhenCodeNonZero() {
        when(client.analyze(any())).thenReturn(new ApiResponse<>(1, "boom", null));

        assertThatThrownBy(() -> facade.analyze("base64"))
                .isInstanceOf(FourColorAiException.class);
    }
}
```

- [ ] **步骤 2：运行测试验证失败（公司 Java 环境）**

运行：

```bash
cd four-color-ai-java
mvn -q -Dtest=FourColorAiFacadeTest test
```

预期：编译失败，报 `FourColorAiFacade` 不存在。

- [ ] **步骤 3：实现 Facade**

`service/FourColorAiFacade.java`：

```java
package com.example.fourcolorai.service;

import com.example.fourcolorai.client.FourColorAiClient;
import com.example.fourcolorai.common.ApiResponse;
import com.example.fourcolorai.dto.FourColorAnalyzeRequest;
import com.example.fourcolorai.dto.FourColorAnalyzeResult;
import com.example.fourcolorai.exception.FourColorAiException;
import com.example.fourcolorai.exception.FourColorAiUnavailableException;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.github.resilience4j.retry.annotation.Retry;
import org.springframework.stereotype.Service;

@Service
public class FourColorAiFacade {

    private final FourColorAiClient client;

    public FourColorAiFacade(FourColorAiClient client) {
        this.client = client;
    }

    @Retry(name = "fourColorAi", fallbackMethod = "analyzeFallback")
    @CircuitBreaker(name = "fourColorAi")
    public FourColorAnalyzeResult analyze(String imageBase64) {
        ApiResponse<FourColorAnalyzeResult> resp = client.analyze(
                new FourColorAnalyzeRequest(imageBase64, FourColorAnalyzeRequest.Options.defaults()));
        if (!resp.ok()) {
            throw new FourColorAiException("AI 服务业务失败: code=" + resp.code() + ", " + resp.message());
        }
        return resp.data();
    }

    private FourColorAnalyzeResult analyzeFallback(String imageBase64, Throwable t) {
        throw new FourColorAiUnavailableException("四色图识别服务暂不可用", t);
    }
}
```

说明：重试/熔断由注解 + application.yml 在 Spring 上下文生效；本单测只验证映射逻辑。集成级熔断/恢复验证见任务 8。

- [ ] **步骤 4：运行测试验证通过（公司 Java 环境）**

运行：

```bash
cd four-color-ai-java
mvn -q -Dtest=FourColorAiFacadeTest test
```

预期：2 个测试 PASS。

- [ ] **步骤 5：Commit**

```powershell
git add four-color-ai-java/src/main/java/com/example/fourcolorai/service four-color-ai-java/src/test
git commit -m "feat(four-color-ai-java): add resilience facade with retry and circuit breaker"
```

---

## 任务 7：异步服务 + 控制器 + 预览存储

**文件：**
- 创建：`config/AsyncConfig.java`、`config/PreviewWebConfig.java`、`service/FourColorAiAsyncService.java`、`service/PreviewStorageService.java`、`service/LocalPreviewStorageService.java`、`web/FourColorController.java`
- 测试：`src/test/java/com/example/fourcolorai/service/LocalPreviewStorageServiceTest.java`

- [ ] **步骤 1：编写失败的测试（本地预览存储）**

`four-color-ai-java/src/test/java/com/example/fourcolorai/service/LocalPreviewStorageServiceTest.java`：

```java
package com.example.fourcolorai.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Base64;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class LocalPreviewStorageServiceTest {

    @TempDir
    Path tempDir;

    @Test
    void savesPngAndReturnsUrl() throws IOException {
        LocalPreviewStorageService service = new LocalPreviewStorageService(tempDir.toString());
        byte[] png = {(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A};

        String url = service.save("e1", "f1", Base64.getEncoder().encodeToString(png));

        assertThat(url).startsWith("/api/risk-management/previews/e1/f1/").endsWith(".png");
        Path saved = tempDir.resolve(url.substring("/api/risk-management/previews/".length()));
        assertThat(Files.readAllBytes(saved)).containsExactly(png);
    }

    @Test
    void sanitizesUnsafeIds() {
        LocalPreviewStorageService service = new LocalPreviewStorageService(tempDir.toString());

        String url = service.save("../evil", "f1", Base64.getEncoder().encodeToString(new byte[]{1, 2, 3}));

        assertThat(url).startsWith("/api/risk-management/previews/evil/f1/");
    }

    @Test
    void rejectsInvalidBase64() {
        LocalPreviewStorageService service = new LocalPreviewStorageService(tempDir.toString());

        assertThatThrownBy(() -> service.save("e1", "f1", "!!!not-base64!!!"))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
```

- [ ] **步骤 2：运行测试验证失败（公司 Java 环境）**

运行：

```bash
cd four-color-ai-java
mvn -q -Dtest=LocalPreviewStorageServiceTest test
```

预期：编译失败，报 `LocalPreviewStorageService` 不存在。

- [ ] **步骤 3：实现存储接口与本地实现**

`service/PreviewStorageService.java`：

```java
package com.example.fourcolorai.service;

public interface PreviewStorageService {
    String save(String enterpriseId, String floorId, String pngBase64);
}
```

`service/LocalPreviewStorageService.java`：

```java
package com.example.fourcolorai.service;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Base64;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class LocalPreviewStorageService implements PreviewStorageService {

    private final Path root;

    public LocalPreviewStorageService(
            @Value("${app.preview-storage.dir:${java.io.tmpdir}/four-color-previews}") String dir) {
        this.root = Paths.get(dir).toAbsolutePath().normalize();
    }

    @Override
    public String save(String enterpriseId, String floorId, String pngBase64) {
        String safeEnterprise = sanitize(enterpriseId);
        String safeFloor = sanitize(floorId);
        String fileName = UUID.randomUUID().toString().replace("-", "") + ".png";
        Path dir = root.resolve(safeEnterprise).resolve(safeFloor).normalize();
        if (!dir.startsWith(root)) {
            throw new IllegalArgumentException("非法存储路径");
        }
        try {
            Files.createDirectories(dir);
            byte[] bytes = Base64.getDecoder().decode(pngBase64);
            Files.write(dir.resolve(fileName), bytes);
        } catch (IllegalArgumentException e) {
            throw e;
        } catch (IOException e) {
            throw new UncheckedIOException("保存预览图失败", e);
        }
        return "/api/risk-management/previews/" + safeEnterprise + "/" + safeFloor + "/" + fileName;
    }

    private String sanitize(String value) {
        String cleaned = value.replaceAll("[^a-zA-Z0-9_-]", "");
        if (cleaned.isEmpty()) {
            throw new IllegalArgumentException("非法标识: " + value);
        }
        return cleaned;
    }
}
```

`config/PreviewWebConfig.java`（让 preview_url 真实可访问）：

```java
package com.example.fourcolorai.config;

import java.nio.file.Path;
import java.nio.file.Paths;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class PreviewWebConfig implements WebMvcConfigurer {

    private final Path root;

    public PreviewWebConfig(
            @Value("${app.preview-storage.dir:${java.io.tmpdir}/four-color-previews}") String dir) {
        this.root = Paths.get(dir).toAbsolutePath().normalize();
    }

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        registry.addResourceHandler("/api/risk-management/previews/**")
                .addResourceLocations(root.toUri().toString());
    }
}
```

- [ ] **步骤 4：运行测试验证通过（公司 Java 环境）**

运行：

```bash
cd four-color-ai-java
mvn -q -Dtest=LocalPreviewStorageServiceTest test
```

预期：3 个测试 PASS。

- [ ] **步骤 5：实现异步服务、线程池、控制器**

`config/AsyncConfig.java`：

```java
package com.example.fourcolorai.config;

import java.util.concurrent.Executor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

@Configuration
@EnableAsync
public class AsyncConfig {

    @Bean("aiCallExecutor")
    public Executor aiCallExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(4);
        executor.setMaxPoolSize(8);
        executor.setQueueCapacity(50);
        executor.setThreadNamePrefix("ai-call-");
        executor.initialize();
        return executor;
    }
}
```

`service/FourColorAiAsyncService.java`：

```java
package com.example.fourcolorai.service;

import com.example.fourcolorai.dto.FourColorAnalyzeResult;
import java.util.concurrent.CompletableFuture;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

@Service
public class FourColorAiAsyncService {

    private final FourColorAiFacade facade;

    public FourColorAiAsyncService(FourColorAiFacade facade) {
        this.facade = facade;
    }

    @Async("aiCallExecutor")
    public CompletableFuture<FourColorAnalyzeResult> analyzeAsync(String imageBase64) {
        return CompletableFuture.completedFuture(facade.analyze(imageBase64));
    }
}
```

`web/FourColorController.java`：

```java
package com.example.fourcolorai.web;

import com.example.fourcolorai.common.ApiResponse;
import com.example.fourcolorai.dto.FrontendAnalyzeResponse;
import com.example.fourcolorai.service.FourColorAiAsyncService;
import com.example.fourcolorai.service.PreviewStorageService;
import java.io.IOException;
import java.util.Base64;
import java.util.concurrent.CompletableFuture;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/risk-management/enterprises/{enterpriseId}/floors/{floorId}/four-color")
public class FourColorController {

    private final FourColorAiAsyncService aiService;
    private final PreviewStorageService previewStorageService;

    public FourColorController(FourColorAiAsyncService aiService,
                               PreviewStorageService previewStorageService) {
        this.aiService = aiService;
        this.previewStorageService = previewStorageService;
    }

    @PostMapping("/analyze")
    public CompletableFuture<ApiResponse<FrontendAnalyzeResponse>> analyze(
            @PathVariable String enterpriseId,
            @PathVariable String floorId,
            @RequestParam("file") MultipartFile file) throws IOException {

        String imageBase64 = Base64.getEncoder().encodeToString(file.getBytes());

        return aiService.analyzeAsync(imageBase64)
                .thenApply(result -> ApiResponse.ok(FrontendAnalyzeResponse.from(
                        result,
                        previewStorageService.save(enterpriseId, floorId, result.previewPngBase64()))));
    }
}
```

- [ ] **步骤 6：全量测试（公司 Java 环境）**

运行：

```bash
cd four-color-ai-java
mvn test
```

预期：8 个测试全 PASS（FeignConfig 3 + Facade 2 + PreviewStorage 3）。

- [ ] **步骤 7：Commit**

```powershell
git add four-color-ai-java/src/main/java/com/example/fourcolorai four-color-ai-java/src/test
git commit -m "feat(four-color-ai-java): add async flow, controller and preview storage"
```

---

## 任务 8：端到端验证与收尾

**文件：**
- 无新文件；执行验证脚本与回归

- [ ] **步骤 1：Python 服务真实 HTTP 端到端验证（本地）**

先启动服务（后台）：

```powershell
$env:FOUR_COLOR_API_KEY='dev-key'
Start-Process -WindowStyle Hidden -FilePath "backend\.venv\Scripts\python.exe" -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8011" -WorkingDirectory "four-color-ai"
Start-Sleep -Seconds 5
```

再跑真实 HTTP 脚本（内联 Python，复用任务 2 的合成图）：

```python
import base64, io, json, urllib.request
from PIL import Image, ImageDraw

img = Image.new("RGB", (600, 450), "white")
d = ImageDraw.Draw(img)
for x0, y0, x1, y1, c in [
    (40, 40, 280, 180, (255, 0, 0)),
    (320, 40, 560, 180, (255, 127, 0)),
    (40, 230, 280, 410, (255, 255, 0)),
    (320, 230, 560, 410, (0, 0, 255)),
]:
    d.rectangle([x0, y0, x1, y1], fill=c)
buf = io.BytesIO()
img.save(buf, format="PNG")

payload = json.dumps({
    "image_base64": base64.b64encode(buf.getvalue()).decode("ascii"),
    "options": {"canvas_width": 800, "canvas_height": 600},
}).encode("utf-8")
req = urllib.request.Request(
    "http://127.0.0.1:8011/api/v1/four-color/analyze",
    data=payload,
    headers={"Content-Type": "application/json", "X-API-Key": "dev-key"},
)
resp = json.load(urllib.request.urlopen(req, timeout=60))
assert resp["code"] == 0, resp
data = resp["data"]
assert len(data["zones"]) == 4, data["zones"]
assert data["canvas_width"] == 800 and data["canvas_height"] == 600
bad = [
    p for z in data["zones"]
    for poly in z["polygons"]
    for p in poly["points"]
    if not (0 <= p["x"] <= 100 and 0 <= p["y"] <= 100)
]
assert not bad, bad
print("E2E OK zones=", len(data["zones"]), "texts=", len(data["texts"]))
```

预期：输出 `E2E OK zones= 4 texts= ...`。验证后停止测试进程。

- [ ] **步骤 2：原系统回归（确保抽取未破坏 backend）**

运行：

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests -q
```

预期：backend 全量测试 PASS（本计划未改 backend 任何文件，此步为安全网）。

- [ ] **步骤 3：Java 侧集成验证清单（公司 Java 环境执行，逐项打勾）**

```bash
# 1) 单测全绿
cd four-color-ai-java && mvn test
# 2) 配置 AI 服务地址与密钥后启动
mvn spring-boot:run -Dspring-boot.run.arguments="--ai-service.four-color.base-url=http://<AI服务>:8000 --ai-service.four-color.api-key=<key>"
# 3) 模拟前端 multipart 调用（前端契约）
curl -X POST "http://localhost:8080/api/risk-management/enterprises/e1/floors/f1/four-color/analyze" \
  -H "Authorization: Bearer <token>" -F "file=@test.png"
# 预期：200，响应含 preview_url/canvas_width/canvas_height/zones
# 4) 停服演练：停掉 AI 服务 → 再次调用
# 预期：30s 内返回降级错误（fallback FourColorAiUnavailableException → 全局异常处理转 503）
# 5) 熔断演练：连续失败 5+ 次后 → 立即快速失败（不再等待 30s）
# 6) 恢复演练：重启 AI 服务 → 15s 半开期后自动恢复 200
```

- [ ] **步骤 4：更新 TASKS.md 快照**

在 `TASKS.md` 顶部追加/更新快照：完成的任务、验证结果、遗留事项（Java 侧待公司环境验证）、下一步。

- [ ] **步骤 5：收尾 Commit（含计划自检修正，如有）**

```powershell
git add -A four-color-ai four-color-ai-java
git commit -m "chore(four-color-ai): finalize extraction with e2e verification"
```

若执行方式为 worktree（推荐），收尾按 `finishing-a-development-branch` 技能决定合并/PR/清理。

---

## 验收标准（对照规格第 7 节）

- [ ] 独立服务通过现有识别器单测 + 服务级测试（pytest 全绿，本地可验证）。
- [ ] Java 端 analyze 全链路 200，前端接口契约不变（preview_url/canvas_width/canvas_height/zones/warnings/excluded/texts）。
- [ ] AI 服务停服时 Java 端 30s 内超时降级；恢复后自动恢复调用（公司环境演练）。
- [ ] 抽取后原系统回归：backend 全量测试通过，四色导入 analyze/commit/cancel 行为不变。

## 非目标（延续规格第 9 节）

- 不做 Java 重写识别算法。
- 不做 202 + 任务轮询模式。
- 不改识别算法、阈值与干扰过滤规则（`four_color_recognizer.py` 原样复制）。
