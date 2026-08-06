# 四色分布图自动识别导入 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 用户上传现有四色分布图（电子图或拍照件）后，后端 OpenCV 自动识别红/橙/黄/蓝区域，前端预览校对后一键落图：上传图成为该楼层底图，分区按原图位置写入数据库。

**架构：** 后端新增纯函数识别管线 `four_color_recognizer.py`（颜色分割→形态学清理→轮廓提取→多边形归一化），新增 analyze/commit/cancel 三个端点；识别结果先经前端预览校对，commit 时原子替换底图与分区。前端新增导入弹窗组件与三个服务函数。

**技术栈：** Python 3.12 + FastAPI + OpenCV（`opencv-python-headless`）+ Pillow + SQLAlchemy（异步）；React 19 + antd 6 + Konva（工作台，不修改绘图引擎）；Playwright E2E。

**规格：** `docs/superpowers/specs/2026-08-06-four-color-auto-import-design.md`

**执行决策（实现时严格遵守）：**
- 识别等级色存储采用系统统一色板 `LEVEL_COLORS`（重大 #ff4d4f / 较大 #fa8c16 / 一般 #fadb14 / 低 #52c41a）。四色图标准中的"蓝=低"只参与识别映射，落库后按系统色板渲染，保证工作台图例、层级树、总览全系统一致。
- 后端测试沿用仓库现有"无数据库"模式：路由函数用 `AsyncMock` db 直接调用（见 `backend/tests/test_risk_mapping_service.py`），存储函数用 `tmp_path` + `monkeypatch.setattr(fss, "UPLOAD_DIR", tmp_path)`（见 `backend/tests/test_floor_plan_upload.py`）。
- Windows 后端解释器路径：`backend/.venv/Scripts/python.exe`；前端命令在 `frontend/` 下执行。

---

## 文件结构

后端（新增/修改）：
- `backend/app/services/four_color_recognizer.py`（新增）：识别管线纯函数，无 DB 依赖。
- `backend/app/services/floor_plan_storage_service.py`（修改）：新增四色图临时文件保存/转正/清理与 token 校验。
- `backend/app/schemas/risk_management.py`（修改）：新增 FourColor* schema。
- `backend/app/routers/risk_management.py`（修改）：新增 analyze/commit/cancel 三个端点。
- `backend/requirements.txt`（修改）：新增 opencv-python-headless、numpy。
- `backend/tests/test_four_color_recognizer.py`（新增）：识别器单测（合成图）。
- `backend/tests/test_four_color_import_api.py`（新增）：存储辅助 + schema + 三端点测试（mock db）。

前端（新增/修改）：
- `frontend/src/types/riskMappingWorkbench.ts`（修改）：FourColor* 类型。
- `frontend/src/services/riskMappingWorkbenchService.ts`（修改）：三个服务函数。
- `frontend/src/services/riskMappingWorkbenchService.test.ts`（新增）：服务函数 vitest。
- `frontend/src/components/enterprise/riskMapping/FourColorImportModal.tsx`（新增）：导入弹窗。
- `frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx`（修改）：入口按钮与回调。
- `frontend/e2e/four-color-import.spec.ts`（新增）：E2E。
- `frontend/e2e/fixtures/four-color-sample.png`（新增）：E2E 测试图（脚本生成后提交）。

## 命令约定

- 后端单测（仓库根目录或 backend 目录均可）：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_four_color_recognizer.py -q`
- 后端全量：`cd backend; .venv\Scripts\python.exe -m pytest -q`
- 前端类型：`cd frontend; npx tsc -b`
- 前端单测：`cd frontend; npx vitest run`
- E2E：`cd frontend; npx playwright test e2e/four-color-import.spec.ts`
- 提交风格：Conventional Commits（如 `feat(risk-mapping): ...`），每任务独立 commit。

---

### 任务 0：依赖与基线

**文件：**
- 修改：`backend/requirements.txt`

- [ ] **步骤 1：在 requirements.txt 追加依赖**

在 `backend/requirements.txt` 末尾追加：

```text
opencv-python-headless>=4.10,<5
numpy>=1.26
```

- [ ] **步骤 2：安装到本地 venv 并验证导入**

运行：
```powershell
backend/.venv/Scripts/python.exe -m pip install "opencv-python-headless>=4.10,<5" "numpy>=1.26"
backend/.venv/Scripts/python.exe -c "import cv2, numpy; print(cv2.__version__, numpy.__version__)"
```
预期：输出两个版本号，无 ImportError。

- [ ] **步骤 3：Commit**

```powershell
git add backend/requirements.txt
git commit -m "build(risk-mapping): add opencv and numpy for four-color recognition"
```

### 任务 1：识别器——颜色分类

**文件：**
- 创建：`backend/app/services/four_color_recognizer.py`
- 测试：`backend/tests/test_four_color_recognizer.py`

- [ ] **步骤 1：编写失败测试**

创建 `backend/tests/test_four_color_recognizer.py`：

```python
"""四色分布图识别器单测：合成图覆盖颜色分类、清理、轮廓、透视、管线。"""
import io

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.services.four_color_recognizer import (
    classify_pixels,
)

PALETTE_BGR = {
    "红": (0, 0, 255),
    "橙": (0, 127, 255),
    "黄": (0, 255, 255),
    "蓝": (255, 0, 0),
}


def _bgr_img(width=200, height=200):
    return np.full((height, width, 3), 255, dtype=np.uint8)


def _png_bytes(img_rgb: Image.Image) -> bytes:
    buf = io.BytesIO()
    img_rgb.save(buf, format="PNG")
    return buf.getvalue()


def _four_rect_rgb(width=600, height=450):
    """四个标准四色矩形（RGB 值），供管线测试。"""
    img = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(img)
    rects = [
        (40, 40, 280, 180, (255, 0, 0)),
        (320, 40, 560, 180, (255, 127, 0)),
        (40, 230, 280, 410, (255, 255, 0)),
        (320, 230, 560, 410, (0, 0, 255)),
    ]
    for x0, y0, x1, y1, color in rects:
        d.rectangle([x0, y0, x1, y1], fill=color)
    return img


def test_classify_pixels_assigns_each_palette_color():
    img = _bgr_img()
    for i, name in enumerate(PALETTE_BGR):
        x0 = 25 + i * 50
        img[50:150, x0:x0 + 40] = PALETTE_BGR[name]
    masks = classify_pixels(img)
    for i, name in enumerate(PALETTE_BGR):
        cx = 25 + i * 50 + 20
        assert masks[name][100, cx] == 255, f"{name} 区域应命中"
        for other in PALETTE_BGR:
            if other != name:
                assert masks[other][100, cx] == 0, f"{other} 掩码不应包含 {name} 区域"
    assert masks["红"][10, 10] == 0, "白色背景不应命中任何颜色"


def test_classify_pixels_tolerates_print_shift():
    img = _bgr_img()
    img[50:150, 50:150] = (20, 20, 200)  # 略暗的红（BGR）
    masks = classify_pixels(img)
    assert masks["红"][100, 100] == 255


def test_classify_pixels_returns_uint8_binary():
    img = _bgr_img()
    masks = classify_pixels(img)
    assert set(masks["红"].flat) <= {0, 255}
```

- [ ] **步骤 2：运行测试确认失败**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_four_color_recognizer.py -q`
预期：FAIL，报错 `ModuleNotFoundError: No module named 'app.services.four_color_recognizer'`

- [ ] **步骤 3：实现最小代码**

创建 `backend/app/services/four_color_recognizer.py`：

```python
"""四色分布图识别管线：颜色分割 → 形态学清理 → 轮廓提取 → 多边形归一化。"""
from __future__ import annotations

import cv2
import numpy as np

COLOR_PALETTE: dict[str, tuple[int, int, int]] = {
    "红": (0, 0, 255),    # BGR
    "橙": (0, 127, 255),  # BGR
    "黄": (0, 255, 255),  # BGR
    "蓝": (255, 0, 0),    # BGR
}
LEVEL_BY_COLOR = {"红": "重大", "橙": "较大", "黄": "一般", "蓝": "低"}
MAX_HSV_DIST = 0.35


def classify_pixels(img: np.ndarray) -> dict[str, np.ndarray]:
    """按 HSV 距离把每个像素归类到最近标准色；距离超过阈值则归为背景。"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    names = list(COLOR_PALETTE)
    refs = [
        cv2.cvtColor(np.uint8([[COLOR_PALETTE[n]]]), cv2.COLOR_BGR2HSV)[0, 0].astype(np.float32)
        for n in names
    ]
    dists = []
    for rh, rs, rv in refs:
        dh = np.minimum(np.abs(h - rh), 180.0 - np.abs(h - rh))
        d = (dh / 180.0) ** 2 * 2.0 + ((s - rs) / 255.0) ** 2 + ((v - rv) / 255.0) ** 2
        dists.append(d)
    dists = np.stack(dists, axis=-1)
    idx = np.argmin(dists, axis=-1)
    mind = np.min(dists, axis=-1)
    return {
        name: np.where((idx == i) & (mind <= MAX_HSV_DIST), 255, 0).astype(np.uint8)
        for i, name in enumerate(names)
    }
```

- [ ] **步骤 4：运行测试确认通过**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_four_color_recognizer.py -q`
预期：3 passed

- [ ] **步骤 5：Commit**

```powershell
git add backend/app/services/four_color_recognizer.py backend/tests/test_four_color_recognizer.py
git commit -m "feat(risk-mapping): four-color pixel classification by HSV distance"
```

### 任务 2：识别器——掩码清理与轮廓提取

**文件：**
- 修改：`backend/app/services/four_color_recognizer.py`
- 测试：`backend/tests/test_four_color_recognizer.py`（追加）

- [ ] **步骤 1：追加失败测试**

在 `backend/tests/test_four_color_recognizer.py` 末尾追加（并更新 import 列表，加入 `clean_mask, mask_to_polygons, normalize_points`）：

```python
def test_clean_mask_removes_small_noise():
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[10:90, 10:90] = 255
    mask[2:4, 2:4] = 255  # 2x2 噪点
    cleaned = clean_mask(mask, kernel_size=3)
    assert cleaned[50, 50] == 255
    assert cleaned[3, 3] == 0


def test_mask_to_polygons_simplifies_rectangle():
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[10:90, 10:90] = 255
    polys = mask_to_polygons(mask, 100, 100, min_area=100.0, epsilon=2.0)
    assert len(polys) == 1
    assert len(polys[0]) == 4
    area = cv2.contourArea(polys[0].astype(np.float32))
    assert 5000 < area < 7000


def test_mask_to_polygons_filters_small_areas():
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[10:20, 10:20] = 255   # 100 px
    mask[40:80, 40:80] = 255   # 1600 px
    polys = mask_to_polygons(mask, 100, 100, min_area=500.0, epsilon=1.0)
    assert len(polys) == 1
    assert cv2.contourArea(polys[0].astype(np.float32)) > 1000


def test_normalize_points_clamps_and_rounds():
    points = [(-5.0, 55.0), (100.5, 33.333), (25.0, 0.0)]
    out = normalize_points(points, 100, 100)
    assert out == [{"x": 0.0, "y": 55.0}, {"x": 100.0, "y": 33.33}, {"x": 25.0, "y": 0.0}]
```

- [ ] **步骤 2：运行测试确认失败**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_four_color_recognizer.py -q`
预期：FAIL，报错 `ImportError: cannot import name 'clean_mask'`

- [ ] **步骤 3：实现代码**

在 `four_color_recognizer.py` 追加常量与函数：

```python
MIN_AREA_RATIO = 5e-5
EPSILON_RATIO = 0.0025
MAX_POLYGON_POINTS = 128


def clean_mask(mask: np.ndarray, kernel_size: int = 3) -> np.ndarray:
    """开运算去噪点 + 闭运算填补文字造成的小孔。"""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)


def mask_to_polygons(mask: np.ndarray, width: int, height: int, min_area: float, epsilon: float) -> list[np.ndarray]:
    """外轮廓提取 + Douglas-Peucker 简化 + 最小面积过滤，返回像素坐标多边形列表。"""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polys: list[np.ndarray] = []
    for cnt in contours:
        if cv2.contourArea(cnt) < min_area:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        if len(approx) < 3:
            continue
        if len(approx) > MAX_POLYGON_POINTS:
            step = max(1, len(approx) // MAX_POLYGON_POINTS)
            approx = approx[::step]
            if len(approx) < 3:
                approx = approx[:3]
        polys.append(approx.reshape(-1, 2))
    return polys


def normalize_points(points: np.ndarray | list, width: int, height: int) -> list[dict]:
    """像素坐标归一化为 0-100，越界 clamp，保留 2 位小数。"""
    out = []
    for x, y in points:
        nx = round(max(0.0, min(100.0, float(x) / width * 100.0)), 2)
        ny = round(max(0.0, min(100.0, float(y) / height * 100.0)), 2)
        out.append({"x": nx, "y": ny})
    return out
```

- [ ] **步骤 4：运行测试确认通过**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_four_color_recognizer.py -q`
预期：7 passed

- [ ] **步骤 5：Commit**

```powershell
git add backend/app/services/four_color_recognizer.py backend/tests/test_four_color_recognizer.py
git commit -m "feat(risk-mapping): contour extraction and polygon normalization"
```

### 任务 3：识别器——透视校正与管线入口

**文件：**
- 修改：`backend/app/services/four_color_recognizer.py`
- 测试：`backend/tests/test_four_color_recognizer.py`（追加）

- [ ] **步骤 1：追加失败测试**

在 `backend/tests/test_four_color_recognizer.py` 末尾追加（并更新 import，加入 `MAX_ZONES, detect_perspective_quad, recognize_from_bytes, warp_perspective`）：

```python
def test_detect_perspective_quad_finds_inset_border():
    img = _bgr_img(400, 500)
    img[50:350, 50:450] = 0  # 深色边框围出的"纸面"
    quad, warning = detect_perspective_quad(img)
    assert quad is not None and len(quad) == 4
    assert warning is None


def test_detect_perspective_quad_returns_none_for_full_image():
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    quad, warning = detect_perspective_quad(img)
    assert quad is None
    assert warning is None


def test_warp_perspective_makes_quad_full_frame():
    img = _bgr_img(400, 500)
    img[50:350, 50:450] = 0
    quad, _ = detect_perspective_quad(img)
    assert quad is not None
    warped = warp_perspective(img, quad)
    h, w = warped.shape[:2]
    quad2, _ = detect_perspective_quad(warped)
    assert quad2 is not None
    assert cv2.contourArea(quad2) / (w * h) > 0.9


def test_recognize_from_bytes_returns_four_zones():
    png = _png_bytes(_four_rect_rgb())
    result = recognize_from_bytes(png)
    assert result.width == 600
    assert result.height == 450
    assert len(result.zones) == 4
    levels = {z["risk_level"] for z in result.zones}
    assert levels == {"重大", "较大", "一般", "低"}
    for zone in result.zones:
        points = zone["polygons"][0]["points"]
        assert len(points) >= 3
        assert all(0 <= p["x"] <= 100 and 0 <= p["y"] <= 100 for p in points)


def test_recognize_from_bytes_zone_centers_match_rects():
    png = _png_bytes(_four_rect_rgb())
    result = recognize_from_bytes(png)
    expected = {
        "重大": (160 / 600 * 100, 110 / 450 * 100),
        "较大": (440 / 600 * 100, 110 / 450 * 100),
        "一般": (160 / 600 * 100, 320 / 450 * 100),
        "低": (440 / 600 * 100, 320 / 450 * 100),
    }
    for zone in result.zones:
        points = zone["polygons"][0]["points"]
        cx = sum(p["x"] for p in points) / len(points)
        cy = sum(p["y"] for p in points) / len(points)
        ex, ey = expected[zone["risk_level"]]
        assert abs(cx - ex) < 5 and abs(cy - ey) < 5


def test_recognize_from_bytes_tolerates_text_overlay():
    img = _four_rect_rgb()
    d = ImageDraw.Draw(img)
    for cx, cy in [(160, 110), (440, 110), (160, 320), (440, 320)]:
        d.rectangle([cx - 30, cy - 12, cx + 30, cy + 12], fill=(0, 0, 0))
    result = recognize_from_bytes(_png_bytes(img))
    assert len(result.zones) == 4


def test_recognize_from_bytes_ignores_small_noise():
    img = Image.new("RGB", (600, 450), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, 280, 180], fill=(255, 0, 0))
    for i in range(10):
        d.rectangle([400 + i * 5, 300, 403 + i * 5, 303], fill=(255, 0, 0))
    result = recognize_from_bytes(_png_bytes(img))
    assert len(result.zones) == 1
    assert result.zones[0]["risk_level"] == "重大"


def test_recognize_from_bytes_empty_when_no_color():
    png = _png_bytes(Image.new("RGB", (200, 150), "white"))
    result = recognize_from_bytes(png)
    assert result.zones == []
```

- [ ] **步骤 2：运行测试确认失败**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_four_color_recognizer.py -q`
预期：FAIL，报错 `ImportError: cannot import name 'detect_perspective_quad'`

- [ ] **步骤 3：实现代码**

在 `four_color_recognizer.py` 追加：

```python
import io
import math
from dataclasses import dataclass
from uuid import uuid4

from PIL import Image, ImageOps

MAX_ZONES = 200
COLOR_HEX_BY_LEVEL = {"重大": "#ff4d4f", "较大": "#fa8c16", "一般": "#fadb14", "低": "#52c41a"}


def _kernel_size(width: int, height: int) -> int:
    k = max(3, int(min(width, height) / 400))
    return k if k % 2 == 1 else k + 1


def _order_points(pts: np.ndarray) -> np.ndarray:
    ordered = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    ordered[0] = pts[np.argmin(s)]     # 左上
    ordered[2] = pts[np.argmax(s)]     # 右下
    diff = np.diff(pts, axis=1).ravel()
    ordered[1] = pts[np.argmin(diff)]  # 右上
    ordered[3] = pts[np.argmax(diff)]  # 左下
    return ordered


def detect_perspective_quad(img: np.ndarray) -> tuple[np.ndarray | None, str | None]:
    """检测最大近似四边形（纸张/图框边缘）。返回 (quad, warning)。"""
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, None
    cnt = max(contours, key=cv2.contourArea)
    area_ratio = cv2.contourArea(cnt) / (w * h)
    if area_ratio < 0.2 or area_ratio > 0.95:
        return None, None
    peri = cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
    if len(approx) != 4:
        return None, "检测到疑似纸张边缘但无法校正透视，请尽量上传正拍图"
    return approx.reshape(4, 2).astype(np.float32), None


def warp_perspective(img: np.ndarray, quad: np.ndarray) -> np.ndarray:
    """按四边形宽高比透视校正为正矩形。"""
    src = _order_points(quad)
    tl, tr, br, bl = src
    width_top = float(np.linalg.norm(tr - tl))
    width_bottom = float(np.linalg.norm(br - bl))
    height_left = float(np.linalg.norm(bl - tl))
    height_right = float(np.linalg.norm(br - tr))
    max_w = max(int(width_top), int(width_bottom), 1)
    max_h = max(int(height_left), int(height_right), 1)
    dst = np.array([[0, 0], [max_w - 1, 0], [max_w - 1, max_h - 1], [0, max_h - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, matrix, (max_w, max_h))


@dataclass
class RecognizeResult:
    zones: list[dict]
    warnings: list[str]
    width: int
    height: int


def recognize_from_bytes(data: bytes) -> RecognizeResult:
    """识别管线入口：解码 → 透视校正 → 分类 → 清理 → 轮廓 → 归一化。"""
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    rgb = np.array(img.convert("RGB"))
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    height, width = bgr.shape[:2]
    warnings: list[str] = []
    quad, quad_warning = detect_perspective_quad(bgr)
    if quad is not None:
        bgr = warp_perspective(bgr, quad)
        height, width = bgr.shape[:2]
    if quad_warning:
        warnings.append(quad_warning)
    masks = classify_pixels(bgr)
    diag = math.hypot(width, height)
    min_area = MIN_AREA_RATIO * width * height
    epsilon = EPSILON_RATIO * diag
    kernel_size = _kernel_size(width, height)
    zones: list[dict] = []
    seq = 0
    capped = False
    for name in ("红", "橙", "黄", "蓝"):
        mask = clean_mask(masks[name], kernel_size)
        polys = mask_to_polygons(mask, width, height, min_area, epsilon)
        for poly in polys:
            if len(zones) >= MAX_ZONES:
                if not capped:
                    warnings.append("识别区域过多，已保留前 200 个")
                    capped = True
                break
            seq += 1
            zones.append({
                "client_id": f"draft-{uuid4().hex}",
                "name": f"分区{seq}",
                "risk_level": LEVEL_BY_COLOR[name],
                "color": COLOR_HEX_BY_LEVEL[LEVEL_BY_COLOR[name]],
                "polygons": [{
                    "id": f"poly-{uuid4().hex}",
                    "label": None,
                    "points": normalize_points(poly, width, height),
                }],
            })
        if len(zones) >= MAX_ZONES:
            break
    return RecognizeResult(zones=zones, warnings=warnings, width=width, height=height)
```

注意：`import io/math/dataclass/uuid4/PIL` 放在文件顶部 import 区（步骤 3 的代码块按追加方式写，最终文件顶部 import 合并为：`import io, math`、`from dataclasses import dataclass`、`from uuid import uuid4`、`import cv2`、`import numpy as np`、`from PIL import Image, ImageOps`）。

- [ ] **步骤 4：运行测试确认通过**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_four_color_recognizer.py -q`
预期：14 passed

- [ ] **步骤 5：Commit**

```powershell
git add backend/app/services/four_color_recognizer.py backend/tests/test_four_color_recognizer.py
git commit -m "feat(risk-mapping): perspective correction and recognize pipeline"
```

### 任务 4：存储——四色图临时文件辅助

**文件：**
- 修改：`backend/app/services/floor_plan_storage_service.py`
- 测试：`backend/tests/test_four_color_import_api.py`（新增，含存储/schema/端点三部分）

- [ ] **步骤 1：编写失败测试**

创建 `backend/tests/test_four_color_import_api.py`：

```python
"""四色图导入 API：存储辅助、schema、analyze/commit/cancel 端点（mock db，不依赖数据库）。"""
import io
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw
from pydantic import ValidationError

import app.services.floor_plan_storage_service as fss
from app.schemas.risk_management import (
    FourColorCommitRequest,
    FourColorCommitZone,
    RiskPolygonPoint,
)
from app.services.floor_plan_storage_service import (
    MAX_BYTES,
    promote_four_color_file,
    remove_four_color_temp_dir,
    save_four_color_temp,
)


def _png_bytes(img: Image.Image | None = None, width=120, height=80, color=(255, 0, 0)) -> bytes:
    if img is None:
        img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _four_color_png() -> bytes:
    img = Image.new("RGB", (600, 450), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, 280, 180], fill=(255, 0, 0))
    d.rectangle([320, 40, 560, 180], fill=(255, 127, 0))
    d.rectangle([40, 230, 280, 410], fill=(255, 255, 0))
    d.rectangle([320, 230, 560, 410], fill=(0, 0, 255))
    return _png_bytes(img)


# ── 存储辅助 ──


def test_save_four_color_temp_writes_and_returns_url(tmp_path, monkeypatch):
    monkeypatch.setattr(fss, "UPLOAD_DIR", tmp_path)
    url, token = save_four_color_temp("e-1", "f-1", _png_bytes(), "image/png")
    assert url.startswith("/uploads/enterprises/e-1/floors/f-1/four_color_tmp/")
    assert (tmp_path / url.removeprefix("/uploads/")).exists()
    assert token


def test_save_four_color_temp_cleans_old_session(tmp_path, monkeypatch):
    monkeypatch.setattr(fss, "UPLOAD_DIR", tmp_path)
    url1, _ = save_four_color_temp("e-1", "f-1", _png_bytes(), "image/png")
    url2, _ = save_four_color_temp("e-1", "f-1", _png_bytes(), "image/png")
    assert not (tmp_path / url1.removeprefix("/uploads/")).exists()
    assert (tmp_path / url2.removeprefix("/uploads/")).exists()


def test_save_four_color_temp_rejects_bad_type(tmp_path, monkeypatch):
    monkeypatch.setattr(fss, "UPLOAD_DIR", tmp_path)
    with pytest.raises(HTTPException) as exc:
        save_four_color_temp("e-1", "f-1", b"x", "image/gif")
    assert exc.value.status_code == 422


def test_save_four_color_temp_rejects_oversized(tmp_path, monkeypatch):
    monkeypatch.setattr(fss, "UPLOAD_DIR", tmp_path)
    with pytest.raises(HTTPException) as exc:
        save_four_color_temp("e-1", "f-1", b"x" * (MAX_BYTES + 1), "image/png")
    assert exc.value.status_code == 413


def test_promote_four_color_file_renames_to_final(tmp_path, monkeypatch):
    monkeypatch.setattr(fss, "UPLOAD_DIR", tmp_path)
    url, token = save_four_color_temp("e-1", "f-1", _png_bytes(width=120, height=80), "image/png")
    final_url, width, height = promote_four_color_file("e-1", "f-1", token)
    assert "four_color_tmp" not in final_url
    assert (width, height) == (120, 80)
    assert (tmp_path / final_url.removeprefix("/uploads/")).exists()
    assert not (tmp_path / url.removeprefix("/uploads/")).exists()


def test_promote_four_color_file_rejects_bad_token(tmp_path, monkeypatch):
    monkeypatch.setattr(fss, "UPLOAD_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        promote_four_color_file("e-1", "f-1", "../evil")


def test_remove_four_color_temp_dir_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(fss, "UPLOAD_DIR", tmp_path)
    _, token = save_four_color_temp("e-1", "f-1", _png_bytes(), "image/png")
    remove_four_color_temp_dir("e-1", "f-1", token)
    remove_four_color_temp_dir("e-1", "f-1", token)
```

- [ ] **步骤 2：运行测试确认失败**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_four_color_import_api.py -q`
预期：FAIL，报错 `ImportError: cannot import name 'save_four_color_temp'`

- [ ] **步骤 3：实现代码**

在 `backend/app/services/floor_plan_storage_service.py` 顶部 import 区追加 `import re`，并在文件末尾追加：

```python
FOUR_COLOR_TMP = "four_color_tmp"
TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")


def _floor_dir(enterprise_id: str, floor_id: str) -> Path:
    return (UPLOAD_DIR / "enterprises" / enterprise_id / "floors" / floor_id).resolve()


def _four_color_tmp_root(enterprise_id: str, floor_id: str) -> Path:
    return _floor_dir(enterprise_id, floor_id) / FOUR_COLOR_TMP


def four_color_temp_dir(enterprise_id: str, floor_id: str, token: str) -> Path | None:
    """校验 token 并返回临时目录；格式非法或目录不存在返回 None。"""
    if not TOKEN_RE.match(token):
        return None
    root = _floor_dir(enterprise_id, floor_id)
    target = (_four_color_tmp_root(enterprise_id, floor_id) / token).resolve()
    if target == root or not target.is_relative_to(root):
        return None
    if not target.is_dir():
        return None
    return target


def save_four_color_temp(enterprise_id: str, floor_id: str, data: bytes, content_type: str) -> tuple[str, str]:
    """保存识别源图临时文件，返回 (preview_url, token)。先清理同楼层旧临时目录。"""
    if content_type not in ALLOWED:
        raise HTTPException(422, "仅支持 PNG/JPEG/WebP 图片")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "文件不能超过 20MB")
    ext = EXT_BY_CONTENT_TYPE.get(content_type, ".png")
    root = _four_color_tmp_root(enterprise_id, floor_id)
    root.mkdir(parents=True, exist_ok=True)
    for child in root.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
    token = uuid.uuid4().hex
    target_dir = root / token
    target_dir.mkdir(parents=True)
    (target_dir / f"source{ext}").write_bytes(data)
    url = f"/uploads/enterprises/{enterprise_id}/floors/{floor_id}/{FOUR_COLOR_TMP}/{token}/source{ext}"
    return url, token


def promote_four_color_file(enterprise_id: str, floor_id: str, token: str) -> tuple[str, int, int]:
    """把临时源图转正为楼层正式底图，返回 (url, width, height)。"""
    tmp_dir = four_color_temp_dir(enterprise_id, floor_id, token)
    if tmp_dir is None:
        raise FileNotFoundError("导入会话不存在")
    source = next(tmp_dir.glob("source.*"), None)
    if source is None:
        raise FileNotFoundError("导入会话不存在")
    with Image.open(source) as img:
        width, height = img.size
    floor_dir = _floor_dir(enterprise_id, floor_id)
    floor_dir.mkdir(parents=True, exist_ok=True)
    name = f"{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex}{source.suffix}"
    target = floor_dir / name
    shutil.move(str(source), str(target))
    return f"/uploads/enterprises/{enterprise_id}/floors/{floor_id}/{name}", width, height


def remove_four_color_temp_dir(enterprise_id: str, floor_id: str, token: str) -> None:
    """幂等删除临时目录；路径安全校验失败则仅返回。"""
    tmp_dir = four_color_temp_dir(enterprise_id, floor_id, token)
    if tmp_dir is None:
        return
    shutil.rmtree(tmp_dir, ignore_errors=True)
```

- [ ] **步骤 4：运行测试确认通过**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_four_color_import_api.py -q`
预期：7 passed

- [ ] **步骤 5：Commit**

```powershell
git add backend/app/services/floor_plan_storage_service.py backend/tests/test_four_color_import_api.py
git commit -m "feat(risk-mapping): four-color temp file storage helpers"
```

### 任务 5：Schema——FourColor* 模型与校验

**文件：**
- 修改：`backend/app/schemas/risk_management.py`
- 测试：`backend/tests/test_four_color_import_api.py`（追加）

- [ ] **步骤 1：追加失败测试**

在 `backend/tests/test_four_color_import_api.py` 末尾追加：

```python
# ── Schema ──


def _commit_zone(name="分区1", level="重大", points=None):
    pts = points or [{"x": 10, "y": 10}, {"x": 30, "y": 10}, {"x": 30, "y": 40}]
    return FourColorCommitZone(name=name, risk_level=level, polygons=[{"points": pts}])


def test_commit_request_accepts_valid_payload():
    req = FourColorCommitRequest(file_token="a" * 32, zones=[_commit_zone()], replace_existing=True)
    assert req.zones[0].risk_level == "重大"
    assert req.file_token == "a" * 32


def test_commit_request_rejects_unknown_level():
    with pytest.raises(ValidationError):
        _commit_zone(level="绿色")


def test_commit_request_rejects_too_few_points():
    with pytest.raises(ValidationError):
        _commit_zone(points=[{"x": 1, "y": 2}])


def test_commit_request_rejects_out_of_range_point():
    with pytest.raises(ValidationError):
        RiskPolygonPoint(x=150, y=50)


def test_commit_request_rejects_empty_zones():
    with pytest.raises(ValidationError):
        FourColorCommitRequest(file_token="a" * 32, zones=[], replace_existing=True)
```

- [ ] **步骤 2：运行测试确认失败**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_four_color_import_api.py -q`
预期：FAIL，报错 `ImportError: cannot import name 'FourColorCommitRequest'`

- [ ] **步骤 3：实现代码**

在 `backend/app/schemas/risk_management.py` 末尾（`RiskZoneFloorPlanPolygon` 定义之后）追加：

```python
class FourColorDraftPolygon(BaseModel):
    id: str
    label: str | None = None
    points: list[RiskPolygonPoint] = Field(min_length=3)


class FourColorDraftZone(BaseModel):
    client_id: str
    name: str
    risk_level: Literal["重大", "较大", "一般", "低"]
    color: str
    polygons: list[FourColorDraftPolygon] = Field(min_length=1)


class FourColorAnalyzeResponse(BaseModel):
    preview_url: str
    canvas_width: int
    canvas_height: int
    zones: list[FourColorDraftZone]
    warnings: list[str] = []


class FourColorCommitPolygon(BaseModel):
    points: list[RiskPolygonPoint] = Field(min_length=3)


class FourColorCommitZone(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    risk_level: Literal["重大", "较大", "一般", "低"]
    polygons: list[FourColorCommitPolygon] = Field(min_length=1)


class FourColorCommitRequest(BaseModel):
    file_token: str
    zones: list[FourColorCommitZone] = Field(min_length=1, max_length=200)
    replace_existing: bool = True


class FourColorCommitResponse(BaseModel):
    floor: FloorResponse
    zones: list[RiskZoneResponse]
```

- [ ] **步骤 4：运行测试确认通过**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_four_color_import_api.py -q`
预期：12 passed

- [ ] **步骤 5：Commit**

```powershell
git add backend/app/schemas/risk_management.py backend/tests/test_four_color_import_api.py
git commit -m "feat(risk-mapping): four-color import schemas"
```

### 任务 6：端点——analyze 四色图识别

**文件：**
- 修改：`backend/app/routers/risk_management.py`
- 测试：`backend/tests/test_four_color_import_api.py`（追加）

- [ ] **步骤 1：追加失败测试**

在 `backend/tests/test_four_color_import_api.py` 末尾追加：

```python
# ── 端点：analyze ──


def _ent_exec_result(ent):
    m = MagicMock()
    m.scalar_one_or_none.return_value = ent
    return m


def _floor_exec_result(floor):
    m = MagicMock()
    m.scalar_one_or_none.return_value = floor
    return m


class FakeUpload:
    def __init__(self, data: bytes, content_type="image/png"):
        self.data = data
        self.content_type = content_type
        self.filename = "sample.png"
        self.size = len(data)
        self.headers = {}

    async def read(self):
        return self.data


@pytest.mark.asyncio
async def test_analyze_returns_zones_and_does_not_touch_db(monkeypatch):
    from app.routers import risk_management as rm

    db = AsyncMock()
    db.execute.side_effect = [_ent_exec_result(MagicMock()), _floor_exec_result(MagicMock())]
    monkeypatch.setattr(rm, "save_four_color_temp", MagicMock(return_value=("/uploads/tmp/x.png", "a" * 32)))
    resp = await rm.analyze_four_color("f-1", "e-1", FakeUpload(_four_color_png()), current_user=MagicMock(), db=db)
    data = resp.data
    assert data.canvas_width == 600 and data.canvas_height == 450
    assert len(data.zones) == 4
    assert {z.risk_level for z in data.zones} == {"重大", "较大", "一般", "低"}
    assert db.add.call_count == 0
    assert db.commit.call_count == 0


@pytest.mark.asyncio
async def test_analyze_no_zones_returns_422(monkeypatch):
    from app.routers import risk_management as rm

    db = AsyncMock()
    db.execute.side_effect = [_ent_exec_result(MagicMock()), _floor_exec_result(MagicMock())]
    monkeypatch.setattr(rm, "save_four_color_temp", MagicMock(return_value=("/uploads/tmp/x.png", "a" * 32)))
    remove_mock = MagicMock()
    monkeypatch.setattr(rm, "remove_four_color_temp_dir", remove_mock)
    upload = FakeUpload(_png_bytes(color=(255, 255, 255)))  # 纯白
    with pytest.raises(HTTPException) as exc:
        await rm.analyze_four_color("f-1", "e-1", upload, current_user=MagicMock(), db=db)
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "NO_ZONE_DETECTED"
    remove_mock.assert_called_once_with("e-1", "f-1", "a" * 32)


@pytest.mark.asyncio
async def test_analyze_invalid_image_returns_422(monkeypatch):
    from app.routers import risk_management as rm

    db = AsyncMock()
    db.execute.side_effect = [_ent_exec_result(MagicMock()), _floor_exec_result(MagicMock())]
    monkeypatch.setattr(rm, "save_four_color_temp", MagicMock(return_value=("/uploads/tmp/x.png", "a" * 32)))
    remove_mock = MagicMock()
    monkeypatch.setattr(rm, "remove_four_color_temp_dir", remove_mock)
    with pytest.raises(HTTPException) as exc:
        await rm.analyze_four_color("f-1", "e-1", FakeUpload(b"not-an-image"), current_user=MagicMock(), db=db)
    assert exc.value.status_code == 422
    remove_mock.assert_called_once_with("e-1", "f-1", "a" * 32)


@pytest.mark.asyncio
async def test_analyze_floor_not_found_404():
    from app.routers import risk_management as rm

    db = AsyncMock()
    db.execute.side_effect = [_ent_exec_result(MagicMock()), _floor_exec_result(None)]
    with pytest.raises(HTTPException) as exc:
        await rm.analyze_four_color("f-x", "e-1", FakeUpload(b"x"), current_user=MagicMock(), db=db)
    assert exc.value.status_code == 404
```

- [ ] **步骤 2：运行测试确认失败**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_four_color_import_api.py -q`
预期：FAIL，报错 `AttributeError: module 'app.routers.risk_management' has no attribute 'analyze_four_color'`

- [ ] **步骤 3：实现代码**

在 `backend/app/routers/risk_management.py` 修改 import：

```python
from sqlalchemy import select, func, update, delete
```

并把 schema import 行追加：

```python
    FourColorAnalyzeResponse,
    FourColorCommitRequest,
    FourColorCommitResponse,
```

存储服务 import 行改为：

```python
from app.services.floor_plan_storage_service import (
    save_floor_plan,
    remove_floor_plan,
    remove_floor_plan_dir,
    normalize_floor_plan_url,
    save_four_color_temp,
    promote_four_color_file,
    remove_four_color_temp_dir,
    four_color_temp_dir,
)
```

并新增：

```python
from app.services.four_color_recognizer import recognize_from_bytes
```

在 `upload_floor_plan` 端点之后新增：

```python
@router.post("/floors/{floor_id}/four-color/analyze", response_model=ApiResponse[FourColorAnalyzeResponse])
async def analyze_four_color(floor_id: str, enterprise_id: str, file: UploadFile = File(...), current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floor = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.id == floor_id, EnterpriseFloor.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not floor:
        raise HTTPException(404, "楼层不存在")
    data = await file.read()
    preview_url, token = save_four_color_temp(enterprise_id, floor_id, data, file.content_type)
    try:
        result = recognize_from_bytes(data)
    except Exception:
        remove_four_color_temp_dir(enterprise_id, floor_id, token)
        raise HTTPException(422, "图片解析失败，请检查图片格式")
    if not result.zones:
        remove_four_color_temp_dir(enterprise_id, floor_id, token)
        raise HTTPException(422, detail={"code": "NO_ZONE_DETECTED", "message": "未识别到红/橙/黄/蓝色块，请检查图片"})
    return ApiResponse(data=FourColorAnalyzeResponse(
        preview_url=preview_url,
        canvas_width=result.width,
        canvas_height=result.height,
        zones=result.zones,
        warnings=result.warnings,
    ))
```

- [ ] **步骤 4：运行测试确认通过**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_four_color_import_api.py backend/tests/test_floor_plan_upload.py -q`
预期：全部通过（本文件 16 passed + 既有上传测试）

- [ ] **步骤 5：Commit**

```powershell
git add backend/app/routers/risk_management.py backend/tests/test_four_color_import_api.py
git commit -m "feat(risk-mapping): four-color analyze endpoint"
```

### 任务 7：端点——commit 落图与替换

**文件：**
- 修改：`backend/app/routers/risk_management.py`
- 测试：`backend/tests/test_four_color_import_api.py`（追加）

- [ ] **步骤 1：追加失败测试**

在 `backend/tests/test_four_color_import_api.py` 末尾追加：

```python
# ── 端点：commit ──


def _count_exec_result(n):
    m = MagicMock()
    m.scalar.return_value = n
    return m


def _zones_exec_result(zones):
    m = MagicMock()
    m.scalars.return_value.all.return_value = zones
    return m


def _commit_body(replace=True, level="重大"):
    return FourColorCommitRequest(
        file_token="a" * 32,
        zones=[_commit_zone(level=level)],
        replace_existing=replace,
    )


@pytest.mark.asyncio
async def test_commit_rejects_invalid_session(monkeypatch):
    from app.routers import risk_management as rm

    db = AsyncMock()
    db.execute.side_effect = [_ent_exec_result(MagicMock()), _floor_exec_result(MagicMock())]
    monkeypatch.setattr(rm, "four_color_temp_dir", MagicMock(return_value=None))
    with pytest.raises(HTTPException) as exc:
        await rm.commit_four_color_import(_commit_body(), "f-1", "e-1", current_user=MagicMock(), db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_commit_rejects_not_empty_without_replace(monkeypatch):
    from app.routers import risk_management as rm

    floor = MagicMock()
    floor.is_default = False
    floor.canvas_texts = []
    db = AsyncMock()
    db.execute.side_effect = [
        _ent_exec_result(MagicMock()),
        _floor_exec_result(floor),
        _count_exec_result(2),  # 已有分区
        _count_exec_result(0),  # 未绑定风险点
    ]
    monkeypatch.setattr(rm, "four_color_temp_dir", MagicMock(return_value=MagicMock()))
    with pytest.raises(HTTPException) as exc:
        await rm.commit_four_color_import(_commit_body(replace=False), "f-1", "e-1", current_user=MagicMock(), db=db)
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "FLOOR_NOT_EMPTY"


@pytest.mark.asyncio
async def test_commit_rejects_polygon_validation_failure(monkeypatch):
    from app.routers import risk_management as rm

    floor = MagicMock()
    floor.is_default = False
    db = AsyncMock()
    db.execute.side_effect = [_ent_exec_result(MagicMock()), _floor_exec_result(floor)]
    monkeypatch.setattr(rm, "four_color_temp_dir", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(rm, "validate_polygon_v2", MagicMock(return_value=["坐标越界"]))
    with pytest.raises(HTTPException) as exc:
        await rm.commit_four_color_import(_commit_body(), "f-1", "e-1", current_user=MagicMock(), db=db)
    assert exc.value.status_code == 422
    assert "坐标越界" in exc.value.detail


@pytest.mark.asyncio
async def test_commit_replace_deletes_old_zones_and_creates_new(monkeypatch):
    from app.routers import risk_management as rm

    floor = MagicMock()
    floor.is_default = False
    floor.canvas_texts = ["旧文字"]
    old_zone = MagicMock()
    db = AsyncMock()
    db.execute.side_effect = [
        _ent_exec_result(MagicMock()),
        _floor_exec_result(floor),
        _zones_exec_result([old_zone]),
        MagicMock(),          # delete 未绑定风险对象
        _count_exec_result(0),  # _floor_response zone_count
        _count_exec_result(0),  # _floor_response risk_point_count
    ]
    monkeypatch.setattr(rm, "four_color_temp_dir", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(rm, "promote_four_color_file", MagicMock(return_value=("/uploads/enterprises/e-1/floors/f-1/20260806_x.png", 600, 450)))
    remove_tmp = MagicMock()
    remove_old = MagicMock()
    monkeypatch.setattr(rm, "remove_four_color_temp_dir", remove_tmp)
    monkeypatch.setattr(rm, "remove_floor_plan", remove_old)
    body = FourColorCommitRequest(
        file_token="a" * 32,
        zones=[
            _commit_zone(name="重大区", level="重大"),
            _commit_zone(name="低风险区", level="低"),
        ],
        replace_existing=True,
    )
    resp = await rm.commit_four_color_import(body, "f-1", "e-1", current_user=MagicMock(), db=db)
    db.delete.assert_called_once_with(old_zone)
    assert floor.floor_plan_url == "/uploads/enterprises/e-1/floors/f-1/20260806_x.png"
    assert floor.canvas_width == 600 and floor.canvas_height == 450
    assert floor.canvas_texts == []
    assert db.add.call_count == 2
    assert db.commit.call_count == 1
    remove_tmp.assert_called_once_with("e-1", "f-1", "a" * 32)
    remove_old.assert_called_once()
    assert len(resp.data.zones) == 2
    created_polys = [call.args[0].floor_plan_polygon for call in db.add.call_args_list]
    assert created_polys[0]["color"] == "#ff4d4f"
    assert created_polys[1]["color"] == "#52c41a"


@pytest.mark.asyncio
async def test_commit_without_replace_on_empty_floor_creates_zones(monkeypatch):
    from app.routers import risk_management as rm

    floor = MagicMock()
    floor.is_default = False
    floor.canvas_texts = []
    db = AsyncMock()
    db.execute.side_effect = [
        _ent_exec_result(MagicMock()),
        _floor_exec_result(floor),
        _count_exec_result(0),  # 分区数
        _count_exec_result(0),  # 未绑定风险点数
        _count_exec_result(0),  # _floor_response zone_count
        _count_exec_result(0),  # _floor_response risk_point_count
    ]
    monkeypatch.setattr(rm, "four_color_temp_dir", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(rm, "promote_four_color_file", MagicMock(return_value=("/uploads/enterprises/e-1/floors/f-1/20260806_x.png", 600, 450)))
    monkeypatch.setattr(rm, "remove_four_color_temp_dir", MagicMock())
    monkeypatch.setattr(rm, "remove_floor_plan", MagicMock())
    resp = await rm.commit_four_color_import(_commit_body(replace=False), "f-1", "e-1", current_user=MagicMock(), db=db)
    assert resp.data.zones[0].name == "分区1"
    assert db.delete.call_count == 0
```

- [ ] **步骤 2：运行测试确认失败**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_four_color_import_api.py -q`
预期：FAIL，报错 `AttributeError: module 'app.routers.risk_management' has no attribute 'commit_four_color_import'`

- [ ] **步骤 3：实现代码**

在 `backend/app/routers/risk_management.py` 中，`LEVEL_COLORS` 加入 service import：

```python
from app.services.risk_mapping_service import (
    ensure_default_floor,
    validate_polygon_v2,
    normalize_polygon,
    effective_color,
    max_risk_level,
    cascade_counts,
    LEVEL_COLORS,
)
```

在 `analyze_four_color` 端点之后新增：

```python
@router.post("/floors/{floor_id}/four-color/commit", response_model=ApiResponse[FourColorCommitResponse])
async def commit_four_color_import(body: FourColorCommitRequest, floor_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floor = (await db.execute(
        select(EnterpriseFloor).where(EnterpriseFloor.id == floor_id, EnterpriseFloor.enterprise_id == enterprise_id).with_for_update()
    )).scalar_one_or_none()
    if not floor:
        raise HTTPException(404, "楼层不存在")
    if four_color_temp_dir(enterprise_id, floor_id, body.file_token) is None:
        raise HTTPException(404, "导入会话不存在")
    if not body.replace_existing:
        zone_count = (await db.execute(select(func.count(RiskZone.id)).where(RiskZone.floor_id == floor_id))).scalar() or 0
        unbound_point_count = (await db.execute(select(func.count(RiskObject.id)).where(RiskObject.floor_id == floor_id, RiskObject.zone_id.is_(None)))).scalar() or 0
        if zone_count or unbound_point_count or floor.canvas_texts:
            raise HTTPException(422, detail={"code": "FLOOR_NOT_EMPTY", "message": "楼层已有分区、风险点或文字标注，请确认替换后重试"})
    for zone in body.zones:
        polygon_v2 = {
            "version": 2,
            "color_source": "manual",
            "color": LEVEL_COLORS[zone.risk_level],
            "polygons": [
                {"id": f"poly-{i}", "label": zone.name, "points": [p.model_dump() for p in poly.points]}
                for i, poly in enumerate(zone.polygons)
            ],
        }
        errors = validate_polygon_v2(polygon_v2)
        if errors:
            raise HTTPException(422, f"分区「{zone.name}」多边形校验失败：{'；'.join(errors)}")
    try:
        new_url, width, height = promote_four_color_file(enterprise_id, floor_id, body.file_token)
    except FileNotFoundError:
        raise HTTPException(404, "导入会话不存在")
    old_url = floor.floor_plan_url
    if body.replace_existing:
        old_zones = (await db.execute(select(RiskZone).where(RiskZone.floor_id == floor_id))).scalars().all()
        for z in old_zones:
            await db.delete(z)
        await db.execute(delete(RiskObject).where(RiskObject.floor_id == floor_id, RiskObject.zone_id.is_(None)))
        floor.canvas_texts = []
    floor.floor_plan_url = new_url
    floor.canvas_width = width
    floor.canvas_height = height
    if floor.is_default:
        ent = (await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))).scalar_one()
        ent.floor_plan_url = new_url
    created: list[RiskZone] = []
    for i, zone in enumerate(body.zones):
        new_zone = RiskZone(
            enterprise_id=enterprise_id,
            floor_id=floor_id,
            name=zone.name,
            description=None,
            sort_order=i,
            floor_plan_polygon={
                "version": 2,
                "color_source": "manual",
                "color": LEVEL_COLORS[zone.risk_level],
                "polygons": [
                    {"id": f"poly-{i}-{j}", "label": zone.name, "points": [p.model_dump() for p in poly.points]}
                    for j, poly in enumerate(zone.polygons)
                ],
            },
        )
        db.add(new_zone)
        created.append(new_zone)
    await db.commit()
    remove_four_color_temp_dir(enterprise_id, floor_id, body.file_token)
    if body.replace_existing:
        remove_floor_plan(old_url)
    await db.refresh(floor)
    return ApiResponse(data=FourColorCommitResponse(
        floor=await _floor_response(db, floor),
        zones=[RiskZoneResponse.model_validate(z) for z in created],
    ))
```

- [ ] **步骤 4：运行测试确认通过**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_four_color_import_api.py -q`
预期：21 passed

- [ ] **步骤 5：Commit**

```powershell
git add backend/app/routers/risk_management.py backend/tests/test_four_color_import_api.py
git commit -m "feat(risk-mapping): four-color commit endpoint with replace semantics"
```

### 任务 8：端点——cancel 清理临时文件

**文件：**
- 修改：`backend/app/routers/risk_management.py`
- 测试：`backend/tests/test_four_color_import_api.py`（追加）

- [ ] **步骤 1：追加失败测试**

在 `backend/tests/test_four_color_import_api.py` 末尾追加：

```python
# ── 端点：cancel ──


@pytest.mark.asyncio
async def test_cancel_removes_temp_dir(monkeypatch):
    from app.routers import risk_management as rm

    db = AsyncMock()
    db.execute.side_effect = [_ent_exec_result(MagicMock()), _floor_exec_result(MagicMock())]
    monkeypatch.setattr(rm, "four_color_temp_dir", MagicMock(return_value=MagicMock()))
    remove_mock = MagicMock()
    monkeypatch.setattr(rm, "remove_four_color_temp_dir", remove_mock)
    resp = await rm.cancel_four_color_import("a" * 32, "f-1", "e-1", current_user=MagicMock(), db=db)
    assert resp.message == "已清理临时文件"
    remove_mock.assert_called_once_with("e-1", "f-1", "a" * 32)


@pytest.mark.asyncio
async def test_cancel_invalid_session_404(monkeypatch):
    from app.routers import risk_management as rm

    db = AsyncMock()
    db.execute.side_effect = [_ent_exec_result(MagicMock()), _floor_exec_result(MagicMock())]
    monkeypatch.setattr(rm, "four_color_temp_dir", MagicMock(return_value=None))
    with pytest.raises(HTTPException) as exc:
        await rm.cancel_four_color_import("bad-token", "f-1", "e-1", current_user=MagicMock(), db=db)
    assert exc.value.status_code == 404
```

- [ ] **步骤 2：运行测试确认失败**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_four_color_import_api.py -q`
预期：FAIL，报错 `AttributeError: module 'app.routers.risk_management' has no attribute 'cancel_four_color_import'`

- [ ] **步骤 3：实现代码**

在 `commit_four_color_import` 端点之后新增：

```python
@router.delete("/floors/{floor_id}/four-color/{file_token}")
async def cancel_four_color_import(file_token: str, floor_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floor = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.id == floor_id, EnterpriseFloor.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not floor:
        raise HTTPException(404, "楼层不存在")
    if four_color_temp_dir(enterprise_id, floor_id, file_token) is None:
        raise HTTPException(404, "导入会话不存在")
    remove_four_color_temp_dir(enterprise_id, floor_id, file_token)
    return ApiResponse(data=None, message="已清理临时文件")
```

- [ ] **步骤 4：运行测试确认通过**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_four_color_import_api.py -q`
预期：23 passed

- [ ] **步骤 5：Commit**

```powershell
git add backend/app/routers/risk_management.py backend/tests/test_four_color_import_api.py
git commit -m "feat(risk-mapping): four-color cancel endpoint"
```

### 任务 9：前端——类型与服务函数

**文件：**
- 修改：`frontend/src/types/riskMappingWorkbench.ts`
- 修改：`frontend/src/services/riskMappingWorkbenchService.ts`
- 测试：`frontend/src/services/riskMappingWorkbenchService.test.ts`（新增）

- [ ] **步骤 1：编写失败测试**

创建 `frontend/src/services/riskMappingWorkbenchService.test.ts`：

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  analyzeFourColorMap,
  cancelFourColorImport,
  commitFourColorImport,
} from "./riskMappingWorkbenchService";
import type { FourColorAnalyzeResult } from "@/types/riskMappingWorkbench";

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

vi.mock("@/services/api", () => ({ default: apiMock }));

describe("riskMappingWorkbenchService four-color", () => {
  beforeEach(() => vi.clearAllMocks());

  it("analyzeFourColorMap 上传文件并解包 data", async () => {
    const data: FourColorAnalyzeResult = {
      preview_url: "/uploads/x.png",
      canvas_width: 600,
      canvas_height: 450,
      zones: [{
        client_id: "d1",
        name: "分区1",
        risk_level: "重大",
        color: "#ff4d4f",
        polygons: [{ id: "p1", label: null, points: [{ x: 10, y: 10 }, { x: 30, y: 10 }, { x: 30, y: 40 }] }],
      }],
      warnings: [],
    };
    apiMock.post.mockResolvedValue({ data: { code: 0, message: "ok", data } });
    const file = new File(["x"], "a.png", { type: "image/png" });
    const result = await analyzeFourColorMap("e1", "f1", file);
    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/risk-management/floors/f1/four-color/analyze",
      expect.any(FormData),
    );
    expect(result.canvas_width).toBe(600);
    expect(result.zones[0].risk_level).toBe("重大");
  });

  it("commitFourColorImport 提交 payload 并解包 data", async () => {
    apiMock.post.mockResolvedValue({
      data: { code: 0, message: "ok", data: { floor: { id: "f1" }, zones: [] } },
    });
    const result = await commitFourColorImport("e1", "f1", {
      file_token: "abc",
      zones: [{ name: "分区1", risk_level: "低", polygons: [{ points: [{ x: 1, y: 2 }, { x: 3, y: 4 }, { x: 5, y: 6 }] }] }],
      replace_existing: true,
    });
    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/risk-management/floors/f1/four-color/commit",
      expect.objectContaining({ file_token: "abc", replace_existing: true }),
    );
    expect(result.floor.id).toBe("f1");
  });

  it("cancelFourColorImport 调用 DELETE", async () => {
    apiMock.delete.mockResolvedValue({ data: { code: 0, message: "ok", data: null } });
    await cancelFourColorImport("e1", "f1", "tok123");
    expect(apiMock.delete).toHaveBeenCalledWith(
      "/enterprises/e1/risk-management/floors/f1/four-color/tok123",
    );
  });
});
```

- [ ] **步骤 2：运行测试确认失败**

运行：`cd frontend; npx vitest run src/services/riskMappingWorkbenchService.test.ts`
预期：FAIL，`Cannot find module './riskMappingWorkbenchService'` 或类型错误（`FourColorAnalyzeResult` 不存在）

- [ ] **步骤 3：实现类型**

在 `frontend/src/types/riskMappingWorkbench.ts` 末尾追加：

```ts
export interface FourColorDraftPolygon {
  id: string;
  label?: string | null;
  points: { x: number; y: number }[];
}
export interface FourColorDraftZone {
  client_id: string;
  name: string;
  risk_level: RiskLevel;
  color: string;
  polygons: FourColorDraftPolygon[];
}
export interface FourColorAnalyzeResult {
  preview_url: string;
  canvas_width: number;
  canvas_height: number;
  zones: FourColorDraftZone[];
  warnings: string[];
}
export interface FourColorCommitPolygon {
  points: { x: number; y: number }[];
}
export interface FourColorCommitZone {
  name: string;
  risk_level: RiskLevel;
  polygons: FourColorCommitPolygon[];
}
export interface FourColorCommitPayload {
  file_token: string;
  zones: FourColorCommitZone[];
  replace_existing: boolean;
}
export interface FourColorCommitResult {
  floor: EnterpriseFloor;
  zones: WorkbenchZone[];
}
```

- [ ] **步骤 4：实现服务函数**

在 `frontend/src/services/riskMappingWorkbenchService.ts` 末尾追加：

```ts
export const analyzeFourColorMap = (eid: string, floorId: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api
    .post<ApiResponse<FourColorAnalyzeResult>>(`${BASE(eid)}/floors/${floorId}/four-color/analyze`, form)
    .then(r => r.data.data);
};

export const commitFourColorImport = (eid: string, floorId: string, payload: FourColorCommitPayload) =>
  api
    .post<ApiResponse<FourColorCommitResult>>(`${BASE(eid)}/floors/${floorId}/four-color/commit`, payload)
    .then(r => r.data.data);

export const cancelFourColorImport = (eid: string, floorId: string, token: string) =>
  api.delete(`${BASE(eid)}/floors/${floorId}/four-color/${token}`);
```

同时更新文件顶部 import：

```ts
import type {
  RawWorkbenchSnapshot,
  BatchSavePayload,
  BatchSaveResponse,
  EnterpriseFloor,
  FourColorAnalyzeResult,
  FourColorCommitPayload,
  FourColorCommitResult,
} from "@/types/riskMappingWorkbench";
```

- [ ] **步骤 5：运行测试确认通过**

运行：`cd frontend; npx vitest run src/services/riskMappingWorkbenchService.test.ts`
预期：3 passed

- [ ] **步骤 6：类型检查 + Commit**

运行：`cd frontend; npx tsc -b`
预期：exit 0

```powershell
cd frontend
git add src/types/riskMappingWorkbench.ts src/services/riskMappingWorkbenchService.ts src/services/riskMappingWorkbenchService.test.ts
git commit -m "feat(risk-mapping): four-color import service and types"
```

### 任务 10：前端——FourColorImportModal 组件

**文件：**
- 创建：`frontend/src/components/enterprise/riskMapping/FourColorImportModal.tsx`

（组件交互由任务 12 E2E 覆盖；本任务以 tsc 类型检查为验证。）

- [ ] **步骤 1：创建组件**

创建 `frontend/src/components/enterprise/riskMapping/FourColorImportModal.tsx`：

```tsx
import { useRef, useState } from "react";
import { Alert, Button, Checkbox, Input, List, Modal, Spin, Tag, Upload, message } from "antd";
import { InboxOutlined } from "@ant-design/icons";
import {
  analyzeFourColorMap,
  cancelFourColorImport,
  commitFourColorImport,
} from "@/services/riskMappingWorkbenchService";
import type {
  FourColorAnalyzeResult,
  FourColorCommitResult,
  FourColorDraftZone,
} from "@/types/riskMappingWorkbench";

interface FourColorImportModalProps {
  open: boolean;
  enterpriseId: string;
  floorId: string;
  hasExistingData: boolean;
  existingZoneCount: number;
  existingRiskPointCount: number;
  onClose: () => void;
  onImported: (result: FourColorCommitResult) => void;
}

type Stage = "select" | "analyzing" | "preview";

const LEVEL_COLORS: Record<string, string> = {
  重大: "#ff4d4f",
  较大: "#fa8c16",
  一般: "#fadb14",
  低: "#52c41a",
};

function extractToken(previewUrl: string): string {
  return previewUrl.split("/four_color_tmp/")[1]?.split("/")[0] ?? "";
}

export default function FourColorImportModal({
  open,
  enterpriseId,
  floorId,
  hasExistingData,
  existingZoneCount,
  existingRiskPointCount,
  onClose,
  onImported,
}: FourColorImportModalProps) {
  const [stage, setStage] = useState<Stage>("select");
  const [result, setResult] = useState<FourColorAnalyzeResult | null>(null);
  const [zones, setZones] = useState<FourColorDraftZone[]>([]);
  const [replaceExisting, setReplaceExisting] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const fileRef = useRef<File | null>(null);

  const reset = () => {
    setStage("select");
    setResult(null);
    setZones([]);
    setReplaceExisting(true);
    fileRef.current = null;
  };

  const handleClose = () => {
    const token = result ? extractToken(result.preview_url) : "";
    if (token) {
      cancelFourColorImport(enterpriseId, floorId, token).catch(() => undefined);
    }
    reset();
    onClose();
  };

  const runAnalyze = async (file: File) => {
    fileRef.current = file;
    setStage("analyzing");
    try {
      const res = await analyzeFourColorMap(enterpriseId, floorId, file);
      setResult(res);
      setZones(res.zones);
      setStage("preview");
    } catch (e) {
      const err = e as { response?: { data?: { detail?: { code?: string; message?: string } } } };
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === "string" ? detail : detail?.message;
      if (detail && typeof detail !== "string" && detail.code === "NO_ZONE_DETECTED") {
        message.error(msg || "未识别到红/橙/黄/蓝色块，请检查图片");
      } else {
        message.error(msg || "识别失败，请重试");
      }
      setStage("select");
    }
  };

  const handleCommit = async () => {
    if (!result || zones.length === 0) return;
    setSubmitting(true);
    try {
      const payload = {
        file_token: extractToken(result.preview_url),
        zones: zones.map(z => ({
          name: z.name,
          risk_level: z.risk_level,
          polygons: z.polygons.map(p => ({ points: p.points })),
        })),
        replace_existing: replaceExisting,
      };
      const commitResult = await commitFourColorImport(enterpriseId, floorId, payload);
      onImported(commitResult);
      reset();
    } catch (e) {
      const err = e as { response?: { data?: { detail?: { code?: string; message?: string } } } };
      const detail = err?.response?.data?.detail;
      message.error(typeof detail === "string" ? detail : detail?.message || "落图失败，请重试");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      title="导入四色分布图"
      width={860}
      onCancel={handleClose}
      destroyOnClose
      footer={[
        <Button key="cancel" onClick={handleClose}>取消</Button>,
        <Button
          key="commit"
          type="primary"
          disabled={stage !== "preview" || zones.length === 0 || submitting}
          loading={submitting}
          onClick={handleCommit}
        >
          确认落图
        </Button>,
      ]}
    >
      {stage === "select" && (
        <Upload.Dragger
          accept="image/png,image/jpeg,image/webp"
          showUploadList={false}
          beforeUpload={file => {
            runAnalyze(file as unknown as File);
            return false;
          }}
        >
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">点击或拖拽上传四色分布图（PNG/JPEG/WebP，≤20MB）</p>
        </Upload.Dragger>
      )}
      {stage === "analyzing" && (
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin tip="正在识别四色区域…">
            <div style={{ width: 80, height: 80 }} />
          </Spin>
        </div>
      )}
      {stage === "preview" && result && (
        <div>
          {result.warnings.map(w => (
            <Alert key={w} type="warning" showIcon message={w} style={{ marginBottom: 8 }} />
          ))}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 12, minHeight: 320 }}>
            <div style={{ position: "relative", background: "#fafafa", borderRadius: 8, overflow: "hidden" }}>
              <img
                src={result.preview_url}
                alt="四色分布图预览"
                style={{
                  display: "block",
                  width: "100%",
                  aspectRatio: `${result.canvas_width} / ${result.canvas_height}`,
                  objectFit: "contain",
                }}
              />
              <svg
                viewBox="0 0 100 100"
                preserveAspectRatio="none"
                style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
              >
                {zones.map(z =>
                  z.polygons.map(p => (
                    <polygon
                      key={p.id}
                      points={p.points.map(pt => `${pt.x},${pt.y}`).join(" ")}
                      fill={LEVEL_COLORS[z.risk_level]}
                      fillOpacity={0.35}
                      stroke={LEVEL_COLORS[z.risk_level]}
                      strokeWidth={1}
                      vectorEffect="non-scaling-stroke"
                    />
                  )),
                )}
              </svg>
            </div>
            <div>
              <List
                size="small"
                dataSource={zones}
                locale={{ emptyText: "未识别到分区" }}
                renderItem={(z, i) => (
                  <List.Item
                    actions={[
                      <Button
                        key="del"
                        type="text"
                        danger
                        onClick={() => setZones(zones.filter(x => x.client_id !== z.client_id))}
                      >
                        删除
                      </Button>,
                    ]}
                  >
                    <div style={{ width: "100%" }}>
                      <Input
                        value={z.name}
                        aria-label={`分区名称${i + 1}`}
                        onChange={e =>
                          setZones(zones.map(x => (x.client_id === z.client_id ? { ...x, name: e.target.value } : x)))
                        }
                        style={{ marginBottom: 4 }}
                      />
                      <Tag color={LEVEL_COLORS[z.risk_level]}>{z.risk_level}</Tag>
                      <span style={{ color: "#999", fontSize: 12 }}>
                        {z.polygons.length} 个多边形 · {z.polygons[0]?.points.length ?? 0} 个顶点
                      </span>
                    </div>
                  </List.Item>
                )}
              />
              {hasExistingData && (
                <Checkbox
                  checked={replaceExisting}
                  onChange={e => setReplaceExisting(e.target.checked)}
                  style={{ marginTop: 12 }}
                >
                  移除该楼层原有分区、文字标注与风险点（{existingZoneCount} 个分区 / {existingRiskPointCount} 个风险点）后导入
                </Checkbox>
              )}
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}
```

- [ ] **步骤 2：类型检查**

运行：`cd frontend; npx tsc -b`
预期：exit 0（组件未被页面引用，tsc 仍会检查该文件）

- [ ] **步骤 3：Commit**

```powershell
cd frontend
git add src/components/enterprise/riskMapping/FourColorImportModal.tsx
git commit -m "feat(risk-mapping): four-color import modal component"
```

### 任务 11：前端——工作台页面集成

**文件：**
- 修改：`frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx`

- [ ] **步骤 1：修改页面**

在 `RiskMappingWorkbenchPage.tsx`：

1. import 追加：

```tsx
import { UploadOutlined } from "@ant-design/icons";
import FourColorImportModal from "@/components/enterprise/riskMapping/FourColorImportModal";
```

2. 在组件内新增状态与选择器（放在 `dirty` 声明之后）：

```tsx
const [importOpen, setImportOpen] = useState(false);
const floors = useRiskMappingWorkbenchStore(s => s.floors);
const zones = useRiskMappingWorkbenchStore(s => s.zones);
const riskPoints = useRiskMappingWorkbenchStore(s => s.riskPoints);
const texts = useRiskMappingWorkbenchStore(s => s.texts);
const currentFloor = floors.find(f => f.id === currentFloorId);
```

3. 在 `EnterpriseFloorManager` 与 `WorkbenchToolbar` 之间插入按钮：

```tsx
<Button
  aria-label="导入四色图"
  icon={<UploadOutlined />}
  disabled={!currentFloor}
  onClick={() => setImportOpen(true)}
>
  导入四色图
</Button>
```

4. 在 `</div>`（最外层 flex 容器结尾）之前插入弹窗：

```tsx
<FourColorImportModal
  open={importOpen}
  enterpriseId={enterpriseId!}
  floorId={currentFloor?.id ?? ""}
  hasExistingData={zones.length > 0 || riskPoints.length > 0 || texts.length > 0}
  existingZoneCount={zones.length}
  existingRiskPointCount={riskPoints.length}
  onClose={() => setImportOpen(false)}
  onImported={result => {
    setImportOpen(false);
    const state = useRiskMappingWorkbenchStore.getState();
    setSnapshot({
      floors: state.floors.map(f => (f.id === result.floor.id ? result.floor : f)),
      currentFloorId: result.floor.id,
      zones: result.zones,
      riskPoints: [],
      texts: [],
      pendingRegions: [],
      deletedRiskPointIds: [],
      deletedZoneIds: [],
    });
    useRiskMappingWorkbenchStore.getState().markSaved();
    message.success("四色图导入成功");
    queryClient.invalidateQueries({ queryKey: ["risk-hierarchy", enterpriseId] });
    queryClient.invalidateQueries({ queryKey: ["risk-overview", enterpriseId] });
  }}
/>
```

- [ ] **步骤 2：类型检查 + 构建**

运行：`cd frontend; npx tsc -b`
预期：exit 0

运行：`cd frontend; npm run build`
预期：构建成功（PWA 输出正常；Node ≥24 时按 vite.config 自动跳过 PWA）

- [ ] **步骤 3：Commit**

```powershell
cd frontend
git add src/pages/Enterprise/RiskMappingWorkbenchPage.tsx
git commit -m "feat(risk-mapping): wire four-color import into workbench page"
```

### 任务 12：E2E——导入四色图全流程

**文件：**
- 创建：`frontend/e2e/fixtures/four-color-sample.png`（脚本生成）
- 创建：`frontend/e2e/four-color-import.spec.ts`

- [ ] **步骤 1：生成测试图 fixture**

运行（仓库根目录）：

```powershell
@'
from PIL import Image, ImageDraw
img = Image.new("RGB", (600, 450), "white")
d = ImageDraw.Draw(img)
d.rectangle([40, 40, 280, 180], fill=(255, 0, 0))
d.rectangle([320, 40, 560, 180], fill=(255, 127, 0))
d.rectangle([40, 230, 280, 410], fill=(255, 255, 0))
d.rectangle([320, 230, 560, 410], fill=(0, 0, 255))
img.save(r"frontend\e2e\fixtures\four-color-sample.png")
'@ | backend/.venv/Scripts/python.exe -
```

验证：`Test-Path frontend/e2e/fixtures/four-color-sample.png` → True

- [ ] **步骤 2：编写失败测试（E2E）**

创建 `frontend/e2e/four-color-import.spec.ts`：

```ts
import { test, expect, type Page } from "@playwright/test";

const ENTERPRISE_ID = "e2e-four-color-import-enterprise";
const FLOOR_ID = "floor-1";

const FLOOR = {
  id: FLOOR_ID,
  enterprise_id: ENTERPRISE_ID,
  name: "一层",
  sort_order: 0,
  floor_plan_url: null,
  description: null,
  canvas_width: 1200,
  canvas_height: 900,
  canvas_texts: [],
  is_default: true,
  zone_count: 0,
  risk_point_count: 0,
  created_at: "2026-08-06T00:00:00+08:00",
  updated_at: "2026-08-06T00:00:00+08:00",
};

const ANALYZE_ZONES = [
  { client_id: "draft-1", name: "分区1", risk_level: "重大", color: "#ff4d4f", polygons: [{ id: "p1", label: null, points: [{ x: 6.67, y: 8.89 }, { x: 46.67, y: 8.89 }, { x: 46.67, y: 40 }, { x: 6.67, y: 40 }] }] },
  { client_id: "draft-2", name: "分区2", risk_level: "较大", color: "#fa8c16", polygons: [{ id: "p2", label: null, points: [{ x: 53.33, y: 8.89 }, { x: 93.33, y: 8.89 }, { x: 93.33, y: 40 }, { x: 53.33, y: 40 }] }] },
  { client_id: "draft-3", name: "分区3", risk_level: "一般", color: "#fadb14", polygons: [{ id: "p3", label: null, points: [{ x: 6.67, y: 51.11 }, { x: 46.67, y: 51.11 }, { x: 46.67, y: 91.11 }, { x: 6.67, y: 91.11 }] }] },
  { client_id: "draft-4", name: "分区4", risk_level: "低", color: "#52c41a", polygons: [{ id: "p4", label: null, points: [{ x: 53.33, y: 51.11 }, { x: 93.33, y: 51.11 }, { x: 93.33, y: 91.11 }, { x: 53.33, y: 91.11 }] }] },
];

const ANALYZE_DATA = {
  preview_url: "/uploads/four-color-sample.png",
  canvas_width: 600,
  canvas_height: 450,
  zones: ANALYZE_ZONES,
  warnings: [],
};

const COMMIT_DATA = {
  floor: { ...FLOOR, floor_plan_url: "/uploads/four-color-sample.png", canvas_width: 600, canvas_height: 450, zone_count: 4 },
  zones: ANALYZE_ZONES.map((z, i) => ({
    id: `zone-${i + 1}`,
    enterprise_id: ENTERPRISE_ID,
    floor_id: FLOOR_ID,
    floor_name: "一层",
    name: z.name,
    description: null,
    sort_order: i,
    floor_plan_polygon: { version: 2, color_source: "manual", color: z.color, polygons: z.polygons },
    max_risk_level: z.risk_level,
    effective_color: z.color,
    object_count: 0,
    created_at: "2026-08-06T00:00:00+08:00",
    updated_at: "2026-08-06T00:00:00+08:00",
  })),
};

const json = (status: number, body: unknown) => ({
  status,
  contentType: "application/json",
  body: JSON.stringify(body),
});

async function mockApis(page: Page, workbenchZones: unknown[] = []) {
  const workbenchFloor = workbenchZones.length
    ? { ...FLOOR, zone_count: workbenchZones.length }
    : FLOOR;
  await page.route("**/api/v1/auth/login**", route =>
    route.fulfill(json(200, { code: 0, message: "ok", data: { token: "e2e-token", user: { id: "u1", email: "qa_e2e_test@test.com" } } })),
  );
  await page.route("**/risk-management/workbench**", route =>
    route.fulfill(json(200, { code: 0, message: "ok", data: { floors: [workbenchFloor], current_floor_id: FLOOR_ID, zones: workbenchZones, risk_points: [], texts: [] } })),
  );
  await page.route("**/risk-management/floors/**", route =>
    route.fulfill(json(200, { code: 0, message: "ok", data: workbenchFloor })),
  );
  await page.route("**/four-color/analyze", route =>
    route.fulfill(json(200, { code: 0, message: "ok", data: ANALYZE_DATA })),
  );
  await page.route("**/four-color/commit", route =>
    route.fulfill(json(200, { code: 0, message: "ok", data: COMMIT_DATA })),
  );
  await page.route("**/four-color/*", route =>
    route.fulfill(json(200, { code: 0, message: "ok", data: null })),
  );
  await page.route("**/uploads/four-color-sample.png", route =>
    route.fulfill({ status: 200, contentType: "image/png", path: "e2e/fixtures/four-color-sample.png" }),
  );
}

async function loginAndOpenWorkbench(page: Page) {
  await page.goto("/login");
  await page.getByPlaceholder("邮箱").fill("qa_e2e_test@test.com");
  await page.getByPlaceholder("密码").fill("test123456");
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(/\/(dashboard|enterprises)/, { timeout: 10000 });
  await page.goto(`/enterprises/${ENTERPRISE_ID}/risk-mapping-workbench`);
  await expect(page.locator('[data-testid="workbench-canvas"] canvas').first()).toBeVisible({ timeout: 15000 });
}

test.describe("四色分布图自动识别导入", () => {
  test("上传→预览→确认落图→工作台出现分区", async ({ page }) => {
    await mockApis(page);
    await loginAndOpenWorkbench(page);
    await page.getByRole("button", { name: "导入四色图" }).click();
    await page.locator('input[type="file"]').setInputFiles("e2e/fixtures/four-color-sample.png");
    await expect(page.getByText("分区1", { exact: true })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("重大").first()).toBeVisible();
    await expect(page.locator("svg polygon")).toHaveCount(4);
    await page.getByRole("button", { name: "确认落图" }).click();
    await expect(page.getByText("四色图导入成功")).toBeVisible();
    await expect(page.getByText("分区1", { exact: true })).toBeVisible();
  });

  test("楼层已有数据时显示替换确认，导入后旧数据消失", async ({ page }) => {
    const OLD_ZONE = {
      id: "old-zone-1",
      enterprise_id: ENTERPRISE_ID,
      floor_id: FLOOR_ID,
      floor_name: "一层",
      name: "旧分区",
      description: null,
      sort_order: 0,
      floor_plan_polygon: null,
      max_risk_level: null,
      effective_color: null,
      object_count: 0,
      created_at: "2026-08-06T00:00:00+08:00",
      updated_at: "2026-08-06T00:00:00+08:00",
    };
    await mockApis(page, [OLD_ZONE]);
    await loginAndOpenWorkbench(page);
    await page.getByText("旧分区", { exact: true }).first().waitFor();
    await page.getByRole("button", { name: "导入四色图" }).click();
    await page.locator('input[type="file"]').setInputFiles("e2e/fixtures/four-color-sample.png");
    await expect(page.getByRole("checkbox")).toBeVisible();
    await expect(page.getByText(/移除该楼层原有分区/)).toBeVisible();
    await page.getByRole("button", { name: "确认落图" }).click();
    await expect(page.getByText("四色图导入成功")).toBeVisible();
    await expect(page.getByText("旧分区", { exact: true })).toHaveCount(0);
    await expect(page.getByText("分区1", { exact: true })).toBeVisible();
  });
});
```

- [ ] **步骤 3：运行 E2E 确认通过**

运行：`cd frontend; npx playwright test e2e/four-color-import.spec.ts`
预期：2 passed

若失败，优先检查：路由 mock 顺序（analyze/commit 必须先于通配 `**/four-color/*` 注册）、`input[type=file]` 选择器、antd v6 按钮文案。

- [ ] **步骤 4：Commit**

```powershell
cd frontend
git add e2e/four-color-import.spec.ts e2e/fixtures/four-color-sample.png
git commit -m "test(risk-mapping): four-color import e2e"
```

### 任务 13：收尾——全量验证与文档

**文件：**
- 修改：`TASKS.md`（快照更新，不随本任务 commit）

- [ ] **步骤 1：后端全量测试**

运行：`cd backend; .venv\Scripts\python.exe -m pytest -q`
预期：全部通过（既有 69 + 新增 23 = 92 passed，无 skipped/failed）

- [ ] **步骤 2：前端全量验证**

运行：`cd frontend; npx tsc -b`
预期：exit 0

运行：`cd frontend; npx vitest run`
预期：全部通过（既有 + 3 个新服务测试）

运行：`cd frontend; npx playwright test`
预期：既有 E2E + 2 个新用例全部通过

- [ ] **步骤 3：仓库卫生检查**

运行：`git diff --check`
预期：无输出

运行：`git status --short`
预期：仅 TASKS.md 与未跟踪备份文件（如有），无遗漏实现文件

- [ ] **步骤 4：更新 TASKS.md 快照**

在 `TASKS.md`「当前状态快照」或本会话快照区记录：四色图自动识别导入已实现，后端 92 passed、前端 tsc/vitest/E2E 全绿，列出新增端点与文件路径。

- [ ] **步骤 5：提交计划文档**

```powershell
git add docs/superpowers/plans/2026-08-06-four-color-auto-import.md
git commit -m "docs(risk-mapping): four-color auto import implementation plan"
```

---

## 计划自检（作者已执行）

**1. 规格覆盖度：** 对照规格逐章核验——整体流程（任务 11/12）、识别管线四色分类/清理/轮廓/归一化/透视（任务 1-3）、analyze（任务 6）、commit + 替换语义（任务 7）、cancel（任务 8）、前端类型/服务（任务 9）、弹窗组件与预览校对（任务 10）、页面集成（任务 11）、错误处理（NO_ZONE_DETECTED/FLOOR_NOT_EMPTY/校验失败/透视 warning 全覆盖）、测试策略（单测/端点 mock/Playwright）、依赖（任务 0）、文件清单（全部文件出现在各任务）。无规格需求缺任务。

**2. 占位符扫描：** 无"待定/TODO/后续实现/补充细节"；每个代码步骤含完整代码；命令与预期输出齐全。

**3. 类型一致性：** `FourColorAnalyzeResponse.canvas_width/height`、`FourColorDraftZone.risk_level`、`FourColorCommitRequest.replace_existing` 在后端 schema、前端类型、E2E mock 三处命名一致；`LEVEL_COLORS`（后端 `risk_mapping_service`）与前端 `LEVEL_COLORS`（弹窗预览）色值一致；存储函数签名 `save_four_color_temp(enterprise_id, floor_id, data, content_type)` 在测试与路由中一致；`four_color_temp_dir` 返回 `Path | None` 在 commit/cancel 一致使用。

**4. 已知取舍（规格批准的决策）：** 低风险识别为蓝但落库色板用系统绿 `#52c41a`，保证全系统图例一致；`FourColorImportModal` 的替换确认从"嵌套 Modal.confirm"改为"弹窗内 Checkbox"（规格 6.3 意图一致，E2E 可测）；后端集成测试采用仓库既有 AsyncMock db 模式（无真实数据库依赖）。
