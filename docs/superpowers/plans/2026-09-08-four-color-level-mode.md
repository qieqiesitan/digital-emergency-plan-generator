# 四色分布图分区显式等级 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 把四色分布图工作台的颜色模型从"任意手动色"升级为"显式等级"：`floor_plan_polygon` 用 `level_mode: auto|manual` + `risk_level` 表达分区颜色，颜色一律由 `LEVEL_COLORS` 派生；存量 manual 色读取时反查等级；AI 导入把识别等级显式落库；同时修复"画布点区域无法改颜色"的交互问题。

**架构：** 数据仍在 `RiskZone.floor_plan_polygon`（JSONB）内演进，不加列、不写 SQL 迁移：读取路径经 `normalize_polygon` 做旧→新归一化（含 `color_source=manual` 按四色反查等级），保存路径经 schema 强制新结构。后端 `effective_color`/`_zone_dual_levels` 改为"显式等级优先，否则按风险对象推导"；前端类型/提交工具同步切换，工作台选中区域联动所属分区并展示"跟随自动/指定四色等级"控件。

**技术栈：** FastAPI + SQLAlchemy(async) + Pydantic v2（backend 容器 emergency-plan-backend，8000）；React 19 + antd 6 + zustand + Konva + vitest（frontend 容器 emergency-plan-frontend，静态 8082 容器 shuzihuayuan）。

**运行环境（先读）：**

- 后端源文件：宿主 `backend/app` bind mount 到容器 `/app/app`，改动即时可见；但 uvicorn 无 `--reload`，真实 API 行为变化需 `docker restart emergency-plan-backend`（pytest 不需要重启）。
- 后端测试：`backend/tests` 不在 bind mount。新建/修改测试后需：
  `docker cp backend/tests/<file>.py emergency-plan-backend:/app/tests/<file>.py`，再 `docker exec emergency-plan-backend pytest tests/<file>.py -v`。
- 前端：宿主 `frontend/src` bind mount 到容器 `/app/src`。验证一律走容器：
  `docker exec emergency-plan-frontend npx vitest run`、`docker exec emergency-plan-frontend npx tsc -b`、
  `docker exec emergency-plan-frontend npx eslint <files>`。宿主 npx 不可用，勿在宿主直接跑。
- 构建同步：`docker exec emergency-plan-frontend npx vite build` 后
  `docker cp emergency-plan-frontend:/app/dist/. <宿主 frontend/dist>` 与
  `docker cp emergency-plan-frontend:/app/dist/. shuzihuayuan:/app/dist/`（若容器输出目录不是 `/app/dist`，先 `docker exec emergency-plan-frontend ls /app/dist` 核实）。
- git：TASKS.md 永不 add；工作区有大量他人/历史未提交改动（报告链路、uploads 删除、scripts 等），每次 commit 用 pathspec 只加本任务文件；commit 前 `git status --short` 核对。本计划涉及的目标文件当前均干净（不在他人未提交清单）。

---

## 文件结构

后端：

- 修改 `backend/app/schemas/risk_management.py`：`RiskZoneFloorPlanPolygon` 字段切换 + 旧结构归一化 validator
- 修改 `backend/app/services/risk_mapping_service.py`：`LEVEL_COLORS_REVERSE`、`normalize_polygon`、`validate_polygon_v2`、`effective_color`
- 修改 `backend/app/routers/risk_management.py`：`_zone_dual_levels`、`commit_four_color_import` 落库与响应、`/risk-publicity` 归一化
- 修改 `backend/tests/test_risk_mapping_service.py`：旧断言更新 + 新增归一化/校验/颜色用例
- 修改 `backend/tests/test_risk_mapping_workbench.py`：fixture 与响应断言更新
- 修改 `backend/tests/test_four_color_import_api.py`：落库与响应断言更新

前端：

- 修改 `frontend/src/types/riskManagement.ts`：`ColorSource` → `LevelMode`，`RiskZoneFloorPlanPolygon` 字段切换
- 修改 `frontend/src/types/riskMappingWorkbench.ts`：re-export 同步
- 修改 `frontend/src/utils/zoneSubmit.ts` + `zoneSubmit.test.ts`：`mergeEditedPolygon` 保留新字段
- 修改 `frontend/src/components/enterprise/RiskZoneForm.tsx`：本地 interface 同步
- 修改 `frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx`：onSave 默认多边形结构
- 修改 `frontend/src/store/riskMappingWorkbenchStore.test.ts`：fixture 同步
- 修改 `frontend/src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx`：编译适配（任务 4）+ 颜色区重构（任务 6）
- 修改 `frontend/src/components/enterprise/riskMapping/WorkbenchCanvas.tsx`：点区域联动所属分区（任务 5）
- 修改 `frontend/src/components/enterprise/riskMapping/WorkbenchLegend.tsx`：图例文案（任务 7）

---

### 任务 1：后端数据模型切换（schema + service 核心）

**文件：**
- 修改：`backend/app/services/risk_mapping_service.py`
- 修改：`backend/app/schemas/risk_management.py`
- 修改：`backend/tests/test_risk_mapping_service.py`

- [ ] **步骤 1：更新现有测试为红（新字段语义）**

把 `backend/tests/test_risk_mapping_service.py` 的旧字段引用全部改为新字段，并新增用例。先机械替换：

运行：`rg -n "color_source|color\b" backend/tests/test_risk_mapping_service.py`
预期：定位到 `_v2_polygon` helper（现 `{"version": 2, "color_source": "auto", "polygons": polygons}`）、`test_validate_polygon_rejects_bad_coordinates`、schema 校验用例与 `test_manual_color_wins`。

替换 helper 为：

```python
def _v2_polygon(polygons: list) -> dict:
    return {"version": 2, "level_mode": "auto", "risk_level": None, "polygons": polygons}
```

把 schema 相关用例改为：

```python
def test_risk_zone_polygon_normalizes_legacy_points():
    result = RiskZoneFloorPlanPolygon.model_validate({
        "id": "zone-1",
        "label": "原料库",
        "points": _points3(),
    })
    assert result.version == 2
    assert result.level_mode == "auto"
    assert result.risk_level is None
    assert result.polygons[0].id == "zone-1"


def test_risk_zone_polygon_normalizes_legacy_color_source_manual():
    result = RiskZoneFloorPlanPolygon.model_validate({
        "version": 2,
        "color_source": "manual",
        "color": "#ff4d4f",
        "polygons": [{"id": "p1", "points": _points3()}],
    })
    assert result.level_mode == "manual"
    assert result.risk_level == "重大"


def test_risk_zone_polygon_normalizes_legacy_color_source_unknown_color():
    result = RiskZoneFloorPlanPolygon.model_validate({
        "version": 2,
        "color_source": "manual",
        "color": "#123456",
        "polygons": [{"id": "p1", "points": _points3()}],
    })
    assert result.level_mode == "auto"
    assert result.risk_level is None


def test_risk_zone_polygon_rejects_invalid_level_mode():
    with pytest.raises(ValidationError):
        RiskZoneFloorPlanPolygon.model_validate({"version": 2, "level_mode": "hack", "polygons": [{"id": "p1", "points": _points3()}]})


def test_risk_zone_polygon_requires_level_for_manual():
    with pytest.raises(ValidationError):
        RiskZoneFloorPlanPolygon.model_validate({"version": 2, "level_mode": "manual", "risk_level": None, "polygons": [{"id": "p1", "points": _points3()}]})


def test_risk_zone_polygon_rejects_level_for_auto():
    with pytest.raises(ValidationError):
        RiskZoneFloorPlanPolygon.model_validate({"version": 2, "level_mode": "auto", "risk_level": "重大", "polygons": [{"id": "p1", "points": _points3()}]})


def test_risk_zone_polygon_accepts_manual_with_level():
    result = RiskZoneFloorPlanPolygon.model_validate({
        "version": 2,
        "level_mode": "manual",
        "risk_level": "较大",
        "polygons": [{"id": "p1", "points": _points3()}],
    })
    assert result.level_mode == "manual"
    assert result.risk_level == "较大"
```

删除 `test_risk_zone_polygon_rejects_invalid_color_source`、`test_risk_zone_polygon_requires_color_for_manual`、`test_risk_zone_polygon_accepts_manual_with_color`（被上例覆盖）。

新增 service 级用例（追加到文件末尾附近）：

```python
def test_normalize_legacy_manual_color_maps_to_level():
    result = normalize_polygon({
        "version": 2,
        "color_source": "manual",
        "color": "#fa8c16",
        "polygons": [{"id": "p1", "points": _points3()}],
    }, "原料库")
    assert result["level_mode"] == "manual"
    assert result["risk_level"] == "较大"
    assert "color_source" not in result
    assert "color" not in result


def test_normalize_legacy_manual_unknown_color_falls_back_auto():
    result = normalize_polygon({
        "version": 2,
        "color_source": "manual",
        "color": "#123456",
        "polygons": [{"id": "p1", "points": _points3()}],
    }, "原料库")
    assert result["level_mode"] == "auto"
    assert result["risk_level"] is None


def test_normalize_new_structure_is_idempotent():
    v2 = {"version": 2, "level_mode": "manual", "risk_level": "重大", "polygons": [{"id": "p1", "points": _points3()}]}
    once = normalize_polygon(v2, "原料库")
    twice = normalize_polygon(once, "原料库")
    assert once == twice == v2


def test_validate_polygon_manual_requires_level():
    errors = validate_polygon_v2({"version": 2, "level_mode": "manual", "risk_level": None, "polygons": [{"id": "p1", "points": _points3()}]})
    assert any("risk_level" in e for e in errors)


def test_validate_polygon_auto_rejects_level():
    errors = validate_polygon_v2({"version": 2, "level_mode": "auto", "risk_level": "重大", "polygons": [{"id": "p1", "points": _points3()}]})
    assert any("auto" in e and "risk_level" in e for e in errors)


def test_manual_level_color_wins():
    color = effective_color({"version": 2, "level_mode": "manual", "risk_level": "重大", "polygons": []}, "低")
    assert color == "#ff4d4f"


def test_auto_uses_computed_level():
    color = effective_color({"version": 2, "level_mode": "auto", "risk_level": None, "polygons": []}, "较大")
    assert color == "#fa8c16"


def test_manual_bad_level_falls_back_to_auto():
    color = effective_color({"version": 2, "level_mode": "manual", "risk_level": "未评估", "polygons": []}, "低")
    assert color == "#52c41a"
```

同时把 `test_validate_polygon_rejects_bad_coordinates` 的 payload 改为 `{"version": 2, "level_mode": "manual", "risk_level": "重大", "polygons": [...]}`（坐标越界断言不变），并修正文件末尾 batch 相关用例里的旧结构。

- [ ] **步骤 2：运行确认失败**

运行：
```powershell
docker cp backend/tests/test_risk_mapping_service.py emergency-plan-backend:/app/tests/test_risk_mapping_service.py
docker exec emergency-plan-backend pytest tests/test_risk_mapping_service.py -v
```
预期：FAIL（字段不存在 / 校验不通过等），收集失败数。

- [ ] **步骤 3：实现 service 新逻辑**

`backend/app/services/risk_mapping_service.py`：

```python
LEVEL_COLORS = {
    "重大": "#ff4d4f",
    "较大": "#fa8c16",
    "一般": "#fadb14",
    "低": "#52c41a",
    "未评估": "#d9d9d9",
}
LEVEL_COLORS_REVERSE = {v.lower(): k for k, v in LEVEL_COLORS.items()}
```

`normalize_polygon` 整体替换为：

```python
def normalize_polygon(raw: dict | None, zone_name: str = "") -> dict | None:
    if not raw:
        return None
    if raw.get("version") != 2:
        points = raw.get("points") or []
        return {
            "version": 2,
            "level_mode": "auto",
            "risk_level": None,
            "polygons": [{
                "id": raw.get("id") or "legacy-polygon",
                "label": raw.get("label") or zone_name,
                "points": points,
            }],
        }
    data = dict(raw)
    if "color_source" in data:
        level = None
        if data.get("color_source") == "manual" and data.get("color"):
            level = LEVEL_COLORS_REVERSE.get(str(data["color"]).lower())
        data["level_mode"] = "manual" if level else "auto"
        data["risk_level"] = level
        data.pop("color_source", None)
        data.pop("color", None)
    else:
        data.setdefault("level_mode", "auto")
        data.setdefault("risk_level", None)
    if data["level_mode"] == "auto":
        data["risk_level"] = None
    return data
```

`validate_polygon_v2` 开头归一化并替换颜色校验段：

```python
def validate_polygon_v2(polygon: dict | None) -> list[str]:
    errors: list[str] = []
    if not polygon:
        return ["floor_plan_polygon 不能为空"]
    if not isinstance(polygon, dict):
        errors.append("floor_plan_polygon 必须为对象")
        return errors
    polygon = normalize_polygon(polygon) or polygon
    if polygon.get("version") != 2:
        errors.append("version 必须为 2")
    if polygon.get("level_mode") not in ("auto", "manual"):
        errors.append("level_mode 必须为 auto 或 manual")
    elif polygon.get("level_mode") == "manual":
        if polygon.get("risk_level") not in LEVEL_COLORS or polygon.get("risk_level") == "未评估":
            errors.append("manual 模式必须指定 risk_level（重大/较大/一般/低）")
    elif polygon.get("risk_level") is not None:
        errors.append("auto 模式不允许携带 risk_level")
    # ... 原有 polygons/坐标/id 重复校验保持不变 ...
```

`effective_color` 替换为：

```python
def effective_color(polygon: dict | Any | None, max_level: str | None) -> str:
    data = polygon.model_dump() if polygon and hasattr(polygon, "model_dump") else polygon
    if data:
        data = normalize_polygon(dict(data)) or {}
        if data.get("level_mode") == "manual" and data.get("risk_level") in LEVEL_COLORS_REVERSE.values():
            return LEVEL_COLORS[data["risk_level"]]
    return LEVEL_COLORS.get(max_level or "未评估", "#d9d9d9")
```

注意：`LEVEL_COLORS_REVERSE` 构建时必须排除"未评估"灰键（`{v.lower(): k for k, v in LEVEL_COLORS.items() if k != "未评估"}`），否则灰 `#d9d9d9` 会被反查成"未评估"并误入 manual 分支；反查表只含四大等级后，manual 分支用 `LEVEL_COLORS_REVERSE.values()` 判断即天然排除"未评估"，与 schema 的 `RISK_LEVEL_SET`（四色）口径一致。`validate_polygon_v2` 只应在输入含旧 `color_source` 键时归一化，避免 `normalize_polygon` 把 auto+risk_level 的非法输入吞成合法。

- [ ] **步骤 4：实现 schema 新结构**

`backend/app/schemas/risk_management.py`：文件顶部加导入（无循环：service 不 import 本 schema 模块）：

```python
from app.services.risk_mapping_service import LEVEL_COLORS_REVERSE
```

`RiskZoneFloorPlanPolygon` 整体替换为：

```python
class RiskZoneFloorPlanPolygon(BaseModel):
    version: Literal[2] = 2
    level_mode: Literal["auto", "manual"] = "auto"
    risk_level: str | None = None
    polygons: list[RiskPolygon] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy(cls, data: Any):
        """兼容旧结构：{points} 旧版与 color_source/color 旧版都归一化为 level_mode/risk_level。"""
        if not isinstance(data, dict):
            return data
        if data.get("points") is not None and data.get("polygons") is None:
            return {
                "version": 2,
                "level_mode": "auto",
                "risk_level": None,
                "polygons": [{
                    "id": data.get("id") or "legacy-polygon",
                    "label": data.get("label"),
                    "points": data.get("points"),
                }],
            }
        if data.get("version") == 2 and data.get("color_source") is not None:
            level = (
                LEVEL_COLORS_REVERSE.get(str(data.get("color") or "").lower())
                if data.get("color_source") == "manual" else None
            )
            return {
                "version": 2,
                "level_mode": "manual" if level else "auto",
                "risk_level": level,
                "polygons": data.get("polygons") or [],
            }
        return data

    @model_validator(mode="after")
    def validate_v2_rules(self):
        if self.level_mode == "manual" and self.risk_level not in RISK_LEVEL_SET:
            raise ValueError("manual 模式必须指定 risk_level（重大/较大/一般/低）")
        if self.level_mode == "auto" and self.risk_level is not None:
            raise ValueError("auto 模式不允许携带 risk_level")
        ids = [p.id for p in self.polygons]
        if len(ids) != len(set(ids)):
            raise ValueError("polygons.id 不能重复")
        return self
```

注意：RISK_LEVEL_SET 只有四色（不含"未评估"），与 manual 约束一致。

- [ ] **步骤 5：运行确认通过**

运行：`docker exec emergency-plan-backend pytest tests/test_risk_mapping_service.py -v`
预期：全部 PASS（含重写的旧用例与新增用例）。

- [ ] **步骤 6：Commit**

```powershell
git add backend/app/services/risk_mapping_service.py backend/app/schemas/risk_management.py backend/tests/test_risk_mapping_service.py
git commit -m "feat(risk): 分区多边形颜色模型切换为显式等级（level_mode/risk_level）"
```

---

### 任务 2：双等级口径与公示接口归一化

**文件：**
- 修改：`backend/app/routers/risk_management.py`
- 修改：`backend/tests/test_risk_mapping_workbench.py`

- [ ] **步骤 1：更新 workbench 测试 fixture 为红**

`backend/tests/test_risk_mapping_workbench.py`：

运行：`rg -n "color_source|color\b" backend/tests/test_risk_mapping_workbench.py`

把第 21-22 行附近的分区 fixture 与第 86-87 行附近的 payload dict 改为：

```python
level_mode="manual",
risk_level="较大",
```

与

```python
"level_mode": "manual",
"risk_level": "较大",
```

并在批量保存成功用例附近新增：

```python
@pytest.mark.asyncio
async def test_workbench_response_uses_manual_level_override():
    zone = MagicMock()
    zone.floor_plan_polygon = {"version": 2, "level_mode": "manual", "risk_level": "重大", "polygons": []}
    from app.routers.risk_management import _zone_dual_levels
    current, color, inherent, inherent_color = _zone_dual_levels(zone)
    assert current == "重大"
    assert inherent == "重大"
    assert color == "#ff4d4f"
    assert inherent_color == "#ff4d4f"
```

（若该文件对 `_zone_dual_levels` 的 mock zone 结构与上述不同，以文件内既有 fixture 为准拼接；若文件已有 manual 相关断言，按其语义同步为新字段。）

- [ ] **步骤 2：运行确认失败**

运行：
```powershell
docker cp backend/tests/test_risk_mapping_workbench.py emergency-plan-backend:/app/tests/test_risk_mapping_workbench.py
docker exec emergency-plan-backend pytest tests/test_risk_mapping_workbench.py -v
```
预期：FAIL（旧字段缺失 / 手动等级未生效）。

- [ ] **步骤 3：实现 _zone_dual_levels 显式等级优先**

`backend/app/routers/risk_management.py`：

```python
def _zone_dual_levels(zone):
    """返回 (max_level, effective_color, inherent_max_level, inherent_effective_color)。
    显式等级（level_mode=manual）对现有/固有两种模式同时生效。"""
    poly = zone.floor_plan_polygon
    override = None
    if isinstance(poly, dict):
        if poly.get("level_mode") == "manual" and poly.get("risk_level") in LEVEL_COLORS:
            override = poly["risk_level"]
    current = override or max_risk_level(zone)
    inherent = override or max_risk_level(zone, "inherent")
    return (current, effective_color(poly, current), inherent, effective_color(poly, inherent))
```

- [ ] **步骤 4：/risk-publicity 接入 normalize**

同一文件 `get_risk_publicity` 的 `zones_data.append` 中，`"floor_plan_polygon": z.floor_plan_polygon` 改为：

```python
"floor_plan_polygon": normalize_polygon(z.floor_plan_polygon, z.name),
```

（`normalize_polygon` 已在文件顶部导入，见现有 import 列表。）

- [ ] **步骤 5：运行确认通过**

运行：`docker exec emergency-plan-backend pytest tests/test_risk_mapping_workbench.py -v`
预期：全部 PASS。

- [ ] **步骤 6：Commit**

```powershell
git add backend/app/routers/risk_management.py backend/tests/test_risk_mapping_workbench.py
git commit -m "feat(risk): 分区显式等级优先于双模式推导，公示接口归一化多边形结构"
```

---

### 任务 3：AI 导入落库显式等级

**文件：**
- 修改：`backend/app/routers/risk_management.py`
- 修改：`backend/tests/test_four_color_import_api.py`

- [ ] **步骤 1：更新导入测试断言为红**

`backend/tests/test_four_color_import_api.py` 的 commit 成功用例（约 420 行）：

```python
assert created_polys[0]["risk_level"] == "重大"
assert created_polys[1]["risk_level"] == "低"
assert created_polys[0]["level_mode"] == "manual"
assert created_polys[0]["color_source"] not in created_polys[0]
```

并在该用例末尾追加响应等级断言：

```python
assert resp.data.zones[0].max_risk_level == "重大"
assert resp.data.zones[0].effective_color == "#ff4d4f"
```

若文件内其它用例（含 `_saved_zones_result` 之类的 mock 响应）断言了 `effective_color`/`max_risk_level` 语义，一并按"manual 等级即响应等级"修正；`analyze` 返回的 draft zone `color`/`risk_level` 键属 AI 识别结果结构，不动。

若 commit 成功用例中模拟 `saved_zones` 的 fixture `floor_plan_polygon=None`（如 `_saved_zones_result`），响应断言无法取到等级，需把该 fixture 的 `floor_plan_polygon` 改为 `{"version": 2, "level_mode": "manual", "risk_level": "重大", "polygons": []}` 等含手动等级的 dict，再运行。

- [ ] **步骤 2：运行确认失败**

运行：
```powershell
docker cp backend/tests/test_four_color_import_api.py emergency-plan-backend:/app/tests/test_four_color_import_api.py
docker exec emergency-plan-backend pytest tests/test_four_color_import_api.py -v
```
预期：FAIL（落库仍是 color_source/color，响应无等级）。

- [ ] **步骤 3：实现落库与响应**

`commit_four_color_import` 中两处 `floor_plan_polygon` dict（预校验的 `polygon_v2` 与 `RiskZone(...)` 构造）都替换为：

```python
{
    "version": 2,
    "level_mode": "manual",
    "risk_level": zone.risk_level,
    "polygons": [
        {"id": f"poly-{i}", "label": zone.name, "points": [p.model_dump() for p in poly.points]}
        for i, poly in enumerate(zone.polygons)
    ],
}
```

（新建分区的 id 前缀沿用 `poly-{i}` 与 `poly-{i}-{j}` 两种现有写法，勿改。）

响应组装段（保存后遍历 `saved_zones`）替换为：

```python
for z in saved_zones:
    r = RiskZoneResponse.model_validate(z)
    norm = normalize_polygon(z.floor_plan_polygon, z.name)
    r.floor_plan_polygon = RiskZoneFloorPlanPolygon.model_validate(norm) if norm else None
    level = norm.get("risk_level") if norm and norm.get("level_mode") == "manual" else None
    r.max_risk_level = level
    r.inherent_max_level = level
    r.effective_color = effective_color(norm, level)
    r.inherent_effective_color = effective_color(norm, level)
    zone_responses.append(r)
```

删除"导入的分区暂无风险对象"注释及其特判逻辑。

- [ ] **步骤 4：运行确认通过**

运行：`docker exec emergency-plan-backend pytest tests/test_four_color_import_api.py -v`
预期：全部 PASS。

- [ ] **步骤 5：Commit**

```powershell
git add backend/app/routers/risk_management.py backend/tests/test_four_color_import_api.py
git commit -m "feat(risk): AI 四色图导入落库显式等级并返回真实分区等级"
```

---

### 任务 4：前端类型与提交工具切换

**文件：**
- 修改：`frontend/src/types/riskManagement.ts`
- 修改：`frontend/src/types/riskMappingWorkbench.ts`
- 修改：`frontend/src/utils/zoneSubmit.ts`
- 修改：`frontend/src/utils/zoneSubmit.test.ts`
- 修改：`frontend/src/components/enterprise/RiskZoneForm.tsx`
- 修改：`frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx`
- 修改：`frontend/src/store/riskMappingWorkbenchStore.test.ts`
- 修改：`frontend/src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx`

- [ ] **步骤 1：改写 zoneSubmit 测试为红**

`frontend/src/utils/zoneSubmit.test.ts` 中"keeps the v2 color_source and color..."用例改为：

```ts
it("keeps the v2 level_mode and risk_level instead of resetting to auto", () => {
  const existing = {
    version: 2 as const,
    level_mode: "manual" as const,
    risk_level: "重大" as const,
    polygons: [{ id: "p-old", label: "旧区", points: [{ x: 1, y: 2 }, { x: 3, y: 4 }, { x: 5, y: 6 }] }],
  };
  const result = mergeEditedPolygon(existing, "新区", [{ x: 7, y: 8 }, { x: 9, y: 10 }, { x: 11, y: 12 }]);
  expect(result.level_mode).toBe("manual");
  expect(result.risk_level).toBe("重大");
});
```

并把文件顶部 fixture（第 7 行附近 `color_source: "auto",`）与新断言里所有 `color_source`/`color` 改为 `level_mode`/`risk_level`。

- [ ] **步骤 2：类型与工具切换**

`frontend/src/types/riskManagement.ts`：

```ts
export type RiskLevel = "重大" | "较大" | "一般" | "低" | "未评估";
export type LevelMode = "auto" | "manual";
export interface RiskZoneFloorPlanPolygon {
  version: 2;
  level_mode: LevelMode;
  risk_level: Exclude<RiskLevel, "未评估"> | null;
  polygons: RiskPolygon[];
}
```

删除 `ColorSource` 类型。`frontend/src/types/riskMappingWorkbench.ts` 的 re-export 列表把 `ColorSource` 换成 `LevelMode`。

`frontend/src/utils/zoneSubmit.ts` `mergeEditedPolygon` 返回值改为：

```ts
return {
  version: 2,
  level_mode: current?.level_mode ?? "auto",
  risk_level: current?.risk_level ?? null,
  polygons: [edited, ...rest],
};
```

`frontend/src/components/enterprise/RiskZoneForm.tsx` 本地 interface `floor_plan_polygon` 同步为 `level_mode: "auto" | "manual"; risk_level: RiskLevel | null;`（文件需 import `RiskLevel` 类型）。

`frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx` onSave 默认结构改为：

```ts
const polygon = z.floor_plan_polygon ?? { version: 2, level_mode: "auto" as const, risk_level: null, polygons: [] };
```

`frontend/src/store/riskMappingWorkbenchStore.test.ts` 第 360 行附近 fixture 改为 `level_mode: "auto", risk_level: null,`。

- [ ] **步骤 3：修复 WorkbenchPropertiesPanel 编译点（最小适配）**

`WorkbenchPropertiesPanel.tsx` 中三处默认结构字面量（约 93/125/368 行）把 `{ version: 2, color_source: "auto" as const, color: null, polygons: [] }` 改为：

```ts
{ version: 2, level_mode: "auto" as const, risk_level: null, polygons: [] }
```

颜色下拉（约 365-386 行）最小适配为：

```tsx
<Select
  style={{ width: "100%", marginTop: 8 }}
  value={zone.floor_plan_polygon?.level_mode || "auto"}
  options={[{ value: "auto", label: "自动颜色" }, { value: "manual", label: "手动覆盖" }]}
  onChange={value => {
    const polygon = zone.floor_plan_polygon || { version: 2, level_mode: "auto" as const, risk_level: null, polygons: [] };
    updateZone({
      floor_plan_polygon: {
        ...polygon,
        level_mode: value as "auto" | "manual",
        risk_level: value === "manual" ? polygon.risk_level || "重大" : null,
      },
    });
  }}
/>
{zone.floor_plan_polygon?.level_mode === "manual" && (
  <Input
    type="text"
    style={{ width: "100%", marginTop: 8 }}
    value={zone.floor_plan_polygon.risk_level || "重大"}
    disabled
  />
)}
```

（任务 6 会把它替换为正式的四色等级 UI。）

- [ ] **步骤 4：运行确认通过**

运行：`docker exec emergency-plan-frontend npx vitest run src/utils/zoneSubmit.test.ts`
预期：PASS。

运行：`docker exec emergency-plan-frontend npx tsc -b`
预期：0 error（若报其它引用点，用 `rg -n "color_source|ColorSource|\.color\b" frontend/src` 排查并同步为新字段，注意区分无关对象的 `.color`，如文字标注 `RiskCanvasText.color` 与法规/风险矩阵等业务色字段——这些保留不动）。

- [ ] **步骤 5：Commit**

```powershell
git add frontend/src/types/riskManagement.ts frontend/src/types/riskMappingWorkbench.ts frontend/src/utils/zoneSubmit.ts frontend/src/utils/zoneSubmit.test.ts frontend/src/components/enterprise/RiskZoneForm.tsx frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx frontend/src/store/riskMappingWorkbenchStore.test.ts frontend/src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx
git commit -m "feat(frontend): 四色分区多边形类型与提交工具切换为显式等级"
```

---

### 任务 5：画布选中区域联动所属分区

**文件：**
- 修改：`frontend/src/components/enterprise/riskMapping/WorkbenchCanvas.tsx`
- 修改：`frontend/src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx`

- [ ] **步骤 1：实现联动（本任务无独立单测，以 tsc + 回归 + 冒烟验证）**

`WorkbenchCanvas.tsx` 已绑定区域 `onClick`（约 890 行附近）改为：

```tsx
onClick={e => {
  e.cancelBubble = true;
  setState({
    selectedRegionId: regionId,
    selectedRiskPointId: null,
    selectedTextId: null,
    selectedZoneId: z.id,
  });
}}
```

`WorkbenchPropertiesPanel.tsx` `bindSelectedPending` 末尾 `setState({ selectedRegionId: null });` 改为：

```tsx
setState({ selectedRegionId: null, selectedZoneId: target.id });
```

- [ ] **步骤 2：验证**

运行：`docker exec emergency-plan-frontend npx tsc -b`
预期：0 error。

运行：`docker exec emergency-plan-frontend npx vitest run`
预期：全量 PASS（含 store/service 既有用例）。

- [ ] **步骤 3：Commit**

```powershell
git add frontend/src/components/enterprise/riskMapping/WorkbenchCanvas.tsx frontend/src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx
git commit -m "feat(frontend): 画布选中区域自动联动所属分区属性面板"
```

---

### 任务 6：属性面板四色等级选择 UI

**文件：**
- 修改：`frontend/src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx`

- [ ] **步骤 1：实现颜色区重构**

把分区属性节（`!zone ? ... : (<>...)`）中的"颜色来源下拉 + text input"整体替换为：

```tsx
<div style={{ borderTop: "1px solid #f0f0f0", marginTop: 8, paddingTop: 8 }}>
  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>分区颜色</div>
  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
    <span style={{ width: 18, height: 18, borderRadius: 4, background: zoneColorPreview, display: "inline-block", border: "1px solid #d9d9d9" }} />
    <span style={{ fontSize: 12, color: "#666" }}>
      {levelPreview}
    </span>
  </div>
  <Radio.Group
    size="small"
    value={zone.floor_plan_polygon?.level_mode || "auto"}
    onChange={e => {
      const polygon = zone.floor_plan_polygon || { version: 2, level_mode: "auto" as const, risk_level: null, polygons: [] };
      const mode = e.target.value as "auto" | "manual";
      updateZone({
        floor_plan_polygon: {
          ...polygon,
          level_mode: mode,
          risk_level: mode === "manual" ? polygon.risk_level || "较大" : null,
        },
      });
    }}
    options={[
      { value: "auto", label: "跟随自动" },
      { value: "manual", label: "手动指定" },
    ]}
  />
  {zone.floor_plan_polygon?.level_mode === "manual" && (
    <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
      {LEVEL_CHOICES.map(([level, color]) => (
        <button
          key={level}
          type="button"
          onClick={() =>
            updateZone({
              floor_plan_polygon: {
                ...zone.floor_plan_polygon!,
                level_mode: "manual",
                risk_level: level,
              },
            })
          }
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            padding: "4px 8px",
            borderRadius: 6,
            border: zone.floor_plan_polygon?.risk_level === level ? "2px solid #1677ff" : "1px solid #d9d9d9",
            background: color,
            color: level === "一般" ? "#333" : "#fff",
            cursor: "pointer",
            fontSize: 12,
          }}
        >
          {level}
        </button>
      ))}
    </div>
  )}
  <div style={{ fontSize: 12, color: "#999", marginTop: 6 }}>
    手动指定后现有/固有模式均显示该颜色，不随风险对象变化。
  </div>
</div>
```

文件顶部导入补充并定义常量：

```ts
import { Radio } from "antd";
import { RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";

const LEVEL_CHOICES: [string, string][] = [
  ["重大", RISK_LEVEL_COLORS["重大"]],
  ["较大", RISK_LEVEL_COLORS["较大"]],
  ["一般", RISK_LEVEL_COLORS["一般"]],
  ["低", RISK_LEVEL_COLORS["低"]],
];
```

组件内（`zone` 已可用处）计算预览值：

```ts
const levelPreview =
  zone.floor_plan_polygon?.level_mode === "manual"
    ? `手动指定 · ${zone.floor_plan_polygon.risk_level ?? "未指定"}风险`
    : `${zone.max_risk_level || "未评估"}风险（自动）`;
const zoneColorPreview =
  zone.floor_plan_polygon?.level_mode === "manual"
    ? (zone.floor_plan_polygon.risk_level && RISK_LEVEL_COLORS[zone.floor_plan_polygon.risk_level]) || "#d9d9d9"
    : zone.effective_color || "#d9d9d9";
```

把颜色区放在分区名称 `Input` 下方、`description` TextArea 上方。删除任务 4 的临时 disabled text input 与旧 `<Input type="color">`。

- [ ] **步骤 2：验证**

运行：`docker exec emergency-plan-frontend npx tsc -b`，预期 0 error。

运行：`docker exec emergency-plan-frontend npx vitest run`，预期全量 PASS。

运行：`docker exec emergency-plan-frontend npx eslint src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx`，预期 0 error。

- [ ] **步骤 3：Commit**

```powershell
git add frontend/src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx
git commit -m "feat(frontend): 属性面板分区颜色改四色等级选择"
```

---

### 任务 7：图例文案

**文件：**
- 修改：`frontend/src/components/enterprise/riskMapping/WorkbenchLegend.tsx`

- [ ] **步骤 1：更新文案**

`WorkbenchLegend.tsx` 标题由"区域颜色 = 该区域 {固有|现有} 最大风险等级"改为：

```tsx
<div style={{ fontWeight: 600, marginBottom: 6 }}>
  区域颜色 = 所属分区颜色（{colorMode === "inherent" ? "固有" : "现有"}最大风险等级或手动指定等级）
</div>
```

- [ ] **步骤 2：验证**

运行：`docker exec emergency-plan-frontend npx tsc -b`，预期 0 error。

- [ ] **步骤 3：Commit**

```powershell
git add frontend/src/components/enterprise/riskMapping/WorkbenchLegend.tsx
git commit -m "docs(frontend): 四色图例文案说明手动指定等级来源"
```

---

### 任务 8：全量回归与部署同步

**文件：** 无代码改动；仅验证与 dist 同步。

- [ ] **步骤 1：后端定向回归**

```powershell
docker cp backend/tests/test_risk_mapping_service.py emergency-plan-backend:/app/tests/test_risk_mapping_service.py
docker cp backend/tests/test_risk_mapping_workbench.py emergency-plan-backend:/app/tests/test_risk_mapping_workbench.py
docker cp backend/tests/test_four_color_import_api.py emergency-plan-backend:/app/tests/test_four_color_import_api.py
docker exec emergency-plan-backend pytest tests/test_risk_mapping_service.py tests/test_risk_mapping_workbench.py tests/test_four_color_import_api.py tests/test_report_four_color_service.py -v
```
预期：全部 PASS。

后端重启并健康检查（API 行为变化生效）：
```powershell
docker restart emergency-plan-backend
docker exec emergency-plan-backend sh -c "curl -s http://localhost:8000/health"
```
预期：返回 200/ok。

- [ ] **步骤 2：前端全量验证**

```powershell
docker exec emergency-plan-frontend npx vitest run
docker exec emergency-plan-frontend npx tsc -b
```
预期：vitest 全量 PASS、tsc 0 error。

- [ ] **步骤 3：构建与同步**

```powershell
docker exec emergency-plan-frontend npx vite build
docker cp emergency-plan-frontend:/app/dist/. "C:\Users\55061\Documents\数字化预案自动生成 2\frontend\dist\"
docker cp emergency-plan-frontend:/app/dist/. shuzihuayuan:/app/dist/
```
预期：build 成功（既有 chunk>500KB 警告可接受）；8082 `curl http://localhost:8082` 引用的新 asset HTTP 200。

- [ ] **步骤 4：浏览器冒烟（人工/Playwright 清单）**

用已有账号登录 8082 工作台逐项验证：

1. 手绘：画一块区域 → 绑定分区 → 属性面板自动切到该分区并出现"分区颜色"；选"手动指定"点"较大"→ 画布该分区区域变橙、左侧卡片等级显示"较大"。
2. 保存并刷新：等级/颜色保持；现有/固有模式切换时手动指定分区颜色不变、auto 分区颜色随模式变化。
3. AI 导入：导入一张四色图 → 分区等级显示为识别等级（重大/较大/一般/低）而非"未评估"，颜色与识别图一致。
4. 风险公示/概览：分区等级与颜色口径与工作台一致；报告四色插图颜色一致。
5. 旧数据兼容：任意一个此前 AI 导入的楼层打开不报错，分区呈现其识别等级颜色。

- [ ] **步骤 5：收尾核对**

运行：`git status --short`
预期：仅剩 TASKS.md 与本任务无关的他人/历史改动；本计划 7 个 commit 均已入 log（`git log --oneline -8` 核对）。

---

## 自检

**1. 规格覆盖度：** 数据模型（任务 1）、读取归一化与幂等（任务 1）、计算口径统一（任务 1 effective_color + 任务 2 `_zone_dual_levels`）、AI 导入落库与响应（任务 3）、公示接口归一化（任务 2）、前端类型（任务 4）、选中联动（任务 5）、四色等级 UI（任务 6）、图例文案（任务 7）、验证与部署（任务 8）——规格每节均有对应任务。旧数据无 SQL 迁移与 `RiskZone` 不加列已落实为"仅 JSON 内演进"。

**2. 占位符扫描：** 无 TODO/待定；每个步骤含代码块或精确命令。

**3. 类型一致性：** 后端统一 `level_mode: "auto"|"manual"` + `risk_level`（四色或 None）；schema 与 service 校验规则一致；前端 `LevelMode` 与后端 `Literal["auto","manual"]` 对齐；`risk_level` 前端用 `Exclude<RiskLevel, "未评估"> | null`，后端 manual 校验用 `RISK_LEVEL_SET`（四色）一致。`RiskZoneFloorPlanPolygon` 在各任务中的字段名一致。
