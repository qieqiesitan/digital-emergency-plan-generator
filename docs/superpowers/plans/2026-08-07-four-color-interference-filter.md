# 四色分布图干扰项自动剔除 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在四色图识别管线内新增纯视觉干扰过滤层（图例簇/细长线/贴边细框/极小噪点自动排除 + 大面积异常形状标记疑似），并以 RapidOCR 提供分区建议名、以零样本 CLIP 强化疑似判别；所有排除项预览可恢复，AI 辅助结果仅提示不自动删除。

**架构：** `four_color_recognizer.py` 重构为「提取组件 → classify_interference 过滤 → 构建分区」，RecognizeResult 扩展 `excluded/texts`、分区扩展 `suspected/suggested_name/ai_hint`；`vision_helpers.py` 封装 RapidOCR 与 CLIP 的延迟加载与降级；analyze 响应扩展后由预览弹窗展示排除列表/建议名/提示。commit 契约不变。

**技术栈：** Python 3.12 + OpenCV + `rapidocr_onnxruntime` + `onnxruntime`（已有，chromadb 依赖）+ React 19 + antd 6；测试沿用既有纯函数/mock 模式。

**规格：** `docs/superpowers/specs/2026-08-07-four-color-interference-filter-design.md`（commit 5ccb962 + c8147e3）

**执行说明：**
- 主检出 `backend/.venv` 当前不可用（缺 pip/numpy，疑另一会话重建导致）——任务 0 负责重建并安装依赖；此后所有后端测试在本地 venv 运行（`backend/.venv/Scripts/python.exe -m pytest ...`，沿用 `--ignore tests/test_autofill_research.py --ignore _docker_test.py`）。
- CLIP 资产（ONNX 视觉编码器 + 提示词 embedding）存在构建期获取风险；任务 5 提供准备脚本与明确的降级路径，失败不阻塞其余功能。
- 提交风格：Conventional Commits；只提交任务相关文件；`TASKS.md`、`chroma.sqlite3` 等无关改动不随任务提交。

---

## 文件结构

后端（新增/修改）：
- `backend/app/services/four_color_recognizer.py`（修改）：过滤层纯函数 + 管线重构 + RecognizeResult 扩展。
- `backend/app/services/vision_helpers.py`（新增）：RapidOCR 与 CLIP 的延迟加载/推理/降级封装。
- `backend/app/schemas/risk_management.py`（修改）：excluded/texts/suspected/suggested_name/ai_hint。
- `backend/requirements.txt`（修改）：`rapidocr_onnxruntime`。
- `scripts/prepare_clip_assets.py`（新增）：构建期 CLIP 资产准备（失败降级）。
- `backend/tests/test_four_color_recognizer.py`（修改）：过滤层 + 辅助接线用例。
- `backend/tests/test_four_color_import_api.py`（修改）：schema 用例。
- `backend/tests/test_vision_helpers.py`（新增）：OCR/CLIP 封装降级与 mock 推理。

前端（新增/修改）：
- `frontend/src/types/riskMappingWorkbench.ts`（修改）：FourColorExcludedItem/FourColorTextItem 等。
- `frontend/src/components/enterprise/riskMapping/FourColorImportModal.tsx`（修改）：排除列表/恢复/疑似 Tag/建议名预填/文字叠显。
- `frontend/src/services/riskMappingWorkbenchService.test.ts`（修改）：analyze mock 扩展。
- `frontend/e2e/four-color-import.spec.ts`（修改）：新增干扰排除/OCR/CLIP 提示用例。

## 命令约定

- 后端单测：`backend/.venv/Scripts/python.exe -m pytest backend/tests/<file>.py -q`
- 后端全量：`cd backend; .venv\Scripts\python.exe -m pytest -q --ignore tests/test_autofill_research.py --ignore _docker_test.py`
- 前端：`cd frontend; npx tsc -b` / `npx vitest run` / `npx playwright test e2e/four-color-import.spec.ts`
- Python 基座（重建 venv 用）：`C:\Users\55061\AppData\Local\Programs\Python\Python312\python.exe`

---

### 任务 0：依赖与测试环境

**文件：**
- 修改：`backend/requirements.txt`

- [ ] **步骤 1：追加依赖**

在 `backend/requirements.txt` 末尾追加：

```text
rapidocr_onnxruntime>=1.3.0
```

- [ ] **步骤 2：重建 venv 并安装依赖**

运行（清华镜像，与既有约定一致）：

```powershell
C:\Users\55061\AppData\Local\Programs\Python\Python312\python.exe -m venv --clear backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

预期：pip 安装完成（含 opencv、rapidocr_onnxruntime、chromadb 等），无失败。

- [ ] **步骤 3：验证导入**

运行：`backend\.venv\Scripts\python.exe -c "import cv2, numpy, rapidocr_onnxruntime; print(cv2.__version__, numpy.__version__, 'rapidocr-ok')"`
预期：输出版本号与 `rapidocr-ok`。

- [ ] **步骤 4：Commit**

```powershell
git add backend/requirements.txt
git commit -m "build(risk-mapping): add rapidocr for four-color map text extraction"
```

### 任务 1：过滤层数据结构与图例簇检测

**文件：**
- 修改：`backend/app/services/four_color_recognizer.py`
- 测试：`backend/tests/test_four_color_recognizer.py`（追加）

- [ ] **步骤 1：追加失败测试**

在 `backend/tests/test_four_color_recognizer.py` 末尾追加（并更新 import，加入 `ComponentInfo, detect_legend_clusters`）：

```python
def _comp(color, x0, y0, x1, y1, area=None):
    return ComponentInfo(
        color=color,
        points=np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float32),
        area=float(area or (x1 - x0) * (y1 - y0)),
        bbox=(x0, y0, x1, y1),
    )


def test_detect_legend_clusters_marks_three_color_cluster():
    # 1200x900 图中紧邻的四个小色块（图例），面积均落在 0.02%-2% 区间
    comps = [
        _comp("红", 1000, 50, 1030, 80, area=900),
        _comp("橙", 1040, 50, 1070, 80, area=900),
        _comp("黄", 1000, 90, 1030, 120, area=900),
        _comp("蓝", 1040, 90, 1070, 120, area=900),
    ]
    excluded = detect_legend_clusters(comps, 1200, 900)
    assert excluded == {0, 1, 2, 3}


def test_detect_legend_clusters_ignores_isolated_zone():
    # 大分区（面积超上限）不参与图例簇
    comps = [
        _comp("红", 80, 80, 700, 500, area=620 * 420),
        _comp("蓝", 750, 80, 1120, 500, area=370 * 420),
    ]
    excluded = detect_legend_clusters(comps, 1200, 900)
    assert excluded == set()


def test_detect_legend_clusters_requires_three_colors():
    # 只有两种颜色的小色块簇不是图例
    comps = [
        _comp("红", 1000, 50, 1030, 80, area=900),
        _comp("橙", 1040, 50, 1070, 80, area=900),
    ]
    excluded = detect_legend_clusters(comps, 1200, 900)
    assert excluded == set()
```

- [ ] **步骤 2：运行测试确认失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_four_color_recognizer.py -q`
预期：FAIL，`ImportError: cannot import name 'ComponentInfo'`

- [ ] **步骤 3：实现代码**

在 `four_color_recognizer.py` 的常量区追加：

```python
LEGEND_MIN_COLORS = 3
LEGEND_MIN_AREA_RATIO = 2e-4
LEGEND_MAX_AREA_RATIO = 0.02
LEGEND_MAX_SIZE_RATIO = 3.0
LEGEND_PROXIMITY_RATIO = 0.08
THIN_ASPECT_RATIO = 12.0
BORDER_FRAME_THICKNESS_RATIO = 0.01
SUSPECT_AREA_RATIO = 0.05
SUSPECT_SOLIDITY = 0.5
```

在 `normalize_points` 之后追加：

```python
@dataclass(eq=False)
class ComponentInfo:
    color: str
    points: np.ndarray
    area: float
    bbox: tuple[int, int, int, int]


def _bbox_gap(a: ComponentInfo, b: ComponentInfo) -> float:
    ax0, ay0, ax1, ay1 = a.bbox
    bx0, by0, bx1, by1 = b.bbox
    gap_x = max(0, bx0 - ax1, ax0 - bx1)
    gap_y = max(0, by0 - ay1, ay0 - by1)
    return float(max(gap_x, gap_y))


def detect_legend_clusters(components: list[ComponentInfo], width: int, height: int) -> set[int]:
    """并查集聚类"紧邻、尺寸相近、≥3 色"的小色块，返回应排除的索引集合。"""
    min_area = LEGEND_MIN_AREA_RATIO * width * height
    max_area = LEGEND_MAX_AREA_RATIO * width * height
    cands = [i for i, c in enumerate(components) if min_area <= c.area <= max_area]
    prox = LEGEND_PROXIMITY_RATIO * min(width, height)
    parent = list(range(len(components)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in cands:
        for j in cands:
            if i >= j:
                continue
            ci, cj = components[i], components[j]
            if ci.color == cj.color:
                continue
            area_ratio = max(ci.area, cj.area) / max(1.0, min(ci.area, cj.area))
            if area_ratio > LEGEND_MAX_SIZE_RATIO:
                continue
            if _bbox_gap(ci, cj) > prox:
                continue
            union(i, j)

    clusters: dict[int, list[int]] = {}
    for i in cands:
        clusters.setdefault(find(i), []).append(i)
    excluded: set[int] = set()
    for members in clusters.values():
        colors = {components[i].color for i in members}
        if len(colors) >= LEGEND_MIN_COLORS:
            excluded.update(members)
    return excluded
```

（`dataclass` 已从 `dataclasses` 导入——把现有 import 行改为 `from dataclasses import dataclass, field`。）

- [ ] **步骤 4：运行测试确认通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_four_color_recognizer.py -q`
预期：18 passed（15 既有 + 3 新增）

- [ ] **步骤 5：Commit**

```powershell
git add backend/app/services/four_color_recognizer.py backend/tests/test_four_color_recognizer.py
git commit -m "feat(risk-mapping): legend cluster detection for interference filter"
```

### 任务 2：过滤规则汇总 classify_interference

**文件：**
- 修改：`backend/app/services/four_color_recognizer.py`
- 测试：`backend/tests/test_four_color_recognizer.py`（追加）

- [ ] **步骤 1：追加失败测试**

在 `backend/tests/test_four_color_recognizer.py` 末尾追加（并更新 import，加入 `InterferenceResult, classify_interference`）：

```python
def test_classify_interference_marks_tiny_thin_and_border_frame():
    comps = [
        _comp("红", 0, 0, 30, 30, area=900),                      # 极小噪点：900 < 5e-5*1200*900=54
        _comp("红", 500, 100, 510, 900, area=8000),               # 细长：810/10=81 > 12
        _comp("蓝", 0, 400, 1199, 410, area=1199 * 10),           # 贴边细框
        _comp("黄", 200, 200, 600, 600, area=160000),             # 正常分区
    ]
    result = classify_interference(comps, 1200, 900)
    reasons = {r for _, r in result.excluded}
    assert reasons == {"tiny", "thin", "border_frame"}
    assert len(result.kept) == 1
    assert result.kept[0].bbox == (200, 200, 600, 600)


def test_classify_interference_marks_suspected_odd_shape():
    # 面积 >5% 画面且实心度 <0.5 的凹形大块 → suspected
    points = np.array([[100, 100], [500, 100], [500, 500], [300, 250], [100, 500]], dtype=np.float32)
    area = cv2.contourArea(points)  # 凹多边形面积显著小于 bbox
    comp = ComponentInfo(color="红", points=points, area=float(area), bbox=(100, 100, 500, 500))
    result = classify_interference([comp], 800, 800)
    assert result.kept == []
    assert len(result.suspected) == 1
    assert result.excluded == []


def test_classify_interference_keeps_normal_zones():
    comps = [
        _comp("红", 80, 80, 700, 500, area=620 * 420),
        _comp("蓝", 750, 80, 1120, 500, area=370 * 420),
    ]
    result = classify_interference(comps, 1200, 900)
    assert len(result.kept) == 2
    assert result.excluded == []
    assert result.suspected == []
```

- [ ] **步骤 2：运行测试确认失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_four_color_recognizer.py -q`
预期：FAIL，`ImportError: cannot import name 'InterferenceResult'`

- [ ] **步骤 3：实现代码**

在 `four_color_recognizer.py` 的 `detect_legend_clusters` 之后追加：

```python
@dataclass
class InterferenceResult:
    kept: list[ComponentInfo]
    excluded: list[tuple[ComponentInfo, str]]
    suspected: list[ComponentInfo]


def classify_interference(components: list[ComponentInfo], width: int, height: int) -> InterferenceResult:
    """按保守优先级过滤：图例簇 → 极小噪点 → 细长线 → 贴边细框 → 疑似标记。"""
    legend_idx = detect_legend_clusters(components, width, height)
    tiny_area = MIN_AREA_RATIO * width * height
    border_w = BORDER_FRAME_THICKNESS_RATIO * min(width, height)
    long_axis = 0.3 * max(width, height)
    suspect_area = SUSPECT_AREA_RATIO * width * height
    kept: list[ComponentInfo] = []
    excluded: list[tuple[ComponentInfo, str]] = []
    suspected: list[ComponentInfo] = []
    for i, c in enumerate(components):
        if i in legend_idx:
            excluded.append((c, "legend"))
            continue
        w_c = c.bbox[2] - c.bbox[0]
        h_c = c.bbox[3] - c.bbox[1]
        if c.area < tiny_area:
            excluded.append((c, "tiny"))
            continue
        short = max(1.0, float(min(w_c, h_c)))
        long = float(max(w_c, h_c))
        if long / short > THIN_ASPECT_RATIO:
            excluded.append((c, "thin"))
            continue
        touches_border = c.bbox[0] <= 1 or c.bbox[1] <= 1 or c.bbox[2] >= width - 2 or c.bbox[3] >= height - 2
        if touches_border and short < border_w and long > long_axis:
            excluded.append((c, "border_frame"))
            continue
        solidity = c.area / max(1.0, float(w_c * h_c))
        if c.area > suspect_area and solidity < SUSPECT_SOLIDITY:
            suspected.append(c)
        else:
            kept.append(c)
    return InterferenceResult(kept=kept, excluded=excluded, suspected=suspected)
```

- [ ] **步骤 4：运行测试确认通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_four_color_recognizer.py -q`
预期：21 passed

- [ ] **步骤 5：Commit**

```powershell
git add backend/app/services/four_color_recognizer.py backend/tests/test_four_color_recognizer.py
git commit -m "feat(risk-mapping): interference classification rules"
```

### 任务 3：识别器管线集成（excluded + suspected）

**文件：**
- 修改：`backend/app/services/four_color_recognizer.py`
- 测试：`backend/tests/test_four_color_recognizer.py`（追加）

- [ ] **步骤 1：追加失败测试**

在 `backend/tests/test_four_color_recognizer.py` 末尾追加：

```python
def _legend_map():
    """1200x900：四个分区 + 右上角四色图例（紧邻小色块）。"""
    img = Image.new("RGB", (1200, 900), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([80, 80, 700, 500], fill=(255, 0, 0))
    d.rectangle([750, 80, 1120, 500], fill=(0, 0, 255))
    d.rectangle([80, 560, 700, 840], fill=(255, 127, 0))
    d.rectangle([750, 560, 1120, 840], fill=(255, 255, 0))
    d.rectangle([1000, 40, 1030, 70], fill=(255, 0, 0))
    d.rectangle([1040, 40, 1070, 70], fill=(255, 127, 0))
    d.rectangle([1000, 80, 1030, 110], fill=(255, 255, 0))
    d.rectangle([1040, 80, 1070, 110], fill=(0, 0, 255))
    return img


def test_recognize_excludes_legend_and_keeps_zones():
    result = recognize_from_bytes(_png_bytes(_legend_map()))
    assert (result.width, result.height) == (1200, 900)
    assert len(result.zones) == 4
    reasons = {e["reason"] for e in result.excluded}
    assert reasons == {"legend"}
    assert len(result.excluded) == 4


def test_recognize_marks_suspected_odd_shape():
    img = Image.new("RGB", (800, 800), "white")
    d = ImageDraw.Draw(img)
    d.polygon([(100, 100), (500, 100), (500, 500), (300, 250), (100, 500)], fill=(255, 0, 0))
    result = recognize_from_bytes(_png_bytes(img))
    assert any(z.get("suspected") for z in result.zones)


def test_recognize_clean_map_has_no_excluded():
    result = recognize_from_bytes(_png_bytes(_clean_map_with_dominant_rect()))
    assert result.excluded == []
    assert all(not z.get("suspected") for z in result.zones)
```

- [ ] **步骤 2：运行测试确认失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_four_color_recognizer.py -q`
预期：FAIL（`RecognizeResult` 尚无 `excluded` 属性 / zones 无 `suspected`）

- [ ] **步骤 3：实现代码**

把 `RecognizeResult` 与 `recognize_from_bytes` 按如下重构（替换原定义）：

```python
@dataclass
class RecognizeResult:
    zones: list[dict]
    warnings: list[str]
    width: int
    height: int
    excluded: list[dict] = field(default_factory=list)
    texts: list[dict] = field(default_factory=list)
```

```python
def recognize_from_bytes(data: bytes, ocr=None, clip=None) -> RecognizeResult:
    """识别管线入口：解码 → 透视校正（保守门控）→ 分类 → 清理 → 轮廓 → 干扰过滤 → 分区。"""
    _require_cv2()
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
    components: list[ComponentInfo] = []
    for name in ("红", "橙", "黄", "蓝"):
        mask = clean_mask(masks[name], kernel_size)
        polys = mask_to_polygons(mask, width, height, min_area, epsilon)
        for poly in polys:
            xs = poly[:, 0]
            ys = poly[:, 1]
            components.append(ComponentInfo(
                color=name,
                points=poly,
                area=float(cv2.contourArea(poly.astype(np.float32))),
                bbox=(int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())),
            ))
    filtered = classify_interference(components, width, height)
    kept_ids = {id(c) for c in filtered.kept}
    suspected_ids = {id(c) for c in filtered.suspected}
    zones: list[dict] = []
    seq = 0
    for c in components:
        if id(c) not in kept_ids and id(c) not in suspected_ids:
            continue
        if len(zones) >= MAX_ZONES:
            if not warnings:
                warnings.append("识别区域过多，已保留前 200 个")
            break
        seq += 1
        zones.append({
            "client_id": f"draft-{uuid4().hex}",
            "name": f"分区{seq}",
            "risk_level": LEVEL_BY_COLOR[c.color],
            "color": COLOR_HEX_BY_LEVEL[LEVEL_BY_COLOR[c.color]],
            "suspected": id(c) in suspected_ids,
            "polygons": [{
                "id": f"poly-{uuid4().hex}",
                "label": None,
                "points": normalize_points(c.points, width, height),
            }],
        })
    excluded_items = [{
        "color": c.color,
        "reason": reason,
        "polygons": [{
            "id": f"poly-{uuid4().hex}",
            "label": None,
            "points": normalize_points(c.points, width, height),
        }],
    } for c, reason in filtered.excluded]
    return RecognizeResult(
        zones=zones,
        warnings=warnings,
        width=width,
        height=height,
        excluded=excluded_items,
    )
```

注意：`ocr`/`clip` 参数本任务暂不使用（任务 6 接入），先保留签名。

- [ ] **步骤 4：运行测试确认通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_four_color_recognizer.py -q`
预期：24 passed

- [ ] **步骤 5：Commit**

```powershell
git add backend/app/services/four_color_recognizer.py backend/tests/test_four_color_recognizer.py
git commit -m "feat(risk-mapping): integrate interference filter into recognize pipeline"
```

### 任务 4：vision_helpers——RapidOCR 封装

**文件：**
- 创建：`backend/app/services/vision_helpers.py`
- 创建：`backend/tests/test_vision_helpers.py`

- [ ] **步骤 1：编写失败测试**

创建 `backend/tests/test_vision_helpers.py`：

```python
"""vision_helpers 单测：OCR/CLIP 降级与 mock 推理。"""
import numpy as np

import app.services.vision_helpers as vh


def test_extract_texts_degrades_without_model(monkeypatch):
    monkeypatch.setattr(vh, "_ocr", False)
    assert vh.extract_texts(np.zeros((100, 100, 3), dtype=np.uint8)) == []


def test_extract_texts_parses_ocr_output(monkeypatch):
    class FakeEngine:
        def __call__(self, img):
            return ([[[[10, 20], [90, 20], [90, 40], [10, 40]], "ZONE", 0.98]], None)

    monkeypatch.setattr(vh, "_ocr", FakeEngine())
    texts = vh.extract_texts(np.zeros((200, 200, 3), dtype=np.uint8))
    assert texts[0]["text"] == "ZONE"
    assert texts[0]["confidence"] == 0.98
    assert len(texts[0]["points"]) == 4


def test_extract_texts_returns_empty_on_engine_error(monkeypatch):
    class BrokenEngine:
        def __call__(self, img):
            raise RuntimeError("boom")

    monkeypatch.setattr(vh, "_ocr", BrokenEngine())
    assert vh.extract_texts(np.zeros((100, 100, 3), dtype=np.uint8)) == []
```

- [ ] **步骤 2：运行测试确认失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_vision_helpers.py -q`
预期：FAIL，`ModuleNotFoundError: No module named 'app.services.vision_helpers'`

- [ ] **步骤 3：实现代码**

创建 `backend/app/services/vision_helpers.py`：

```python
"""四色图识别视觉辅助：RapidOCR 文字提取（延迟加载 + 降级）。"""
from __future__ import annotations

import numpy as np

_ocr = None


def load_ocr():
    """延迟加载 RapidOCR；失败返回 None（调用方降级为空结果）。"""
    global _ocr
    if _ocr is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _ocr = RapidOCR()
        except Exception:
            _ocr = False
    return _ocr or None


def extract_texts(bgr_image: np.ndarray) -> list[dict]:
    """对 BGR 图像执行 OCR，返回 [{points: [{x,y}*4], text, confidence}]；模型缺失/异常返回空列表。"""
    engine = load_ocr()
    if engine is None:
        return []
    try:
        result, _ = engine(bgr_image)
    except Exception:
        return []
    texts: list[dict] = []
    for item in result or []:
        box, text, score = item[0], item[1], item[2]
        texts.append({
            "points": [{"x": float(p[0]), "y": float(p[1])} for p in box],
            "text": str(text),
            "confidence": float(score),
        })
    return texts
```

- [ ] **步骤 4：运行测试确认通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_vision_helpers.py -q`
预期：3 passed

- [ ] **步骤 5：Commit**

```powershell
git add backend/app/services/vision_helpers.py backend/tests/test_vision_helpers.py
git commit -m "feat(risk-mapping): rapidocr text extraction helper with degradation"
```

### 任务 5：vision_helpers——零样本 CLIP 判别 + 资产准备脚本

**文件：**
- 修改：`backend/app/services/vision_helpers.py`
- 创建：`scripts/prepare_clip_assets.py`
- 测试：`backend/tests/test_vision_helpers.py`（追加）

- [ ] **步骤 1：追加失败测试**

在 `backend/tests/test_vision_helpers.py` 末尾追加：

```python
def test_classify_region_degrades_without_assets(monkeypatch):
    monkeypatch.setattr(vh, "_clip", False)
    assert vh.classify_region(np.zeros((100, 100, 3), dtype=np.uint8)) is None


def test_classify_region_returns_hint_for_non_zone(monkeypatch):
    class FakeSession:
        def run(self, _, feed):
            return [np.array([[0.0, 1.0, 0.0, 0.0]])]

    class FakePrompts:
        def __getitem__(self, key):
            if key == "labels":
                return np.array(["风险分区色块", "图标或Logo", "图例色块", "文字标签"])
            return np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=np.float32)

    monkeypatch.setattr(vh, "_clip", {"session": FakeSession(), "prompts": FakePrompts()})
    hint = vh.classify_region(np.zeros((100, 100, 3), dtype=np.uint8))
    assert hint == "疑似图标或Logo"


def test_classify_region_returns_none_for_zone(monkeypatch):
    class FakeSession:
        def run(self, _, feed):
            return [np.array([[1.0, 0.0, 0.0, 0.0]])]

    class FakePrompts:
        def __getitem__(self, key):
            if key == "labels":
                return np.array(["风险分区色块", "图标或Logo", "图例色块", "文字标签"])
            return np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=np.float32)

    monkeypatch.setattr(vh, "_clip", {"session": FakeSession(), "prompts": FakePrompts()})
    assert vh.classify_region(np.zeros((100, 100, 3), dtype=np.uint8)) is None
```

- [ ] **步骤 2：运行测试确认失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_vision_helpers.py -q`
预期：FAIL，`AttributeError: module 'app.services.vision_helpers' has no attribute 'classify_region'`

- [ ] **步骤 3：实现代码**

在 `vision_helpers.py` 末尾追加：

```python
import os
from pathlib import Path

_clip = None
CLIP_PROMPTS = ["风险分区色块", "图标或Logo", "图例色块", "文字标签"]


def _models_dir() -> Path:
    return Path(os.environ.get("FOUR_COLOR_MODELS_DIR", Path(__file__).resolve().parents[2] / "models"))


def load_clip():
    """延迟加载 CLIP 视觉编码器（ONNX）+ 预计算提示词 embedding；资产缺失返回 None。"""
    global _clip
    if _clip is None:
        try:
            import onnxruntime as ort
            vision_path = _models_dir() / "clip_vision.onnx"
            prompts_path = _models_dir() / "clip_prompts.npz"
            if not vision_path.exists() or not prompts_path.exists():
                _clip = False
            else:
                _clip = {
                    "session": ort.InferenceSession(str(vision_path), providers=["CPUExecutionProvider"]),
                    "prompts": np.load(prompts_path),
                }
        except Exception:
            _clip = False
    return _clip or None


def _preprocess_crop(crop_bgr: np.ndarray, size: int = 224) -> np.ndarray:
    import cv2
    img = cv2.resize(crop_bgr, (size, size))
    img = img.astype(np.float32) / 255.0
    mean = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
    std = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
    img = (img - mean) / std
    return img.transpose(2, 0, 1)[None, ...]


def classify_region(crop_bgr: np.ndarray, threshold: float = 0.72) -> str | None:
    """对疑似色块裁剪图做零样本分类：返回"疑似<标签>"；判定为风险分区或置信不足返回 None。"""
    clip = load_clip()
    if clip is None:
        return None
    try:
        x = _preprocess_crop(crop_bgr)
        out = clip["session"].run(None, {"pixel_values": x})[0]
        emb = out[0].astype(np.float32)
        emb = emb / (np.linalg.norm(emb) + 1e-8)
        labels = list(clip["prompts"]["labels"])
        embs = clip["prompts"]["embeddings"].astype(np.float32)
        embs = embs / (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-8)
        scores = embs @ emb
        best = int(np.argmax(scores))
        if float(scores[best]) < threshold or labels[best] == "风险分区色块":
            return None
        return f"疑似{labels[best]}"
    except Exception:
        return None
```

创建 `scripts/prepare_clip_assets.py`：

```python
"""构建期脚本：生成 CLIP 视觉编码器 ONNX 与提示词 embedding。

用法：backend/.venv/Scripts/python.exe scripts/prepare_clip_assets.py
成功：backend/models/clip_vision.onnx + clip_prompts.npz。
失败：打印原因并退出 0（运行期自动降级为纯规则，不阻塞）。
"""
import sys
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parents[1] / "backend" / "models"
PROMPTS = ["风险分区色块", "图标或Logo", "图例色块", "文字标签"]
MODEL_ID = "openai/clip-vit-base-patch32"


def main() -> int:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        import numpy as np
        import torch
        from transformers import CLIPModel, CLIPProcessor, CLIPVisionModel

        model = CLIPModel.from_pretrained(MODEL_ID)
        inputs = CLIPProcessor.from_pretrained(MODEL_ID)(text=PROMPTS, return_tensors="pt")
        with torch.no_grad():
            text_embs = model.get_text_features(**inputs).numpy()
        np.savez(MODELS_DIR / "clip_prompts.npz", labels=np.array(PROMPTS), embeddings=text_embs)

        vision = CLIPVisionModel.from_pretrained(MODEL_ID)
        vision.eval()
        dummy = torch.randn(1, 3, 224, 224)
        torch.onnx.export(
            vision,
            dummy,
            str(MODELS_DIR / "clip_vision.onnx"),
            input_names=["pixel_values"],
            output_names=["image_embeds"],
            opset_version=17,
        )
        print(f"CLIP assets ready: {MODELS_DIR / 'clip_vision.onnx'}, {MODELS_DIR / 'clip_prompts.npz'}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[prepare_clip_assets] 资产准备失败（运行期将降级为纯规则）：{exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

注意：脚本需 `torch` 与 `transformers`（仅构建期使用，不入 requirements；首次运行会从 HuggingFace 下载模型，网络慢时可跳过，直接进入降级模式）。脚本失败退出码 0 是预期行为。

- [ ] **步骤 4：运行测试确认通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_vision_helpers.py -q`
预期：6 passed

- [ ] **步骤 5：尝试准备 CLIP 资产（可选，失败不阻塞）**

运行：`backend\.venv\Scripts\python.exe scripts\prepare_clip_assets.py`
预期：输出 `CLIP assets ready: ...`（成功）或 `资产准备失败（运行期将降级为纯规则）：...`（失败，退出码 0）。无论哪种结果都继续。

- [ ] **步骤 6：Commit**

```powershell
git add backend/app/services/vision_helpers.py backend/tests/test_vision_helpers.py scripts/prepare_clip_assets.py
git commit -m "feat(risk-mapping): zero-shot clip helper with model asset preparation script"
```

### 任务 6：OCR/CLIP 接入识别管线

**文件：**
- 修改：`backend/app/services/four_color_recognizer.py`
- 测试：`backend/tests/test_four_color_recognizer.py`（追加）

- [ ] **步骤 1：追加失败测试**

在 `backend/tests/test_four_color_recognizer.py` 末尾追加：

```python
def test_recognize_uses_ocr_suggested_name():
    img = _clean_map_with_dominant_rect()
    called = []

    def fake_ocr(_img):
        called.append(1)
        return [{
            "points": [{"x": 200, "y": 100}, {"x": 300, "y": 100}, {"x": 300, "y": 120}, {"x": 200, "y": 120}],
            "text": "原料库",
            "confidence": 0.95,
        }]

    result = recognize_from_bytes(_png_bytes(img), ocr=fake_ocr, clip=lambda crop: None)
    assert called
    names = [z.get("suggested_name") for z in result.zones]
    assert "原料库" in names
    assert result.texts[0]["text"] == "原料库"


def test_recognize_uses_clip_ai_hint_on_suspected():
    img = Image.new("RGB", (800, 800), "white")
    d = ImageDraw.Draw(img)
    d.polygon([(100, 100), (500, 100), (500, 500), (300, 250), (100, 500)], fill=(255, 0, 0))
    result = recognize_from_bytes(_png_bytes(img), ocr=lambda img: [], clip=lambda crop: "疑似Logo")
    hints = [z.get("ai_hint") for z in result.zones]
    assert "疑似Logo" in hints


def test_recognize_degrades_without_ocr_clip():
    result = recognize_from_bytes(_png_bytes(_clean_map_with_dominant_rect()))
    assert result.texts == []
    assert all(not z.get("ai_hint") for z in result.zones)
```

- [ ] **步骤 2：运行测试确认失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_four_color_recognizer.py -q`
预期：FAIL（`suggested_name`/`ai_hint`/`texts` 尚未实现）

- [ ] **步骤 3：实现代码**

在 `four_color_recognizer.py` 中，`normalize_points` 之后追加两个辅助纯函数：

```python
def _point_in_polygon(px: float, py: float, points: list[dict]) -> bool:
    """射线法判断归一化点是否在多边形内（points 为 [{x,y}]）。"""
    n = len(points)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = points[i]["x"], points[i]["y"]
        xj, yj = points[j]["x"], points[j]["y"]
        if (yi > py) != (yj > py):
            x_cross = (xj - xi) * (py - yi) / (yj - yi) + xi
            if px < x_cross:
                inside = not inside
        j = i
    return inside


def _crop_from_zone(bgr: np.ndarray, zone: dict, width: int, height: int) -> np.ndarray:
    """按分区多边形 bbox 带 8% 边距裁剪 BGR 图（供 CLIP 判别）。"""
    pts = zone["polygons"][0]["points"]
    xs = [p["x"] / 100 * width for p in pts]
    ys = [p["y"] / 100 * height for p in pts]
    margin_x = int(0.08 * width)
    margin_y = int(0.08 * height)
    x0 = max(0, int(min(xs)) - margin_x)
    y0 = max(0, int(min(ys)) - margin_y)
    x1 = min(width, int(max(xs)) + margin_x)
    y1 = min(height, int(max(ys)) + margin_y)
    return bgr[y0:y1, x0:x1]
```

在 `recognize_from_bytes` 的 `return RecognizeResult(...)` 之前插入辅助逻辑，并把 return 扩展为：

```python
    if ocr is None:
        from app.services.vision_helpers import extract_texts
        ocr = extract_texts
    if clip is None:
        from app.services.vision_helpers import classify_region
        clip = classify_region
    try:
        texts: list[dict] = ocr(bgr) or []
    except Exception:
        texts = []
    for text in texts:
        pts = text.get("points") or []
        if len(pts) < 3:
            continue
        cx = sum(p["x"] for p in pts) / len(pts) / width * 100
        cy = sum(p["y"] for p in pts) / len(pts) / height * 100
        for zone in zones:
            if zone.get("suggested_name"):
                continue
            for poly in zone["polygons"]:
                if _point_in_polygon(cx, cy, poly["points"]):
                    zone["suggested_name"] = text["text"]
                    break
    for zone in zones:
        if zone.get("suspected") and not zone.get("ai_hint"):
            try:
                hint = clip(_crop_from_zone(bgr, zone, width, height))
                if hint:
                    zone["ai_hint"] = hint
            except Exception:
                pass
    return RecognizeResult(
        zones=zones,
        warnings=warnings,
        width=width,
        height=height,
        excluded=excluded_items,
        texts=texts,
    )
```

- [ ] **步骤 4：运行测试确认通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_four_color_recognizer.py -q`
预期：27 passed

- [ ] **步骤 5：Commit**

```powershell
git add backend/app/services/four_color_recognizer.py backend/tests/test_four_color_recognizer.py
git commit -m "feat(risk-mapping): wire ocr suggested names and clip hints into pipeline"
```

### 任务 7：Schema 扩展

**文件：**
- 修改：`backend/app/schemas/risk_management.py`
- 测试：`backend/tests/test_four_color_import_api.py`（追加）

- [ ] **步骤 1：追加失败测试**

在 `backend/tests/test_four_color_import_api.py` 末尾追加（并更新顶部 import，加入 `FourColorAnalyzeResponse, FourColorDraftZone, FourColorExcludedItem, FourColorTextItem`）：

```python
# ── Schema：干扰过滤扩展 ──


def test_analyze_response_accepts_excluded_and_texts():
    resp = FourColorAnalyzeResponse(
        preview_url="/uploads/x.png",
        canvas_width=1200,
        canvas_height=900,
        zones=[FourColorDraftZone(
            client_id="d1",
            name="分区1",
            risk_level="重大",
            color="#ff4d4f",
            suspected=True,
            suggested_name="原料库",
            ai_hint="疑似Logo",
            polygons=[{"id": "p1", "points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}]}],
        )],
        excluded=[FourColorExcludedItem(
            color="红",
            reason="legend",
            polygons=[{"id": "p2", "points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}]}],
        )],
        texts=[FourColorTextItem(
            points=[{"x": 1, "y": 2}, {"x": 3, "y": 2}, {"x": 3, "y": 4}, {"x": 1, "y": 4}],
            text="原料库",
            confidence=0.9,
        )],
    )
    assert resp.zones[0].suspected is True
    assert resp.zones[0].suggested_name == "原料库"
    assert resp.zones[0].ai_hint == "疑似Logo"
    assert resp.excluded[0].reason == "legend"
    assert resp.texts[0].text == "原料库"


def test_excluded_item_rejects_unknown_reason():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        FourColorExcludedItem(color="红", reason="mystery", polygons=[{"id": "p", "points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}]}])
```

- [ ] **步骤 2：运行测试确认失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_four_color_import_api.py -q`
预期：FAIL，`ImportError: cannot import name 'FourColorExcludedItem'`

- [ ] **步骤 3：实现代码**

在 `backend/app/schemas/risk_management.py` 中，把 `FourColorDraftZone` 与 `FourColorAnalyzeResponse` 替换为：

```python
class FourColorDraftZone(BaseModel):
    client_id: str
    name: str
    risk_level: Literal["重大", "较大", "一般", "低"]
    color: str
    suspected: bool = False
    suggested_name: str | None = None
    ai_hint: str | None = None
    polygons: list[FourColorDraftPolygon] = Field(min_length=1)


class FourColorExcludedItem(BaseModel):
    color: str
    reason: Literal["legend", "thin", "border_frame", "tiny"]
    polygons: list[FourColorDraftPolygon]


class FourColorTextItem(BaseModel):
    points: list[RiskPolygonPoint]
    text: str
    confidence: float


class FourColorAnalyzeResponse(BaseModel):
    preview_url: str
    canvas_width: int
    canvas_height: int
    zones: list[FourColorDraftZone]
    warnings: list[str] = []
    excluded: list[FourColorExcludedItem] = []
    texts: list[FourColorTextItem] = []
```

（其余 FourColor* schema 保持不变。）

- [ ] **步骤 4：运行测试确认通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_four_color_import_api.py -q`
预期：25 passed（23 既有 + 2 新增）

- [ ] **步骤 5：Commit**

```powershell
git add backend/app/schemas/risk_management.py backend/tests/test_four_color_import_api.py
git commit -m "feat(risk-mapping): extend schemas for excluded items, texts and hints"
```

### 任务 8：前端——类型与服务测试

**文件：**
- 修改：`frontend/src/types/riskMappingWorkbench.ts`
- 修改：`frontend/src/services/riskMappingWorkbenchService.test.ts`

- [ ] **步骤 1：追加失败测试**

在 `frontend/src/services/riskMappingWorkbenchService.test.ts` 中，把 analyze 用例的 mock data 扩展为：

```ts
const data: FourColorAnalyzeResult = {
  preview_url: "/uploads/x.png",
  canvas_width: 600,
  canvas_height: 450,
  zones: [{
    client_id: "d1",
    name: "原料库",
    risk_level: "重大",
    color: "#ff4d4f",
    suspected: true,
    suggested_name: "原料库",
    ai_hint: "疑似Logo",
    polygons: [{ id: "p1", label: null, points: [{ x: 10, y: 10 }, { x: 30, y: 10 }, { x: 30, y: 40 }] }],
  }],
  excluded: [{
    color: "红",
    reason: "legend",
    polygons: [{ id: "p2", label: null, points: [{ x: 80, y: 5 }, { x: 90, y: 5 }, { x: 90, y: 10 }] }],
  }],
  texts: [{ points: [{ x: 10, y: 10 }, { x: 30, y: 10 }, { x: 30, y: 12 }, { x: 10, y: 12 }], text: "原料库", confidence: 0.9 }],
  warnings: [],
};
```

并在断言处追加：

```ts
expect(result.excluded[0].reason).toBe("legend");
expect(result.zones[0].suggested_name).toBe("原料库");
expect(result.zones[0].ai_hint).toBe("疑似Logo");
expect(result.texts[0].text).toBe("原料库");
```

- [ ] **步骤 2：运行测试确认失败**

运行：`cd frontend; npx vitest run src/services/riskMappingWorkbenchService.test.ts`
预期：FAIL，`FourColorAnalyzeResult` 类型无 `excluded`/`texts` 属性

- [ ] **步骤 3：实现类型**

在 `frontend/src/types/riskMappingWorkbench.ts` 中修改：

```ts
export interface FourColorDraftZone {
  client_id: string;
  name: string;
  risk_level: RiskLevel;
  color: string;
  suspected?: boolean;
  suggested_name?: string | null;
  ai_hint?: string | null;
  polygons: FourColorDraftPolygon[];
}
export interface FourColorExcludedItem {
  color: string;
  reason: "legend" | "thin" | "border_frame" | "tiny";
  polygons: FourColorDraftPolygon[];
}
export interface FourColorTextItem {
  points: { x: number; y: number }[];
  text: string;
  confidence: number;
}
export interface FourColorAnalyzeResult {
  preview_url: string;
  canvas_width: number;
  canvas_height: number;
  zones: FourColorDraftZone[];
  warnings: string[];
  excluded: FourColorExcludedItem[];
  texts: FourColorTextItem[];
}
```

（`FourColorCommitPayload/Result` 等保持不变；service 函数无需改动。）

- [ ] **步骤 4：运行测试确认通过 + 类型检查**

运行：`cd frontend; npx vitest run src/services/riskMappingWorkbenchService.test.ts`
预期：3 passed

运行：`cd frontend; npx tsc -b`
预期：exit 0

- [ ] **步骤 5：Commit**

```powershell
cd frontend
git add src/types/riskMappingWorkbench.ts src/services/riskMappingWorkbenchService.test.ts
git commit -m "feat(risk-mapping): frontend types for excluded items, texts and hints"
```

### 任务 9：前端——FourColorImportModal 增强

**文件：**
- 修改：`frontend/src/components/enterprise/riskMapping/FourColorImportModal.tsx`

- [ ] **步骤 1：实现组件增强**

在 `FourColorImportModal.tsx` 中：

1. import 追加 `Collapse`，类型追加 `FourColorExcludedItem, FourColorTextItem`。
2. 组件内追加状态与常量：

```tsx
const [excluded, setExcluded] = useState<FourColorExcludedItem[]>([]);
const [texts, setTexts] = useState<FourColorTextItem[]>([]);
const [showTexts, setShowTexts] = useState(true);

const COLOR_LEVEL: Record<string, RiskLevel> = { 红: "重大", 橙: "较大", 黄: "一般", 蓝: "低" };
const REASON_LABEL: Record<string, string> = {
  legend: "图例",
  thin: "细长线/符号",
  border_frame: "贴边图框",
  tiny: "极小噪点",
};
```

3. `reset()` 增加清空：

```tsx
setExcluded([]);
setTexts([]);
setShowTexts(true);
```

4. `runAnalyze` 成功分支改为：

```tsx
const res = await analyzeFourColorMap(enterpriseId, floorId, file);
setResult(res);
setZones(res.zones.map(z => ({ ...z, name: z.suggested_name || z.name })));
setExcluded(res.excluded);
setTexts(res.texts);
setStage("preview");
```

5. 新增恢复函数：

```tsx
const handleRestore = (item: FourColorExcludedItem) => {
  const level = COLOR_LEVEL[item.color] ?? "一般";
  const newZone: FourColorDraftZone = {
    client_id: `draft-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name: `分区${zones.length + 1}`,
    risk_level: level,
    color: LEVEL_COLORS[level],
    polygons: item.polygons,
  };
  setZones([...zones, newZone]);
  setExcluded(excluded.filter(x => x !== item));
};
```

6. 预览区（`stage === "preview"`）在分区列表右侧（`texts` 叠显）与列表下方（排除折叠区）追加：

```tsx
{texts.length > 0 && (
  <Checkbox
    checked={showTexts}
    onChange={e => setShowTexts(e.target.checked)}
    style={{ position: "absolute", top: 8, right: 8, zIndex: 2, background: "rgba(255,255,255,.85)", padding: "0 6px" }}
  >
    文字标注
  </Checkbox>
)}
{showTexts && texts.map((t, i) => (
  <svg key={`text-${i}`} viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
    <polygon
      points={t.points.map(p => `${p.x / result.canvas_width * 100},${p.y / result.canvas_height * 100}`).join(" ")}
      fill="none"
      stroke="#1677ff"
      strokeWidth={1}
      strokeDasharray="3 3"
      vectorEffect="non-scaling-stroke"
    />
  </svg>
))}
```

（将这段放在原分区 SVG overlay 的容器内；文字框坐标是像素，需先按画布归一化。）

7. 分区行：`suspected` 时在 `Tag` 后追加：

```tsx
{z.suspected && (
  <Tag color="orange" title={z.ai_hint || "形状异常，可能不是真实分区"}>疑似干扰</Tag>
)}
```

8. 分区列表下方追加折叠区：

```tsx
{excluded.length > 0 && (
  <Collapse
    style={{ marginTop: 12 }}
    items={[{
      key: "excluded",
      label: `已自动排除干扰项（${excluded.length}）`,
      children: (
        <List
          size="small"
          dataSource={excluded}
          renderItem={(item, i) => (
            <List.Item
              actions={[
                <Button key="restore" type="link" onClick={() => handleRestore(item)}>恢复</Button>,
              ]}
            >
              <span style={{ color: "#999", fontSize: 12 }}>
                {i + 1}. {REASON_LABEL[item.reason]} · {item.polygons[0]?.points.length ?? 0} 个顶点
              </span>
            </List.Item>
          )}
        />
      ),
    }]}
  />
)}
```

9. `handleCommit` 的 payload 组装不变（zones 已含恢复项与建议名）。

- [ ] **步骤 2：类型检查 + 构建**

运行：`cd frontend; npx tsc -b`
预期：exit 0

运行：`cd frontend; npm run build`
预期：构建成功

- [ ] **步骤 3：Commit**

```powershell
cd frontend
git add src/components/enterprise/riskMapping/FourColorImportModal.tsx
git commit -m "feat(risk-mapping): excluded list restore, suspected tag and text overlay in import modal"
```

### 任务 10：E2E 更新

**文件：**
- 修改：`frontend/e2e/four-color-import.spec.ts`

- [ ] **步骤 1：实现测试**

在 `frontend/e2e/four-color-import.spec.ts` 中：

1. 把 `mockApis` 增加 `analyzeData` 参数（默认 `ANALYZE_DATA`），analyze 路由改为 `route.fulfill(json(200, { code: 0, message: "ok", data: analyzeData }))`。
2. 新增带 AI 增强的 mock 数据：

```ts
const ANALYZE_DATA_AI = {
  ...ANALYZE_DATA,
  zones: [
    { ...ANALYZE_DATA.zones[0], suggested_name: "原料库", suspected: true, ai_hint: "疑似Logo" },
    ...ANALYZE_DATA.zones.slice(1),
  ],
  excluded: [{
    color: "红",
    reason: "legend",
    polygons: [{ id: "e1", label: null, points: [{ x: 90, y: 2 }, { x: 99, y: 2 }, { x: 99, y: 8 }, { x: 90, y: 8 }] }],
  }],
  texts: [{ points: [{ x: 80, y: 70 }, { x: 99, y: 70 }, { x: 99, y: 74 }, { x: 80, y: 74 }], text: "原料库", confidence: 0.9 }],
};
```

3. 新增用例：

```ts
test("干扰项自动排除可恢复，疑似分区带 AI 提示，文字标注可开关", async ({ page }) => {
  await mockApis(page, [], ANALYZE_DATA_AI);
  await loginAndOpenWorkbench(page);
  await page.getByRole("button", { name: "导入四色图" }).click();
  await dialogFileInput(page).setInputFiles("e2e/fixtures/four-color-sample.png");
  await expect(dialogZoneInput(page, 1)).toHaveValue("原料库", { timeout: 10000 });
  await expect(page.getByText("疑似干扰", { exact: true })).toBeVisible();
  await expect(page.getByText("已自动排除干扰项（1）", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "恢复" }).click();
  await expect(page.getByText("已自动排除干扰项（0）", { exact: true })).toHaveCount(0);
  await expect(dialogZoneInput(page, 5)).toHaveValue("分区5");
  const textCheckbox = page.getByRole("dialog", { name: "导入四色分布图" }).getByText("文字标注", { exact: true });
  await expect(textCheckbox).toBeVisible();
  await textCheckbox.click();
  await page.getByRole("button", { name: "确认落图" }).click();
  await expect(page.getByText("四色图导入成功")).toBeVisible();
});
```

（若 `已自动排除干扰项（0）` 文案因 Collapse 关闭不可见，改用断言 `恢复` 按钮数量为 0：`await expect(page.getByRole("button", { name: "恢复" })).toHaveCount(0)`。）

- [ ] **步骤 2：运行 E2E 确认通过**

运行：`cd frontend; npx playwright test e2e/four-color-import.spec.ts`
预期：3 passed（2 既有 + 1 新增）

- [ ] **步骤 3：Commit**

```powershell
cd frontend
git add e2e/four-color-import.spec.ts
git commit -m "test(risk-mapping): interference filter and ai hints e2e"
```

### 任务 11：收尾——全量验证与文档

**文件：**
- 修改：`TASKS.md`（快照更新，不随本任务 commit）

- [ ] **步骤 1：后端全量测试**

运行：`cd backend; .venv\Scripts\python.exe -m pytest -q --ignore tests/test_autofill_research.py --ignore _docker_test.py`
预期：全部通过（既有 127 + 新增 15 = 142 passed，无 skipped/failed）

- [ ] **步骤 2：前端全量验证**

运行：`cd frontend; npx tsc -b` → exit 0

运行：`cd frontend; npx vitest run` → 全部通过

运行：`cd frontend; npx playwright test` → hermetic 套件全部通过（comprehensive.spec.ts 的环境性失败除外，与本功能无关）

- [ ] **步骤 3：仓库卫生检查**

运行：`git diff --check` → 无输出

- [ ] **步骤 4：更新 TASKS.md 快照**

记录：干扰过滤 + OCR/CLIP 辅助已实现，后端/前端/E2E 验证结果与新增文件清单。

- [ ] **步骤 5：提交计划文档**

```powershell
git add docs/superpowers/plans/2026-08-07-four-color-interference-filter.md
git commit -m "docs(risk-mapping): interference filter implementation plan"
```

---

## 计划自检（作者已执行）

**1. 规格覆盖度：** 对照规格逐章核验——过滤层四条规则（任务 1-2）、管线重构与 excluded/suspected（任务 3）、OCR 三用途（任务 4+6）、CLIP 判别与资产脚本（任务 5）、数据结构/API（任务 7）、前端排除列表/恢复/疑似 Tag/建议名/文字叠显（任务 8-9）、测试策略（各任务 TDD + E2E 任务 10）、降级策略（任务 4/5/6）、明确不做（YOLO/持久化等未建任务，符合规格）。无规格需求缺任务。

**2. 占位符扫描：** 无"待定/TODO/后续实现/补充细节"；每个代码步骤含完整代码；命令与预期输出齐全。

**3. 类型一致性：** 后端 `excluded[].reason`（legend/thin/border_frame/tiny）、`zones[].suspected/suggested_name/ai_hint`、`texts[].points/text/confidence` 与前端类型、E2E mock 三处一致；`recognize_from_bytes(data, ocr=None, clip=None)` 签名在任务 3 定义、任务 6 使用一致；`ComponentInfo`（color/points/area/bbox）在任务 1-3 一致；`classify_region` 返回"疑似<标签>"或 None 在任务 5-6 一致；CLIP 资产文件名 `clip_vision.onnx`/`clip_prompts.npz` 在脚本与加载器一致。

**4. 已知取舍：** CLIP 资产获取存在构建期不确定性（脚本失败退出码 0 即降级）；RapidOCR 依赖已入 requirements 并在任务 0 安装；venv 重建是既有环境问题的一次性修复；E2E 中"恢复后计数"断言提供替代写法（Collapse 折叠导致文案不可见时的兜底）。
