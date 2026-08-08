# 预案附图扩展 第 2 批（数据绘制服务 + 占位符 + 补图接口）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现风险矩阵图（L×S）与厂区平面疏散图的数据自动绘制服务，统一占位符结构，新增 `diagram_svgs` 存储与一键补图接口。

**架构：** 新增 `plan_diagram_service.py`（risk_matrix/evacuation/placeholder 生成器 + 补图入口）；`PlanSection` 增加 `diagram_svgs` JSONB 列（幂等迁移）；生成流程在写库前调用 `_attach_diagrams` 后处理；新增 `POST /plans/{id}/diagrams/regenerate-missing`。

**技术栈：** FastAPI + SQLAlchemy async；SVG 代码生成（无第三方绘图依赖，Playwright 转 PNG 复用现有）。

**规格：** `docs/superpowers/specs/2026-08-08-plan-diagrams-enhancement-design.md` §4、§5、§6.1、§6.2、§6.3

---

## 文件结构

**后端：**
- 新增 `backend/app/services/plan_diagram_service.py`
- 新增 `backend/db_migration_plan_diagram_svgs.sql`
- 修改 `backend/app/models/enterprise.py` — PlanSection + diagram_svgs
- 修改 `backend/app/routers/generation.py` — `_attach_diagrams` 后处理、enterprise_data 扩展
- 修改 `backend/app/routers/diagrams.py`（新增）或 `plans.py` — 补图接口
- 修改 `backend/app/services/plan_quality_service.py` — 占位 warning
- 新增 `backend/tests/test_plan_diagram_service.py`、`backend/tests/test_plan_diagrams_api.py`

---

### 任务 1：PlanSection 模型 + 迁移 SQL

**文件：**
- 修改：`backend/app/models/enterprise.py`（PlanSection）
- 新增：`backend/db_migration_plan_diagram_svgs.sql`
- 测试：`backend/tests/test_plan_diagram_service.py`

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_diagram_service.py
from app.models.enterprise import PlanSection


def test_plan_section_has_diagram_svgs_column():
    cols = {c.name for c in PlanSection.__table__.columns}
    assert "diagram_svgs" in cols


def test_diagram_svgs_default():
    s = PlanSection(id="t", plan_project_id="p", section_key="s", title="t", level=1, sort_order=0)
    assert s.diagram_svgs == {}
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/test_plan_diagram_service.py -v`
预期：FAIL，`KeyError: 'diagram_svgs'` 或列缺失

- [ ] **步骤 3：实现模型字段**

```python
# backend/app/models/enterprise.py  PlanSection 类内追加：
    diagram_svgs: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
```

- [ ] **步骤 4：新增迁移 SQL**

```sql
-- backend/db_migration_plan_diagram_svgs.sql
ALTER TABLE plan_sections
  ADD COLUMN IF NOT EXISTS diagram_svgs JSONB NOT NULL DEFAULT '{}';
```

- [ ] **步骤 5：运行测试验证通过**

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/test_plan_diagram_service.py -v`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add backend/app/models/enterprise.py backend/db_migration_plan_diagram_svgs.sql backend/tests/test_plan_diagram_service.py
git commit -m "feat(plan): add diagram_svgs column to plan sections (diagrams batch2)"
```

---

### 任务 2：plan_diagram_service 核心生成器

**文件：**
- 新增：`backend/app/services/plan_diagram_service.py`
- 测试：`backend/tests/test_plan_diagram_service.py`（追加）

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_diagram_service.py 追加
from app.services.plan_diagram_service import (
    build_risk_matrix_svg, build_evacuation_svg, make_placeholder,
)


def test_make_placeholder_structure():
    p = make_placeholder("risk_matrix", "missing_risk_events")
    assert p["placeholder"] is True
    assert p["key"] == "risk_matrix"
    assert p["reason"] == "missing_risk_events"


def test_build_risk_matrix_svg():
    events = [
        {"name": "储罐泄漏", "likelihood": 3, "severity": 4, "risk_level": "较大"},
        {"name": "电气火灾", "likelihood": 2, "severity": 3, "risk_level": "一般"},
    ]
    out = build_risk_matrix_svg(events)
    assert out["placeholder"] is False
    assert "<svg" in out["svg"]
    assert "储罐泄漏" in out["svg"]


def test_build_risk_matrix_svg_no_data():
    assert build_risk_matrix_svg([])["placeholder"] is True


def test_build_evacuation_svg_with_points():
    out = build_evacuation_svg(
        floor_plan_url=None,
        zones=[{"name": "生产区", "polygon": {"version": 2, "polygons": [
            {"points": [[10, 10], [90, 10], [90, 90], [10, 90]]}
        ]}}],
        objects=[{"name": "储罐", "location_x": 50, "location_y": 50}],
        resources=[{"name": "灭火器", "category": "消防", "location": "东墙"}],
    )
    assert out["placeholder"] is False
    assert "<svg" in out["svg"]
    assert "储罐" in out["svg"]


def test_build_evacuation_svg_no_data():
    out = build_evacuation_svg(None, [], [], [])
    assert out["placeholder"] is True
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/test_plan_diagram_service.py -v`
预期：FAIL，`ModuleNotFoundError: No module named 'app.services.plan_diagram_service'`

- [ ] **步骤 3：实现服务**

```python
# backend/app/services/plan_diagram_service.py
"""预案附图数据绘制服务：风险矩阵、平面疏散图、占位符。"""

VIEW_W, VIEW_H = 1000, 700


def make_placeholder(key: str, reason: str) -> dict:
    return {"key": key, "placeholder": True, "reason": reason}


def build_risk_matrix_svg(risk_events: list) -> dict:
    """5×5 L×S 风险矩阵热力图。risk_events: [{name, likelihood, severity, risk_level}]"""
    events = [e for e in risk_events if e.get("likelihood") and e.get("severity")]
    if not events:
        return make_placeholder("risk_matrix", "missing_risk_events")

    level_colors = {"重大": "#d4380d", "较大": "#fa8c16", "一般": "#fadb14", "低": "#91d5ff"}
    cell = 120
    origin_x, origin_y = 80, 560
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="700" viewBox="0 0 1000 700">',
             '<rect width="1000" height="700" fill="#fff"/>',
             '<text x="500" y="40" text-anchor="middle" font-size="20" font-weight="bold">风险矩阵图（可能性 L × 严重度 S）</text>']

    # 网格
    for i in range(5):
        for j in range(5):
            x = origin_x + j * cell
            y = origin_y - (i + 1) * cell
            score = (i + 1) * (j + 1)
            color = "#ffccc7" if score >= 15 else "#ffd591" if score >= 9 else "#fff1b8" if score >= 4 else "#e6f7ff"
            parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{color}" stroke="#d9d9d9"/>')

    # 轴标签
    for i in range(5):
        parts.append(f'<text x="{origin_x - 30}" y="{origin_y - i*cell - cell/2 + 5}" text-anchor="middle" font-size="14">S{i+1}</text>')
        parts.append(f'<text x="{origin_x + i*cell + cell/2}" y="{origin_y + 25}" text-anchor="middle" font-size="14">L{i+1}</text>')

    # 事件点
    for e in events:
        l = min(max(int(e["likelihood"]), 1), 5)
        s = min(max(int(e["severity"]), 1), 5)
        x = origin_x + (l - 1) * cell + cell / 2
        y = origin_y - s * cell + cell / 2
        color = level_colors.get(e.get("risk_level", ""), "#333")
        parts.append(f'<circle cx="{x}" cy="{y}" r="14" fill="{color}" opacity="0.85"/>')
        parts.append(f'<text x="{x}" y="{y + 4}" text-anchor="middle" font-size="10" fill="#fff">{e.get("name", "")}</text>')

    parts.append("</svg>")
    return {"key": "risk_matrix", "placeholder": False, "svg": "\n".join(parts)}


def _to_view(x: float, y: float) -> tuple[float, float]:
    """0-100 坐标 → 1000×700 视口（留边距）。"""
    return 60 + x / 100 * 880, 40 + y / 100 * 620


def build_evacuation_svg(floor_plan_url, zones, objects, resources) -> dict:
    """厂区平面疏散图：底图（如有）+ 分区 + 风险点 + 疏散标注。"""
    has_geometry = bool(zones) or bool(objects)
    if not has_geometry:
        return make_placeholder("evacuation", "missing_floor_data")

    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="700" viewBox="0 0 1000 700">',
             '<rect width="1000" height="700" fill="#fafafa"/>',
             '<text x="500" y="30" text-anchor="middle" font-size="18" font-weight="bold">厂区平面疏散示意图</text>']
    if floor_plan_url:
        parts.append(f'<image href="{floor_plan_url}" x="60" y="40" width="880" height="620" preserveAspectRatio="xMidYMid meet" opacity="0.35"/>')

    zone_colors = ["#ffccc7", "#ffd591", "#fff1b8", "#e6f7ff"]
    for idx, z in enumerate(zones):
        poly = z.get("polygon") or {}
        for p in poly.get("polygons", []):
            pts = p.get("points", [])
            if len(pts) < 3:
                continue
            mapped = " ".join(f"{_to_view(x, y)[0]:.1f},{_to_view(x, y)[1]:.1f}" for x, y in pts)
            color = zone_colors[idx % len(zone_colors)]
            parts.append(f'<polygon points="{mapped}" fill="{color}" stroke="#999" stroke-width="2"/>')
            cx = sum(x for x, y in pts) / len(pts)
            cy = sum(y for x, y in pts) / len(pts)
            vx, vy = _to_view(cx, cy)
            parts.append(f'<text x="{vx}" y="{vy}" text-anchor="middle" font-size="13">{z.get("name", "")}</text>')

    for o in objects:
        x, y = _to_view(o.get("location_x", 50), o.get("location_y", 50))
        parts.append(f'<circle cx="{x}" cy="{y}" r="8" fill="#d4380d"/>')
        parts.append(f'<text x="{x + 12}" y="{y + 4}" font-size="12">{o.get("name", "")}</text>')

    # 疏散集合点（右上角）与消防设施（若有）
    ex, ey = _to_view(85, 10)
    parts.append(f'<rect x="{ex-30}" y="{ey-30}" width="60" height="60" fill="#52c41a" rx="8"/>')
    parts.append(f'<text x="{ex}" y="{ey+4}" text-anchor="middle" font-size="11" fill="#fff">集合点</text>')
    for r in resources:
        if r.get("category") in ("消防", "灭火"):
            rx, ry = _to_view(10, 10)
            parts.append(f'<rect x="{rx-14}" y="{ry-14}" width="28" height="28" fill="#fa541c" rx="5"/>')
            parts.append(f'<text x="{rx}" y="{ry+4}" text-anchor="middle" font-size="9" fill="#fff">{r.get("name", "消防")}</text>')
            break

    parts.append("</svg>")
    return {"key": "evacuation", "placeholder": False, "svg": "\n".join(parts)}
```

- [ ] **步骤 4：运行测试验证通过**

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/test_plan_diagram_service.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/plan_diagram_service.py backend/tests/test_plan_diagram_service.py
git commit -m "feat(plan): add risk matrix and evacuation diagram generators (diagrams batch2)"
```

---

### 任务 3：生成流程后处理接入

**文件：**
- 修改：`backend/app/routers/generation.py`（`_attach_diagrams`、`_collect_enterprise_data` 扩展）
- 测试：`backend/tests/test_plan_diagram_service.py`（追加）

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_diagram_service.py 追加
from unittest.mock import MagicMock
from app.routers.generation import _attach_diagrams


def test_attach_diagrams_writes_risk_matrix_for_sec2():
    s = MagicMock()
    s.section_key = "sec_2"
    s.diagram_svgs = None
    ent_data = {"risk_events": [
        {"name": "火灾", "likelihood": 3, "severity": 4, "risk_level": "较大"}
    ]}
    _attach_diagrams(s, "comprehensive", ent_data)
    assert s.diagram_svgs.get("risk_matrix", {}).get("placeholder") is False


def test_attach_diagrams_placeholder_when_no_data():
    s = MagicMock()
    s.section_key = "sec_2"
    s.diagram_svgs = None
    _attach_diagrams(s, "comprehensive", {})
    assert s.diagram_svgs.get("risk_matrix", {}).get("placeholder") is True
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/test_plan_diagram_service.py -v`
预期：FAIL，`ImportError: cannot import name '_attach_diagrams'`

- [ ] **步骤 3：实现后处理函数**

```python
# backend/app/routers/generation.py  模块级新增：
def _attach_diagrams(section, plan_type: str, ent_data: dict) -> None:
    """生成后处理：按章节写入数据图（风险矩阵/疏散图）或占位符。"""
    from app.services.plan_diagram_service import (
        build_risk_matrix_svg, build_evacuation_svg, make_placeholder,
    )
    section.diagram_svgs = section.diagram_svgs or {}
    key = section.section_key

    if key == "sec_2" and plan_type == "comprehensive":
        section.diagram_svgs["risk_matrix"] = build_risk_matrix_svg(
            ent_data.get("risk_events", [])
        )
    elif key == "sec_3_3" and plan_type == "onsite":
        section.diagram_svgs["evacuation"] = build_evacuation_svg(
            floor_plan_url=ent_data.get("floor_plan_url"),
            zones=ent_data.get("zones", []),
            objects=ent_data.get("risk_objects", []),
            resources=ent_data.get("resources", []),
        )
```

- [ ] **步骤 4：enterprise_data 扩展（risk_events/zones/objects）**

`_collect_enterprise_data` 返回值增加：

```python
        "risk_events": [
            {
                "name": e.get("name", ""),
                "likelihood": e.get("likelihood"),
                "severity": e.get("severity"),
                "risk_level": e.get("risk_level", ""),
            }
            for e in risk_context.get("risk_events", [])
        ],
        "zones": [
            {"name": z.get("name", ""), "polygon": z.get("polygon")}
            for z in risk_context.get("zones", [])
        ],
        "risk_objects": [
            {
                "name": o.get("name", ""),
                "location_x": o.get("location_x"),
                "location_y": o.get("location_y"),
            }
            for o in risk_context.get("risk_objects", [])
        ],
        "floor_plan_url": ent.floor_plan_url if ent else None,
```

`build_risk_management_context` 需同步返回 `risk_events`/`zones`/`risk_objects` 展平列表（batch2 任务 3 一并改 `risk_context_builder.py`，或在本任务补一个展平函数；若改 builder 影响其他调用方，用只读展平——在 `_collect_enterprise_data` 内从五层结构展平。实现者按实际代码选择：优先扩展 `build_risk_management_context` 返回结构，保持向后兼容）。

- [ ] **步骤 5：生成流程调用点**

单章与批量生成写库前调用：

```python
            _attach_diagrams(s, plan_type, ent_data)
```

位置：`generate_section` 中 `s.content = md_to_html(...)` 之后、`await db.commit()` 之前；`_run_batch_generation` 中同一位置。

- [ ] **步骤 6：运行测试验证通过 + 全量回归**

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/test_plan_diagram_service.py tests/test_generation_enterprise_data.py -v`
预期：PASS

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/ -q --ignore=tests/test_autofill_research.py`
预期：全部通过

- [ ] **步骤 7：Commit**

```bash
git add backend/app/routers/generation.py backend/app/services/risk_context_builder.py backend/tests/test_plan_diagram_service.py
git commit -m "feat(plan): attach data-driven diagrams during generation (diagrams batch2)"
```

---

### 任务 4：补图接口 + 占位 warning

**文件：**
- 新增：`backend/app/routers/diagrams.py`
- 修改：`backend/app/services/plan_quality_service.py`
- 修改：`backend/app/main.py`（注册路由）
- 测试：`backend/tests/test_plan_diagrams_api.py`

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_diagrams_api.py
from unittest.mock import MagicMock, AsyncMock
import pytest


@pytest.mark.asyncio
async def test_regenerate_missing_diagrams_counts():
    from app.routers.diagrams import regenerate_missing_diagrams
    db = MagicMock()
    sec = MagicMock()
    sec.section_key = "sec_2"
    sec.diagram_svgs = {"risk_matrix": {"placeholder": True}}
    plan = MagicMock()
    plan.plan_type = "comprehensive"
    result = await regenerate_missing_diagrams(db, plan, [sec], {"risk_events": [
        {"name": "火灾", "likelihood": 3, "severity": 4, "risk_level": "较大"}
    ]})
    assert result["regenerated"] == 1
    assert result["placeholders_remaining"] == 0
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/test_plan_diagrams_api.py -v`
预期：FAIL，`ModuleNotFoundError: No module named 'app.routers.diagrams'`

- [ ] **步骤 3：实现路由与补图逻辑**

```python
# backend/app/routers/diagrams.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import PlanProject, PlanSection
from app.routers.generation import _attach_diagrams, _collect_enterprise_data
from app.services.risk_context_builder import build_risk_management_context

router = APIRouter(prefix="/plans", tags=["Diagrams"])


async def regenerate_missing_diagrams(db, plan, sections, ent_data) -> dict:
    regenerated = 0
    skipped = 0
    for s in sections:
        before = (s.diagram_svgs or {})
        has_placeholder = any(
            isinstance(v, dict) and v.get("placeholder") for v in before.values()
        )
        if not has_placeholder:
            continue
        _attach_diagrams(s, plan.plan_type, ent_data)
        after = s.diagram_svgs or {}
        remaining = any(
            isinstance(v, dict) and v.get("placeholder") for v in after.values()
        )
        if remaining:
            skipped += 1
        else:
            regenerated += 1
    await db.commit()
    placeholders_remaining = sum(
        1 for s in sections
        if any(isinstance(v, dict) and v.get("placeholder") for v in (s.diagram_svgs or {}).values())
    )
    return {"regenerated": regenerated, "skipped": skipped, "placeholders_remaining": placeholders_remaining}


@router.post("/{plan_id}/diagrams/regenerate-missing")
async def regenerate_missing(plan_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(
        PlanProject.id == plan_id, PlanProject.user_id == current_user.id
    ))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "预案不存在")
    sections = (await db.execute(
        select(PlanSection).where(PlanSection.plan_project_id == plan_id)
    )).scalars().all()
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()
    resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == p.enterprise_id))).scalars().all()
    risk_context = await build_risk_management_context(p.enterprise_id, db) if ent else {}
    ent_data = _collect_enterprise_data(ent, risk_context, resources) if ent else {}
    result = await regenerate_missing_diagrams(db, p, sections, ent_data)
    return {"code": 0, "data": result}
```

（导入 `Enterprise`/`EmergencyResource` 按需补充；`_collect_enterprise_data` 已含这些字段。）

- [ ] **步骤 4：注册路由 + 占位 warning**

`backend/app/main.py` 导入并 `include_router(diagrams.router, prefix="/api/v1")`。

`backend/app/services/plan_quality_service.py` 的 `check_plan` 增加规则：

```python
        # 占位附图
        for key, meta in (s.diagram_svgs or {}).items():
            if isinstance(meta, dict) and meta.get("placeholder"):
                warnings.append({
                    "section_key": s.section_key,
                    "section_title": s.title,
                    "warning": f"存在未生成的附图占位：{key}（{meta.get('reason', '')}）",
                })
```

- [ ] **步骤 5：运行测试验证通过 + 全量回归**

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/test_plan_diagrams_api.py -v`
预期：PASS

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/ -q --ignore=tests/test_autofill_research.py`
预期：全部通过

- [ ] **步骤 6：Commit**

```bash
git add backend/app/routers/diagrams.py backend/app/main.py backend/app/services/plan_quality_service.py backend/tests/test_plan_diagrams_api.py
git commit -m "feat(plan): add regenerate-missing-diagrams endpoint and placeholder warning (diagrams batch2)"
```

---

### 任务 5：第 2 批收尾验证

- [ ] **步骤 1：后端全量回归**

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/ -q --ignore=tests/test_autofill_research.py`
预期：全部通过

- [ ] **步骤 2：规格对照自检**

- [x] §4.1 自动降级 → 任务 2（各 builder 无数据返回 placeholder）
- [x] §4.3 一键补图 → 任务 4
- [x] §5 占位符 → 任务 2（make_placeholder）+ 任务 4（warning）
- [x] §6.1 diagram_svgs → 任务 1
- [x] §6.2 risk_matrix/evacuation → 任务 2
- [x] §6.3 生成后处理 → 任务 3

- [ ] **步骤 3：Commit（如收尾有额外改动）**

```bash
git add -A
git commit -m "chore(plan): diagrams batch2 final verification"
```
