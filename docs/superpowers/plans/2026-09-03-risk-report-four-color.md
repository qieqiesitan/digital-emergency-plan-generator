# 风险评估报告附四色分布图 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 风险评估报告在草稿与定稿中都展示企业风险四色分布图：全量生成时按楼层渲染 PNG 并记录到 `summary.images`；合并时在「辨识汇总」与「风险等级评估」之间插入图片行；Word 导出能渲染图片。

**架构：** 后端新增 Pillow 渲染服务（复用 `risk_mapping_service` 的 `LEVEL_COLORS/effective_color/max_risk_level`，坐标按 0-100 百分比映射到 1200×900），PNG 写入 `/app/uploads/enterprises/{eid}/four-color/` 并走既有 `/uploads` 静态服务；前端 `ReportDocument.fourColorImages` 透传，工作台在 ch2 下方展示图块。

**技术栈：** Python FastAPI + SQLAlchemy + Pillow（已装 12.3）+ 文泉驿正黑字体（容器已装）；React 19 + antd + Tiptap；docker 验证环境（backend 8000 / frontend 5173 / shuzihuayuan 8082）。

**执行约定：**
- 后端测试：`docker cp backend/tests/<file> emergency-plan-backend:/app/tests/<file>` 后
  `docker exec -w /app emergency-plan-backend python -m pytest tests/<file> -q`。
- 前端类型：`cd frontend && node node_modules/typescript/bin/tsc -b`；前端测试
  `docker exec emergency-plan-frontend sh -c "cd /app && npx vitest run <file>"`。
- 后端代码改动后需 `docker restart emergency-plan-backend`；前端 dist 改后需重建并同步
  宿主 `frontend/dist` 与 `shuzihuayuan:/app/dist/`。
- Commit 只 add 本功能文件；TASKS.md、.codex-custom-subagents、graph.json 与既有他人未提交文件不 add。

---

## 文件结构

- 创建 `backend/app/services/report_four_color_service.py`：渲染服务（数据装配 + Pillow 绘制 + 图片行工具）。
- 创建 `backend/tests/test_report_four_color_service.py`：纯函数 + 渲染集成测试。
- 修改 `backend/app/routers/risk_assessment.py`：generate 写 `summary.images`；merge 插入图片行；docx 图片渲染。
- 修改 `frontend/src/types/reportWorkspace.ts`：`ReportDocument.fourColorImages`。
- 修改 `frontend/src/services/reportAdapters.ts`：load 透传 `summary.images`。
- 修改 `frontend/src/components/report/ReportWorkspace.tsx`：ch2 下方图块 + batch_done 后刷新。

---

## 任务 1：四色图渲染服务（TDD）

**文件：**
- 创建：`backend/app/services/report_four_color_service.py`
- 创建：`backend/tests/test_report_four_color_service.py`

### 步骤 1：编写失败测试

`backend/tests/test_report_four_color_service.py`：

```python
import asyncio
import tempfile
from pathlib import Path

from PIL import Image

from app.services.report_four_color_service import (
    four_color_images_markdown,
    hex_to_rgba,
    insert_figure_block,
    polygon_points_to_pixels,
    render_four_color_png,
)


def test_hex_to_rgba():
    assert hex_to_rgba("#ff4d4f") == (255, 77, 79, 255)
    assert hex_to_rgba("#ff4d4f", alpha=90) == (255, 77, 79, 90)


def test_polygon_points_to_pixels():
    pts = [{"x": 0, "y": 0}, {"x": 100, "y": 100}]
    out = polygon_points_to_pixels(pts, 1200, 900)
    assert out[0] == (0, 0)
    assert out[1] == (1200, 900)


def test_four_color_images_markdown():
    md = four_color_images_markdown([
        {"floor_id": "f1", "floor_name": "默认总图",
         "url": "/uploads/enterprises/e1/four-color/f1.png"},
    ])
    assert "![默认总图 四色分布图](/uploads/enterprises/e1/four-color/f1.png)" in md


def test_insert_figure_block_between_sections():
    content = "# 企业报告\n\n## 二、危险有害因素辨识汇总\n\n汇总内容\n\n## 三、风险等级评估\n\n评估内容"
    out = insert_figure_block(content, "图块", "三、风险等级评估")
    assert out.index("图块") > out.index("二、危险有害因素辨识汇总")
    assert out.index("图块") < out.index("三、风险等级评估")


def test_insert_figure_block_idempotent():
    content = "# 标题\n\n## 三、风险等级评估\n\n内容"
    once = insert_figure_block(content, "![图](url)", "三、风险等级评估")
    twice = insert_figure_block(once, "![图](url)", "三、风险等级评估")
    assert twice == once


def test_render_four_color_png_creates_image(tmp_path):
    floor = {"name": "一层", "floor_plan_url": None}
    zones = [{
        "name": "机房",
        "effective_color": "#ff4d4f",
        "polygons": [{"label": "机房", "points": [
            {"x": 10, "y": 10}, {"x": 50, "y": 10},
            {"x": 50, "y": 50}, {"x": 10, "y": 50},
        ]}],
    }]
    points = [{"name": "配电柜", "x": 30, "y": 30}]
    out = tmp_path / "f1.png"
    render_four_color_png(floor, zones, points, str(out), font_path=None)
    assert out.exists()
    with Image.open(out) as im:
        assert im.size == (1200, 900)
```

### 步骤 2：运行测试验证失败

```bash
docker cp backend/tests/test_report_four_color_service.py emergency-plan-backend:/app/tests/test_report_four_color_service.py
docker exec -w /app emergency-plan-backend python -m pytest tests/test_report_four_color_service.py -q
```
预期：FAIL（ModuleNotFoundError: report_four_color_service）。

### 步骤 3：实现 `backend/app/services/report_four_color_service.py`

```python
"""风险评估报告四色分布图渲染服务。"""
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select

from app.models.enterprise import EnterpriseFloor
from app.models.risk_management import RiskZone, RiskObject
from app.services.risk_mapping_service import (
    LEVEL_COLORS,
    effective_color,
    max_risk_level,
    normalize_polygon,
)

logger = logging.getLogger(__name__)

CANVAS_W, CANVAS_H = 1200, 900
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def hex_to_rgba(color: str | None, alpha: int = 255) -> tuple[int, int, int, int]:
    c = (color or "#d9d9d9").lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        rgb = tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        rgb = (217, 217, 217)
    return (rgb[0], rgb[1], rgb[2], alpha)


def polygon_points_to_pixels(points: list[dict], width: int = CANVAS_W, height: int = CANVAS_H) -> list[tuple[int, int]]:
    out = []
    for p in points:
        x = max(0.0, min(100.0, float(p.get("x", 0))))
        y = max(0.0, min(100.0, float(p.get("y", 0))))
        out.append((int(x / 100 * width), int(y / 100 * height)))
    return out


def _load_font(size: int):
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return None


def render_four_color_png(floor: dict, zones: list[dict], risk_points: list[dict],
                          out_path: str, font_path: str | None = None) -> None:
    """在 1200x900 画布上绘制单层四色分布图（zones/points 坐标为 0-100 百分比）。"""
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), "#ffffff")
    # 底图（可选）
    base = floor.get("floor_plan_url")
    if base:
        try:
            # floor_plan_url 形如 /uploads/...；由调用方换算为本地绝对路径传入
            local = floor.get("_floor_plan_local")
            if local and Path(local).exists():
                bg = Image.open(local).convert("RGB")
                bg = bg.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)
                img.paste(bg, (0, 0))
        except Exception as e:
            logger.warning("four-color floor plan load failed: %s", e)
    draw = ImageDraw.Draw(img, "RGBA")
    font = _load_font(22) if font_path is None else None
    if font_path:
        try:
            font = ImageFont.truetype(font_path, 22)
        except Exception:
            font = None
    font_small = _load_font(13) if font is not None else None

    for z in zones:
        fill = hex_to_rgba(z.get("effective_color"), alpha=110)
        for poly in z.get("polygons", []):
            pts = polygon_points_to_pixels(poly.get("points", []))
            if len(pts) < 3:
                continue
            draw.polygon(pts, fill=fill, outline=hex_to_rgba(z.get("effective_color"), 255))
            if font is not None:
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                label = poly.get("label") or z.get("name", "")
                draw.text((cx - 30, cy - 12), label, fill=(30, 30, 30, 255), font=font)

    for p in risk_points:
        px = int(max(0.0, min(100.0, float(p.get("x", 50)))) / 100 * CANVAS_W)
        py = int(max(0.0, min(100.0, float(p.get("y", 50)))) / 100 * CANVAS_H)
        r = 10
        draw.ellipse((px - r, py - r, px + r, py + r), fill=(22, 119, 255, 255), outline="#ffffff")
        if font_small is not None:
            draw.text((px + 12, py - 8), p.get("name", ""), fill=(20, 20, 20, 255), font=font_small)

    # 标题与图例
    if font is not None:
        draw.text((24, 18), f"{floor.get('name', '')} 四色分布图", fill=(20, 20, 20, 255), font=font)
        legend = [("重大风险", LEVEL_COLORS.get("重大", "#ff4d4f")),
                  ("较大风险", LEVEL_COLORS.get("较大", "#fa8c16")),
                  ("一般风险", LEVEL_COLORS.get("一般", "#fadb14")),
                  ("低风险", LEVEL_COLORS.get("低", "#52c41a"))]
        ly = CANVAS_H - 48
        for label, color in legend:
            draw.rectangle((CANVAS_W - 240, ly, CANVAS_W - 220, ly + 16), fill=hex_to_rgba(color))
            draw.text((CANVAS_W - 212, ly - 2), label, fill=(20, 20, 20, 255), font=font_small)
            ly += 24

    img.save(out_path, "PNG")


def four_color_images_markdown(images: list[dict]) -> str:
    lines = []
    for im in images:
        title = f"{im.get('floor_name', '')} 四色分布图"
        lines.append(f"![{title}]({im.get('url', '')})")
    return "\n\n".join(lines)


def insert_figure_block(content: str, block: str, marker_title: str) -> str:
    """把 block 插入到 “## {marker_title}” 之前；找不到标题则追加文末；已含 block 则幂等跳过。"""
    if not block:
        return content
    if block in content:
        return content
    marker = f"## {marker_title}"
    idx = content.find(marker)
    if idx == -1:
        return content.rstrip() + "\n\n" + block + "\n"
    return content[:idx].rstrip() + "\n\n" + block + "\n\n" + content[idx:]


def _uploads_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "uploads"


async def render_enterprise_four_color_images(enterprise_id: str, db) -> list[dict]:
    """按楼层渲染四色图 PNG；无楼层/分区时返回 []。写入 uploads 并返回 url 列表。"""
    floors = (await db.execute(
        select(EnterpriseFloor)
        .where(EnterpriseFloor.enterprise_id == enterprise_id)
        .order_by(EnterpriseFloor.sort_order)
    )).scalars().all()
    if not floors:
        return []
    zones = (await db.execute(
        select(RiskZone).where(RiskZone.enterprise_id == enterprise_id)
    )).scalars().all()
    points = (await db.execute(
        select(RiskObject).where(
            RiskObject.enterprise_id == enterprise_id,
            RiskObject.is_risk_point.is_(True),
        )
    )).scalars().all()

    by_floor: dict[str, list[RiskZone]] = {}
    for z in zones:
        by_floor.setdefault(z.floor_id, []).append(z)

    base_dir = _uploads_dir() / "enterprises" / enterprise_id / "four-color"
    base_dir.mkdir(parents=True, exist_ok=True)
    images: list[dict] = []
    for floor in floors:
        fzones = by_floor.get(floor.id, [])
        if not fzones:
            continue
        zdata = []
        for z in fzones:
            level = max_risk_level(z)
            color = effective_color(z.floor_plan_polygon, level)
            polygon = normalize_polygon(z.floor_plan_polygon, z.name)
            zdata.append({
                "name": z.name,
                "effective_color": color,
                "polygons": (polygon or {}).get("polygons", []),
            })
        pdata = [
            {"name": p.name, "x": p.location_x, "y": p.location_y}
            for p in points if p.floor_id == floor.id
        ]
        out = base_dir / f"{floor.id}.png"
        try:
            render_four_color_png(
                {"name": floor.name, "floor_plan_url": floor.floor_plan_url,
                 "_floor_plan_local": _resolve_floor_plan_local(floor.floor_plan_url)},
                zdata, pdata, str(out),
            )
        except Exception as e:
            logger.error("four-color render failed floor=%s: %s", floor.id, e)
            continue
        images.append({
            "floor_id": floor.id,
            "floor_name": floor.name,
            "url": f"/uploads/enterprises/{enterprise_id}/four-color/{floor.id}.png",
        })
    return images


def _resolve_floor_plan_local(url: str | None):
    if not url or not url.startswith("/uploads/"):
        return None
    return str(_uploads_dir() / url[len("/uploads/"):])
```

### 步骤 4：运行测试验证通过

```bash
docker exec -w /app emergency-plan-backend python -m pytest tests/test_report_four_color_service.py -q
```
预期：6 passed。

### 步骤 5：Commit

```bash
git add backend/app/services/report_four_color_service.py backend/tests/test_report_four_color_service.py
git commit -m "feat(report): four-color figure render service for risk assessment"
```

---

## 任务 2：risk_assessment generate/merge/docx 接线

**文件：**
- 修改：`backend/app/routers/risk_assessment.py`

### 步骤 1：全量 generate 写 summary.images

在 generate 的草稿保存块（`async with async_session() as bg_db:` 内、`await bg_db.commit()` 前）追加：

```python
try:
    from app.services.report_four_color_service import render_enterprise_four_color_images
    bg_report.summary["images"] = await render_enterprise_four_color_images(enterprise_id, bg_db)
except Exception:
    logger.exception("four-color images render failed")
```

（`bg_report.summary` 已是 dict，含 `chapters`，直接加键即可。）

### 步骤 2：merge 在 ch2/ch3 之间插入图片行

`merge_risk_assessment` 中 `merged = _clean_for_docx(merged)` 之后、`report.content = merged` 之前追加：

```python
try:
    from app.services.report_four_color_service import (
        four_color_images_markdown,
        insert_figure_block,
    )
    images = (report.summary or {}).get("images") or []
    block = four_color_images_markdown(images)
    merged = insert_figure_block(merged, block, "三、风险等级评估")
except Exception:
    logger.exception("four-color figure inject failed")
```

### 步骤 3：docx 导出渲染图片行

`_render_content_to_docx` 的逐行循环中，在 `elif line.startswith("# ")` 分支之前增加图片行分支：

```python
                import re as _re
                img_m = _re.match(r"^!\[([^\]]*)\]\((uploads|/uploads/[^)]+)\)\s*$", line)
                if img_m:
                    url = img_m.group(2)
                    local = None
                    if url.startswith("/uploads/"):
                        from pathlib import Path
                        local = str(Path(__file__).resolve().parents[2] / "uploads" / url[len("/uploads/"):])
                    elif url.startswith("uploads/"):
                        from pathlib import Path
                        local = str(Path(__file__).resolve().parents[2] / url)
                    if local and Path(local).exists():
                        try:
                            from docx.shared import Inches
                            para = doc.add_paragraph()
                            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                            run = para.add_run()
                            run.add_picture(local, width=Inches(6.3))
                            if img_m.group(1):
                                cap = doc.add_paragraph(img_m.group(1))
                                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        except Exception as e:
                            logger.warning("docx image insert failed: %s", e)
                    continue
```

注意：`_render_content_to_docx` 顶部已 `content = _clean_for_docx(content)`；确认 `_clean_for_docx` 不清除 `![..](..)` 行（其规则只处理代码块/json/星号/井号/重复行，图片行不受影响）。

### 步骤 4：回归验证

```bash
docker exec -w /app emergency-plan-backend python -c "import app.routers.risk_assessment; print('ok')"
docker exec -w /app emergency-plan-backend python -m pytest tests/test_report_four_color_service.py tests/test_report_docx_clean.py -q
```
预期：import ok，两文件全绿。

### 步骤 5：Commit

```bash
git add backend/app/routers/risk_assessment.py
git commit -m "feat(report): persist and render four-color figures in risk report"
```

---

## 任务 3：前端透传与图块展示

**文件：**
- 修改：`frontend/src/types/reportWorkspace.ts`
- 修改：`frontend/src/services/reportAdapters.ts`
- 修改：`frontend/src/components/report/ReportWorkspace.tsx`

### 步骤 1：类型与 adapter

`types/reportWorkspace.ts` 的 `ReportDocument` 增加：

```ts
  fourColorImages?: Array<{ floor_id: string; floor_name: string; url: string }>;
```

`reportAdapters.ts` load 返回值增加：

```ts
        fourColorImages: (doc.summary as { images?: Array<{ floor_id: string; floor_name: string; url: string }> })?.images ?? [],
```

### 步骤 2：工作台图块

在 `ReportWorkspace.tsx`：

1. 找到“编辑器下方”的渲染区（当前选中章节内容区之后），新增只读图块（仅
   `kind === "risk" && currentChapter?.key === "ch2_summary" && doc?.fourColorImages?.length` 时渲染）：

```tsx
{kind === "risk" && currentChapter?.key === "ch2_summary" && (doc?.fourColorImages?.length ?? 0) > 0 && (
  <div style={{ marginTop: 16 }}>
    <div style={{ fontWeight: 600, marginBottom: 8 }}>四色分布图</div>
    {doc!.fourColorImages!.map((im) => (
      <Card key={im.floor_id} size="small" style={{ marginBottom: 12 }}
            title={`${im.floor_name} 四色分布图`}>
        <img src={im.url} alt={im.floor_name} style={{ maxWidth: "100%" }} />
      </Card>
    ))}
  </div>
)}
```

2. 全量生成 `batch_done` 成功后（现有分支内）追加 `await loadReport()`（若该函数已
   在 batch_done 分支被调用则无需新增），确保 images 刷新。

### 步骤 3：验证

```bash
cd frontend && node node_modules/typescript/bin/tsc -b
docker exec emergency-plan-frontend sh -c "cd /app && npx vitest run"
```
预期：tsc exit 0，全量测试通过（基线 29 文件 180 passed + 无新增前端测试则持平）。

### 步骤 4：Commit

```bash
git add frontend/src/types/reportWorkspace.ts frontend/src/services/reportAdapters.ts frontend/src/components/report/ReportWorkspace.tsx
git commit -m "feat(report): show four-color figures under risk summary chapter in workspace"
```

---

## 任务 4：端到端验证与部署（主控执行）

- [ ] **步骤 1**：后端真实数据渲染验证（不调 LLM、不写正式 uploads）：

```bash
docker exec -w /app emergency-plan-backend python -c "
import asyncio, tempfile, os
from pathlib import Path
from app.database import async_session
from app.services.report_four_color_service import render_four_color_png

async def main():
    # 临时目录渲染：读真实企业楼层/分区数据，验证输出 PNG 尺寸与文件存在
    from sqlalchemy import select
    from app.models.enterprise import EnterpriseFloor
    from app.models.risk_management import RiskZone, RiskObject
    from app.services.risk_mapping_service import normalize_polygon, effective_color, max_risk_level
    eid = '94804158-cc33-464d-9aef-025ec90226be'
    tmp = Path(tempfile.mkdtemp())
    async with async_session() as db:
        floors = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.enterprise_id==eid))).scalars().all()
        zones = (await db.execute(select(RiskZone).where(RiskZone.enterprise_id==eid))).scalars().all()
        points = (await db.execute(select(RiskObject).where(RiskObject.enterprise_id==eid, RiskObject.is_risk_point.is_(True)))).scalars().all()
        print('floors', len(floors), 'zones', len(zones), 'points', len(points))
        for f in floors[:1]:
            zdata=[]
            for z in [z for z in zones if z.floor_id==f.id]:
                poly = normalize_polygon(z.floor_plan_polygon, z.name)
                zdata.append({'name': z.name, 'effective_color': effective_color(z.floor_plan_polygon, max_risk_level(z)), 'polygons': (poly or {}).get('polygons', [])})
            pdata=[{'name': p.name, 'x': p.location_x, 'y': p.location_y} for p in points if p.floor_id==f.id]
            out = tmp / (f.id + '.png')
            render_four_color_png({'name': f.name}, zdata, pdata, str(out))
            print(out, out.exists(), out.stat().st_size if out.exists() else 0)
asyncio.run(main())
"
```

预期：floors/zones/points 计数 >0，PNG 生成且尺寸 1200×900（可在脚本中加 PIL 校验）。

- [ ] **步骤 2**：`docker restart emergency-plan-backend`；健康检查 200。
- [ ] **步骤 3**：重建前端并同步：

```bash
docker exec emergency-plan-frontend sh -c "cd /app && npm run build"
docker cp "emergency-plan-frontend:/app/dist/." "C:\Users\55061\Documents\数字化预案自动生成 2\frontend\dist\"
docker cp "C:\Users\55061\Documents\数字化预案自动生成 2\frontend\dist\." "shuzihuayuan:/app/dist/"
```

- [ ] **步骤 4**：手工验收（请用户执行）：重新生成风险评估报告 → 草稿「辨识汇总」下方出现图；合并 → 预览含图；导出 Word 含图；无图企业不报错。
- [ ] **步骤 5**：更新 TASKS.md 快照并汇报。

---

## 自检结果

- 规格覆盖：渲染规格 → 任务 1；generate/merge/docx → 任务 2；前端草稿展示 → 任务 3；
  测试与手工验收 → 任务 1/4。
- 占位符：无 TODO；每步含可执行代码或精确命令。
- 类型一致性：`fourColorImages` 在 types/adapter/Workspace 中使用一致；
  `summary.images` 元素 `{floor_id, floor_name, url}` 前后一致；
  复用 `risk_mapping_service.effective_color/max_risk_level/normalize_polygon/LEVEL_COLORS` 与既有
  `_clean_for_docx`、`_render_content_to_docx`。
