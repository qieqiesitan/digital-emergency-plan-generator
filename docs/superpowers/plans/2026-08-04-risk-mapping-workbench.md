# 风险分级管控四色分布图工作台 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法跟踪进度。

**目标：** 在风险分级管控模块中新增四色分布图工作台，支持多层厂房、分区绘制、风险点拖拽/新建、颜色自动与手动覆盖、批量保存和总览联动。

**架构：** 后端新增 `enterprise_floors` 及 `risk_zones/risk_objects.floor_id`，用 JSONB 保存 v2 多边形与楼层文字；新增 Floors CRUD、Workbench 聚合加载和单事务批量保存。前端使用 React 19 + Zustand + Konva/react-konva 实现画布工作台，总览页复用同一百分比坐标数据渲染只读分布图。

**技术栈：** Python 3.12 + FastAPI + SQLAlchemy 2.0 async + PostgreSQL JSONB + React 19 + TypeScript + Zustand + Ant Design + Konva/react-konva。

**规格文档：** `docs/superpowers/specs/2026-08-04-risk-mapping-drawing-design.md`

---

## 批次与依赖

| 批次 | 任务 | 并行数 | 依赖 |
|---|---|:---:|---|
| 第 1 批 | 任务 1（模型/迁移）+ 任务 2（服务/Schema） | 1 | — |
| 第 2 批 | 任务 3（Floors/上传/清理）+ 任务 4（Workbench API） | 1 | 第 1 批 |
| 第 3 批 | 任务 5（前端类型/服务/路由）+ 任务 6（Store/几何） | 2 | 第 2 批 |
| 第 4 批 | 任务 7（工作台框架）+ 任务 8（画布工具） | 2 | 第 3 批 |
| 第 5 批 | 任务 9（绑定/保存/属性）+ 任务 10（总览联动） | 2 | 第 4 批 |
| 收尾 | 任务 11（E2E/性能/发布验证） | 1 | 第 5 批 |

---

## 文件结构

### 后端新建

| 文件 | 职责 |
|---|---|
| `backend/db_migration_risk_mapping_workbench.sql` | 楼层表、字段、索引、约束、旧数据迁移 |
| `backend/app/services/risk_mapping_service.py` | v2 多边形、颜色、楼层默认值、级联统计 |
| `backend/app/services/floor_plan_storage_service.py` | 平面图校验、存储、替换、清理 |
| `backend/app/services/enterprise_cleanup_service.py` | 企业级风险分级数据清理 |
| `backend/tests/test_risk_mapping_migration.py` | 模型字段与迁移 SQL 幂等断言 |
| `backend/tests/test_risk_mapping_service.py` | 多边形/颜色/级联统计纯函数测试 |
| `backend/tests/test_risk_mapping_workbench.py` | API 级工作台/批量保存测试 |
| `backend/tests/test_floor_plan_upload.py` | 上传契约与默认楼层同步测试 |
| `backend/tests/test_risk_mapping_cascade.py` | 分区/企业删除确认与级联测试 |

### 后端修改

| 文件 | 变更 |
|---|---|
| `backend/requirements.txt` | 增加 `Pillow`、`pytest`、`pytest-asyncio` |
| `backend/app/models/enterprise.py` | 新增 `EnterpriseFloor` |
| `backend/app/models/risk_management.py` | 新增 `floor_id`，`zone_id` 外键改为 `RESTRICT` |
| `backend/app/schemas/risk_management.py` | 新增楼层/工作台/批量保存/总览 Schema |
| `backend/app/routers/risk_management.py` | 新增 Floors CRUD、Workbench、Overview、Batch Save |
| `backend/app/routers/enterprises.py` | 企业删除改为调用清理服务 |

### 前端新建

| 文件 | 职责 |
|---|---|
| `frontend/src/types/riskMappingWorkbench.ts` | 工作台专用 TS 类型 |
| `frontend/src/services/riskMappingWorkbenchService.ts` | 工作台 API 调用 |
| `frontend/src/utils/riskMappingGeometry.ts` | 坐标转换、多边形校验、吸附 |
| `frontend/src/store/riskMappingWorkbenchStore.ts` | 工作台 Zustand Store |
| `frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx` | 工作台页面壳 |
| `frontend/src/components/enterprise/EnterpriseFloorManager.tsx` | 楼层维护 |
| `frontend/src/components/enterprise/riskMapping/WorkbenchToolbar.tsx` | 工具栏 |
| `frontend/src/components/enterprise/riskMapping/WorkbenchZonePanel.tsx` | 左侧分区面板 |
| `frontend/src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx` | 右侧属性面板 |
| `frontend/src/components/enterprise/riskMapping/WorkbenchCanvas.tsx` | Konva 画布 |
| `frontend/src/components/enterprise/riskMapping/WorkbenchRiskPointLayer.tsx` | 风险点图层 |
| `frontend/src/components/enterprise/riskMapping/RiskDistributionStage.tsx` | 总览只读分布图 |
| `frontend/src/components/enterprise/riskMapping/WorkbenchLegend.tsx` | 四色图例 |
| `frontend/e2e/risk-mapping-workbench.spec.ts` | E2E 流程 |
| `frontend/src/store/riskMappingWorkbenchStore.test.ts` | Store 单元测试 |

### 前端修改

| 文件 | 变更 |
|---|---|
| `frontend/package.json` | 增加 `konva`、`react-konva` |
| `frontend/src/types/riskManagement.ts` | 扩展 floor_id、polygon v2、updated_at |
| `frontend/src/types/enterprise.ts` | 扩展楼层相关字段 |
| `frontend/src/services/riskManagementService.ts` | 扩展 zones/objects/hierarchy/overview |
| `frontend/src/routes/index.tsx` | 增加工作台路由 |
| `frontend/src/pages/Enterprise/RiskManagementTab.tsx` | 增加工作台入口 |
| `frontend/src/pages/Enterprise/RiskOverviewPage.tsx` | 替换占位热区 |
| `frontend/src/components/enterprise/RiskZoneForm.tsx` | v2 多边形兼容 |
| `frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx` | 楼层平面图读取切换 |

---

## 任务 1：数据模型与迁移基线

**文件：**
- 创建：`backend/db_migration_risk_mapping_workbench.sql`
- 创建：`backend/tests/test_risk_mapping_migration.py`
- 修改：`backend/app/models/enterprise.py`
- 修改：`backend/app/models/risk_management.py`

- [ ] **步骤 1.1：编写迁移 SQL**

创建 `backend/db_migration_risk_mapping_workbench.sql`，内容为规格文档 `4.1`、`4.2`、`4.3`、`4.6` 的完整 SQL。核心内容如下：

```sql
BEGIN;

CREATE TABLE IF NOT EXISTS enterprise_floors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    floor_plan_url VARCHAR(500),
    description TEXT,
    canvas_width INTEGER,
    canvas_height INTEGER,
    canvas_texts JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_default BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_ef_enterprise FOREIGN KEY (enterprise_id) REFERENCES enterprises(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_ef_enterprise ON enterprise_floors(enterprise_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ef_enterprise_name ON enterprise_floors(enterprise_id, name);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ef_default_per_enterprise ON enterprise_floors(enterprise_id) WHERE is_default = true;

INSERT INTO enterprise_floors (enterprise_id, name, sort_order, floor_plan_url, description, is_default)
SELECT e.id, '默认总图', 0, e.floor_plan_url, '由 enterprises.floor_plan_url 迁移生成', true
FROM enterprises e
WHERE NOT EXISTS (
    SELECT 1 FROM enterprise_floors ef WHERE ef.enterprise_id = e.id AND ef.is_default = true
)
ON CONFLICT (enterprise_id, name) DO UPDATE
SET is_default = true,
    floor_plan_url = EXCLUDED.floor_plan_url,
    description = EXCLUDED.description;

ALTER TABLE risk_zones ADD COLUMN IF NOT EXISTS floor_id UUID;
ALTER TABLE risk_objects ADD COLUMN IF NOT EXISTS floor_id UUID;

UPDATE risk_zones rz
SET floor_id = ef.id
FROM enterprise_floors ef
WHERE ef.enterprise_id = rz.enterprise_id
  AND ef.is_default = true
  AND rz.floor_id IS NULL;

UPDATE risk_objects ro
SET floor_id = COALESCE(rz.floor_id, ef.id)
FROM risk_zones rz, enterprise_floors ef
WHERE rz.id = ro.zone_id
  AND ef.enterprise_id = ro.enterprise_id
  AND ef.is_default = true
  AND ro.floor_id IS NULL;

ALTER TABLE risk_zones ALTER COLUMN floor_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_risk_zones_floor'
    ) THEN
        ALTER TABLE risk_zones
            ADD CONSTRAINT fk_risk_zones_floor
            FOREIGN KEY (floor_id) REFERENCES enterprise_floors(id) ON DELETE RESTRICT;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_risk_objects_floor'
    ) THEN
        ALTER TABLE risk_objects
            ADD CONSTRAINT fk_risk_objects_floor
            FOREIGN KEY (floor_id) REFERENCES enterprise_floors(id) ON DELETE RESTRICT;
    END IF;
END $$;

DO $$
DECLARE fk_name text;
BEGIN
    SELECT conname INTO fk_name
    FROM pg_constraint
    WHERE conrelid = 'risk_objects'::regclass
      AND contype = 'f'
      AND confrelid = 'risk_zones'::regclass
      AND conname <> 'fk_risk_objects_zone';
    IF fk_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE risk_objects DROP CONSTRAINT %I', fk_name);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_risk_objects_zone'
          AND conrelid = 'risk_objects'::regclass
    ) THEN
        ALTER TABLE risk_objects
            ADD CONSTRAINT fk_risk_objects_zone
            FOREIGN KEY (zone_id) REFERENCES risk_zones(id) ON DELETE RESTRICT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_rz_floor ON risk_zones(floor_id);
CREATE INDEX IF NOT EXISTS idx_ro_floor ON risk_objects(floor_id);

UPDATE risk_zones rz
SET floor_plan_polygon = jsonb_build_object(
    'version', 2,
    'color_source', 'auto',
    'color', NULL::text,
    'polygons', jsonb_build_array(
        jsonb_build_object(
            'id', rz.id::text,
            'label', rz.name,
            'points', rz.floor_plan_polygon->'points'
        )
    )
)
WHERE rz.floor_plan_polygon IS NOT NULL
  AND rz.floor_plan_polygon ? 'points'
  AND NOT (rz.floor_plan_polygon ? 'version');

COMMIT;
```

- [ ] **步骤 1.2：新增 ORM 模型**

在 `backend/app/models/enterprise.py` 的 `RiskSource` 类之前新增：

```python
class EnterpriseFloor(Base):
    __tablename__ = "enterprise_floors"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    floor_plan_url: Mapped[Optional[str]] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text)
    canvas_width: Mapped[Optional[int]] = mapped_column(Integer)
    canvas_height: Mapped[Optional[int]] = mapped_column(Integer)
    canvas_texts: Mapped[list] = mapped_column(JSONB, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

在 `backend/app/models/risk_management.py` 中：

```python
class RiskZone(Base):
    ...
    floor_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprise_floors.id", ondelete="RESTRICT"), nullable=False, index=True)
    floor = relationship("EnterpriseFloor", lazy="selectin")

class RiskObject(Base):
    ...
    floor_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprise_floors.id", ondelete="RESTRICT"), nullable=True, index=True)
    zone_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("risk_zones.id", ondelete="RESTRICT"), nullable=True)
    floor = relationship("EnterpriseFloor", lazy="selectin")
```

同时从 `backend/app/models/enterprise.py` 导入 `EnterpriseFloor` 到 `risk_management.py`：

```python
from app.models.enterprise import EnterpriseFloor
```

- [ ] **步骤 1.3：编写迁移元数据测试**

创建 `backend/tests/test_risk_mapping_migration.py`：

```python
from app.models.enterprise import EnterpriseFloor
from app.models.risk_management import RiskZone, RiskObject

def test_enterprise_floor_columns():
    cols = {c.name for c in EnterpriseFloor.__table__.columns}
    assert {"enterprise_id", "name", "sort_order", "floor_plan_url", "canvas_width", "canvas_height", "canvas_texts", "is_default"} <= cols

def test_risk_floor_columns():
    zone_cols = {c.name for c in RiskZone.__table__.columns}
    object_cols = {c.name for c in RiskObject.__table__.columns}
    assert "floor_id" in zone_cols
    assert "floor_id" in object_cols

def test_zone_object_fk_restrict():
    fk = next(f for f in RiskObject.__table__.foreign_keys if f.parent.name == "zone_id")
    assert fk.ondelete == "RESTRICT"
```

- [ ] **步骤 1.4：运行测试**

运行：`cd backend && python -m pytest tests/test_risk_mapping_migration.py -v`

预期：3 个测试全部 PASS。

- [ ] **步骤 1.5：Commit**

```bash
git add backend/db_migration_risk_mapping_workbench.sql backend/app/models/enterprise.py backend/app/models/risk_management.py backend/tests/test_risk_mapping_migration.py
git commit -m "feat(risk-mapping): add floor model and workbench migration baseline"
```

---

## 任务 2：后端服务纯函数与 Schema

**文件：**
- 创建：`backend/app/services/risk_mapping_service.py`
- 创建：`backend/tests/test_risk_mapping_service.py`
- 修改：`backend/app/schemas/risk_management.py`

- [ ] **步骤 2.1：创建服务文件**

创建 `backend/app/services/risk_mapping_service.py`：

```python
from typing import Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent, RiskMeasure
from app.models.enterprise import EnterpriseFloor

LEVEL_ORDER = {"未评估": 0, "低": 1, "一般": 2, "较大": 3, "重大": 4}
LEVEL_COLORS = {
    "重大": "#ff4d4f",
    "较大": "#fa8c16",
    "一般": "#fadb14",
    "低": "#52c41a",
    "未评估": "#d9d9d9",
}

def normalize_polygon(raw: dict | None, zone_name: str = "") -> dict | None:
    if not raw:
        return None
    if raw.get("version") == 2:
        return raw
    points = raw.get("points") or []
    return {
        "version": 2,
        "color_source": "auto",
        "color": None,
        "polygons": [{
            "id": raw.get("id") or "legacy-polygon",
            "label": raw.get("label") or zone_name,
            "points": points,
        }],
    }

def validate_polygon_v2(polygon: dict | None) -> list[str]:
    errors: list[str] = []
    if not polygon:
        return ["floor_plan_polygon 不能为空"]
    if polygon.get("version") != 2:
        errors.append("version 必须为 2")
    if polygon.get("color_source") not in ("auto", "manual"):
        errors.append("color_source 必须为 auto 或 manual")
    if polygon.get("color_source") == "manual" and not isinstance(polygon.get("color"), str):
        errors.append("manual 模式必须提供 color")
    polygons = polygon.get("polygons") or []
    if not isinstance(polygons, list) or not polygons:
        errors.append("polygons 不能为空")
    ids = []
    for p in polygons:
        pts = p.get("points") or []
        if len(pts) < 3:
            errors.append("每个区域至少 3 个顶点")
        for pt in pts:
            if not isinstance(pt.get("x"), (int, float)) or not isinstance(pt.get("y"), (int, float)):
                errors.append("坐标必须是数值")
            elif not (0 <= pt["x"] <= 100 and 0 <= pt["y"] <= 100):
                errors.append("坐标必须在 0-100 范围内")
        ids.append(p.get("id"))
    if len(ids) != len(set(ids)):
        errors.append("polygons.id 不能重复")
    return errors

def effective_color(polygon: dict | Any | None, max_level: str | None) -> str:
    data = polygon.model_dump() if polygon and hasattr(polygon, "model_dump") else polygon
    if data and data.get("color_source") == "manual":
        return data.get("color") or LEVEL_COLORS.get(max_level or "未评估") or "#d9d9d9"
    return LEVEL_COLORS.get(max_level or "未评估", "#d9d9d9")

def max_risk_level(zone: RiskZone) -> str:
    level = "未评估"
    for obj in zone.objects:
        for ev in obj.events:
            if ev.risk_level and LEVEL_ORDER.get(ev.risk_level, 0) > LEVEL_ORDER.get(level, 0):
                level = ev.risk_level
        for unit in obj.units:
            for ev in unit.events:
                if ev.risk_level and LEVEL_ORDER.get(ev.risk_level, 0) > LEVEL_ORDER.get(level, 0):
                    level = ev.risk_level
    return level

async def ensure_default_floor(db: AsyncSession, enterprise_id: str) -> EnterpriseFloor:
    floor = (await db.execute(
        select(EnterpriseFloor).where(EnterpriseFloor.enterprise_id == enterprise_id, EnterpriseFloor.is_default.is_(True))
    )).scalar_one_or_none()
    if floor:
        return floor
    floor = EnterpriseFloor(
        enterprise_id=enterprise_id,
        name="默认总图",
        sort_order=0,
        floor_plan_url=None,
        is_default=True,
    )
    db.add(floor)
    await db.flush()
    return floor

async def cascade_counts(db: AsyncSession, zone_id: str) -> dict[str, int]:
    object_ids = (await db.execute(select(RiskObject.id).where(RiskObject.zone_id == zone_id))).scalars().all()
    object_count = len(object_ids)
    unit_count = 0
    event_count = 0
    measure_count = 0
    if object_ids:
        unit_ids = (await db.execute(select(RiskUnit.id).where(RiskUnit.object_id.in_(object_ids)))).scalars().all()
        unit_count = len(unit_ids)
        event_filters = [RiskEvent.object_id.in_(object_ids)]
        if unit_ids:
            event_filters.append(RiskEvent.unit_id.in_(unit_ids))
        from sqlalchemy import or_
        event_ids = (await db.execute(select(RiskEvent.id).where(or_(*event_filters)))).scalars().all()
        event_count = len(event_ids)
        if event_ids:
            measure_count = (await db.execute(select(func.count(RiskMeasure.id)).where(RiskMeasure.event_id.in_(event_ids)))).scalar() or 0
    return {
        "object_count": object_count,
        "unit_count": unit_count,
        "event_count": event_count,
        "measure_count": measure_count,
    }
```

- [ ] **步骤 2.2：扩展 Schema**

在 `backend/app/schemas/risk_management.py` 新增：

```python
from pydantic import field_validator, model_validator

class FloorCreate(BaseModel):
    name: str
    sort_order: int = 0
    floor_plan_url: str | None = None
    description: str | None = None
    canvas_width: int | None = None
    canvas_height: int | None = None
    canvas_texts: list[dict] = []
    is_default: bool = False

class FloorUpdate(BaseModel):
    name: str | None = None
    sort_order: int | None = None
    floor_plan_url: str | None = None
    description: str | None = None
    canvas_width: int | None = None
    canvas_height: int | None = None
    canvas_texts: list[dict] | None = None
    is_default: bool | None = None

class FloorResponse(BaseModel):
    id: str
    enterprise_id: str
    name: str
    sort_order: int
    floor_plan_url: str | None
    description: str | None
    canvas_width: int | None
    canvas_height: int | None
    canvas_texts: list[dict]
    is_default: bool
    zone_count: int = 0
    risk_point_count: int = 0
    created_at: DatetimeStr
    updated_at: DatetimeStr
    model_config = {"from_attributes": True}

class RiskPolygonPoint(BaseModel):
    x: float
    y: float

    @field_validator("x", "y")
    @classmethod
    def check_range(cls, v: float):
        if not (0 <= v <= 100):
            raise ValueError("坐标范围 0-100")
        return v

class RiskPolygon(BaseModel):
    id: str
    label: str | None = None
    points: list[RiskPolygonPoint]

class RiskZoneFloorPlanPolygon(BaseModel):
    version: int = 2
    color_source: str
    color: str | None = None
    polygons: list[RiskPolygon]

class RiskCanvasText(BaseModel):
    id: str
    content: str
    x: float
    y: float
    font_size: int = 14
    color: str = "#333333"
    rotation: int = 0
    sort_order: int = 0
```

同时把现有 Schema 扩展为：

```python
class RiskZoneCreate(BaseModel):
    floor_id: str | None = None
    name: str
    description: str | None = None
    sort_order: int = 0
    floor_plan_polygon: RiskZoneFloorPlanPolygon | None = None

class RiskZoneUpdate(BaseModel):
    floor_id: str | None = None
    name: str | None = None
    description: str | None = None
    sort_order: int | None = None
    floor_plan_polygon: RiskZoneFloorPlanPolygon | None = None

class RiskZoneResponse(BaseModel):
    id: str
    enterprise_id: str
    floor_id: str | None
    floor_name: str | None = None
    name: str
    description: str | None
    sort_order: int
    floor_plan_polygon: RiskZoneFloorPlanPolygon | None
    max_risk_level: str | None = None
    effective_color: str | None = None
    object_count: int = 0
    created_at: DatetimeStr
    updated_at: DatetimeStr
    model_config = {"from_attributes": True}

class RiskObjectCreate(BaseModel):
    zone_id: str | None = None
    floor_id: str | None = None
    name: str
    category: str | None = None
    location: str | None = None
    location_x: float | None = None
    location_y: float | None = None
    description: str | None = None
    image_url: str | None = None
    is_risk_point: bool = False
    sort_order: int = 0

    @model_validator(mode="after")
    def validate_risk_point(self):
        if self.is_risk_point and (not self.zone_id or self.location_x is None or self.location_y is None):
            raise ValueError("风险点必须绑定分区和坐标")
        return self

class RiskObjectUpdate(BaseModel):
    zone_id: str | None = None
    floor_id: str | None = None
    name: str | None = None
    category: str | None = None
    location: str | None = None
    location_x: float | None = None
    location_y: float | None = None
    description: str | None = None
    image_url: str | None = None
    is_risk_point: bool | None = None
    sort_order: int | None = None

class RiskObjectResponse(BaseModel):
    id: str
    enterprise_id: str
    zone_id: str | None
    floor_id: str | None
    name: str
    category: str | None
    location: str | None
    location_x: float | None
    location_y: float | None
    description: str | None
    image_url: str | None
    is_risk_point: bool
    sort_order: int
    created_at: DatetimeStr
    updated_at: DatetimeStr
    unit_count: int = 0
    model_config = {"from_attributes": True}
```

新增批量保存与总览 Schema：

```python
class BatchSaveZoneItem(BaseModel):
    client_id: str | None = None
    zone_id: str | None = None
    name: str | None = None
    description: str | None = None
    sort_order: int = 0
    updated_at: DatetimeStr | None = None
    floor_plan_polygon: RiskZoneFloorPlanPolygon

class BatchSaveRiskPointItem(BaseModel):
    client_id: str | None = None
    id: str | None = None
    name: str | None = None
    category: str | None = None
    description: str | None = None
    zone_id: str | None = None
    zone_client_id: str | None = None
    floor_id: str | None = None
    location_x: float
    location_y: float
    updated_at: DatetimeStr | None = None

class BatchSaveRequest(BaseModel):
    floor_id: str
    floor_updated_at: DatetimeStr
    zones: list[BatchSaveZoneItem]
    risk_points: list[BatchSaveRiskPointItem] = []
    deleted_risk_point_ids: list[str] = []
    deleted_zone_ids: list[str] = []
    confirm_cascade_zone_ids: list[str] = []
    texts: list[RiskCanvasText] = []

class BatchSaveResponse(BaseModel):
    floor: FloorResponse
    zones: list[RiskZoneResponse]
    risk_points: list[RiskObjectResponse]
    texts: list[RiskCanvasText]
    created_zone_map: dict[str, str] = {}
    created_risk_point_map: dict[str, str] = {}

class WorkbenchZone(RiskZoneResponse):
    objects: list[RiskObjectResponse] = []

class WorkbenchResponse(BaseModel):
    floors: list[FloorResponse]
    current_floor_id: str
    zones: list[WorkbenchZone]
    risk_points: list[RiskObjectResponse]
    texts: list[RiskCanvasText]

class OverviewResponse(BaseModel):
    floor: FloorResponse
    zones: list[WorkbenchZone]
    risk_points: list[RiskObjectResponse]
```

- [ ] **步骤 2.3：编写服务测试**

创建 `backend/tests/test_risk_mapping_service.py`：

```python
from app.services.risk_mapping_service import normalize_polygon, validate_polygon_v2, effective_color

def test_normalize_legacy_points():
    result = normalize_polygon({"points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}]}, "原料库")
    assert result["version"] == 2
    assert result["polygons"][0]["label"] == "原料库"
    assert result["polygons"][0]["points"][0]["x"] == 1

def test_validate_polygon_rejects_bad_coordinates():
    errors = validate_polygon_v2({
        "version": 2,
        "color_source": "manual",
        "color": "#ff4d4f",
        "polygons": [{"id": "p1", "points": [{"x": 10, "y": 10}, {"x": 20, "y": 20}, {"x": 30, "y": 101}]}],
    })
    assert any("0-100" in e for e in errors)

def test_manual_color_wins():
    color = effective_color({"version": 2, "color_source": "manual", "color": "#123456", "polygons": []}, "重大")
    assert color == "#123456"
```

- [ ] **步骤 2.4：运行测试**

运行：`cd backend && python -m pytest tests/test_risk_mapping_service.py tests/test_risk_mapping_migration.py -v`

预期：全部 PASS。

- [ ] **步骤 2.5：Commit**

```bash
git add backend/app/services/risk_mapping_service.py backend/app/schemas/risk_management.py backend/tests/test_risk_mapping_service.py
git commit -m "feat(risk-mapping): add workbench schemas and geometry service"
```

---

## 任务 3：Floors CRUD、平面图上传与企业清理

**文件：**
- 创建：`backend/app/services/floor_plan_storage_service.py`
- 创建：`backend/app/services/enterprise_cleanup_service.py`
- 创建：`backend/tests/test_floor_plan_upload.py`
- 创建：`backend/tests/test_risk_mapping_cascade.py`
- 修改：`backend/requirements.txt`
- 修改：`backend/app/routers/risk_management.py`
- 修改：`backend/app/routers/enterprises.py`

- [ ] **步骤 3.1：增加依赖**

在 `backend/requirements.txt` 末尾追加：

```text
Pillow>=10.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

运行：`cd backend && pip install -r requirements.txt`

- [ ] **步骤 3.2：创建平面图存储服务**

创建 `backend/app/services/floor_plan_storage_service.py`：

```python
import os, uuid
from datetime import datetime
from pathlib import Path
from fastapi import UploadFile, HTTPException
from PIL import Image
from app.config import settings

UPLOAD_DIR = Path(settings.UPLOAD_DIR if hasattr(settings, "UPLOAD_DIR") else Path(__file__).resolve().parents[2] / "uploads")
ALLOWED = {"image/png", "image/jpeg", "image/webp"}
MAX_BYTES = 20 * 1024 * 1024
MAX_PIXEL = 12000

async def save_floor_plan(enterprise_id: str, floor_id: str, file: UploadFile) -> tuple[str, int, int]:
    if file.content_type not in ALLOWED:
        raise HTTPException(422, "仅支持 PNG/JPEG/WebP 图片")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(422, "文件不能超过 20MB")
    ext = os.path.splitext(file.filename or "image.png")[1].lower() or ".png"
    target_dir = UPLOAD_DIR / "enterprises" / enterprise_id / "floors" / floor_id
    target_dir.mkdir(parents=True, exist_ok=True)
    name = f"{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex}{ext}"
    target = target_dir / name
    try:
        target.write_bytes(data)
        with Image.open(target) as img:
            width, height = img.size
        if width > MAX_PIXEL or height > MAX_PIXEL:
            raise HTTPException(422, "图片像素不能超过 12000x12000")
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    except Exception:
        target.unlink(missing_ok=True)
        raise HTTPException(422, "无法读取图片尺寸")
    return f"/uploads/enterprises/{enterprise_id}/floors/{floor_id}/{name}", width, height

def remove_floor_plan(url: str | None):
    if not url or not url.startswith("/uploads/"):
        return
    rel = url.removeprefix("/uploads/")
    try:
        (UPLOAD_DIR / rel).unlink(missing_ok=True)
    except OSError:
        pass
```

如果 `app.config.settings` 没有 `UPLOAD_DIR`，则保持使用路径兜底，不引入配置变更。

- [ ] **步骤 3.3：在路由中新增 Floors CRUD**

在 `backend/app/routers/risk_management.py` 的 imports 增加：

```python
from app.models.enterprise import Enterprise, EnterpriseFloor
from app.schemas.risk_management import FloorCreate, FloorUpdate, FloorResponse, RiskZoneFloorPlanPolygon
from app.services.floor_plan_storage_service import save_floor_plan, remove_floor_plan
```

在 Zones 区段之前新增：

```python
async def _default_floor(db, enterprise_id):
    floor = (await db.execute(select(EnterpriseFloor).where(
        EnterpriseFloor.enterprise_id == enterprise_id,
        EnterpriseFloor.is_default.is_(True)
    ))).scalar_one_or_none()
    if not floor:
        floor = EnterpriseFloor(enterprise_id=enterprise_id, name="默认总图", is_default=True)
        db.add(floor)
        await db.flush()
    return floor

async def _floor_response(db, floor):
    zone_count = (await db.execute(select(func.count(RiskZone.id)).where(RiskZone.floor_id == floor.id))).scalar() or 0
    risk_point_count = (await db.execute(select(func.count(RiskObject.id)).where(RiskObject.floor_id == floor.id, RiskObject.is_risk_point.is_(True)))).scalar() or 0
    resp = FloorResponse.model_validate(floor)
    resp.zone_count = zone_count
    resp.risk_point_count = risk_point_count
    return resp

@router.get("/floors", response_model=ApiResponse[list[FloorResponse]])
async def list_floors(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floor = await _default_floor(db, enterprise_id)
    await db.commit()
    floors = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.enterprise_id == enterprise_id).order_by(EnterpriseFloor.sort_order))).scalars().all()
    return ApiResponse(data=[await _floor_response(db, f) for f in floors])

@router.post("/floors", response_model=ApiResponse[FloorResponse], status_code=201)
async def create_floor(body: FloorCreate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    exists = (await db.execute(select(EnterpriseFloor.id).where(EnterpriseFloor.enterprise_id == enterprise_id, EnterpriseFloor.name == body.name))).first()
    if exists:
        raise HTTPException(409, "楼层名称已存在")
    if not body.is_default:
        has_default = (await db.execute(select(func.count(EnterpriseFloor.id)).where(EnterpriseFloor.enterprise_id == enterprise_id, EnterpriseFloor.is_default.is_(True)))).scalar() or 0
        body.is_default = has_default == 0
    floor = EnterpriseFloor(enterprise_id=enterprise_id, **body.model_dump(exclude_unset=True))
    if body.is_default:
        await db.execute(update(EnterpriseFloor).where(EnterpriseFloor.enterprise_id == enterprise_id).values(is_default=False))
    db.add(floor)
    await db.commit()
    await db.refresh(floor)
    return ApiResponse(data=await _floor_response(db, floor))

@router.put("/floors/{floor_id}", response_model=ApiResponse[FloorResponse])
async def update_floor(floor_id: str, body: FloorUpdate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floor = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.id == floor_id, EnterpriseFloor.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not floor:
        raise HTTPException(404, "楼层不存在")
    if body.is_default is False and floor.is_default:
        default_count = (await db.execute(select(func.count(EnterpriseFloor.id)).where(EnterpriseFloor.enterprise_id == enterprise_id, EnterpriseFloor.is_default.is_(True)))).scalar() or 0
        if default_count <= 1:
            raise HTTPException(409, "企业必须保留一个默认楼层")
    if body.is_default:
        await db.execute(update(EnterpriseFloor).where(EnterpriseFloor.enterprise_id == enterprise_id).values(is_default=False))
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(floor, k, v)
    if floor.is_default and floor.floor_plan_url:
        ent = (await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))).scalar_one()
        ent.floor_plan_url = floor.floor_plan_url
    await db.commit()
    await db.refresh(floor)
    return ApiResponse(data=await _floor_response(db, floor))

@router.delete("/floors/{floor_id}")
async def delete_floor(floor_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floor = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.id == floor_id, EnterpriseFloor.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not floor:
        raise HTTPException(404, "楼层不存在")
    zone_count = (await db.execute(select(func.count(RiskZone.id)).where(RiskZone.floor_id == floor_id))).scalar() or 0
    object_count = (await db.execute(select(func.count(RiskObject.id)).where(RiskObject.floor_id == floor_id))).scalar() or 0
    if zone_count or object_count:
        raise HTTPException(409, "楼层存在分区或风险对象，不允许删除")
    if floor.is_default and (await db.execute(select(func.count(EnterpriseFloor.id)).where(EnterpriseFloor.enterprise_id == enterprise_id))).scalar() == 1:
        raise HTTPException(409, "唯一默认楼层不可删除")
    await db.delete(floor)
    await db.commit()
    return ApiResponse(message="已删除")

@router.post("/floors/{floor_id}/plan", response_model=ApiResponse[FloorResponse])
async def upload_floor_plan(floor_id: str, enterprise_id: str, file: UploadFile = File(...), current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floor = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.id == floor_id, EnterpriseFloor.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not floor:
        raise HTTPException(404, "楼层不存在")
    old_url = floor.floor_plan_url
    url, width, height = await save_floor_plan(enterprise_id, floor_id, file)
    floor.floor_plan_url = url
    floor.canvas_width = width
    floor.canvas_height = height
    if floor.is_default:
        ent = (await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))).scalar_one()
        ent.floor_plan_url = url
    await db.commit()
    remove_floor_plan(old_url)
    await db.refresh(floor)
    return ApiResponse(data=await _floor_response(db, floor))
```

注意导入 `update`：`from sqlalchemy import select, func, update`。

- [ ] **步骤 3.4：企业清理服务**

创建 `backend/app/services/enterprise_cleanup_service.py`：

```python
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enterprise import Enterprise, EnterpriseFloor
from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent, RiskMeasure

async def delete_enterprise_risk_mapping(db: AsyncSession, enterprise_id: str):
    object_ids = (await db.execute(select(RiskObject.id).where(RiskObject.enterprise_id == enterprise_id))).scalars().all()
    zone_ids = (await db.execute(select(RiskZone.id).where(RiskZone.enterprise_id == enterprise_id))).scalars().all()
    if object_ids:
        await db.execute(delete(RiskMeasure).where(RiskMeasure.event_id.in_(select(RiskEvent.id).where(RiskEvent.object_id.in_(object_ids)))))
        await db.execute(delete(RiskEvent).where(RiskEvent.object_id.in_(object_ids)))
        await db.execute(delete(RiskUnit).where(RiskUnit.object_id.in_(object_ids)))
    await db.execute(delete(RiskObject).where(RiskObject.enterprise_id == enterprise_id))
    if zone_ids:
        await db.execute(delete(RiskZone).where(RiskZone.id.in_(zone_ids)))
    await db.execute(delete(EnterpriseFloor).where(EnterpriseFloor.enterprise_id == enterprise_id))

async def delete_enterprise_complete(db: AsyncSession, enterprise_id: str):
    await delete_enterprise_risk_mapping(db, enterprise_id)
    await db.execute(delete(Enterprise).where(Enterprise.id == enterprise_id))
```

修改 `backend/app/routers/enterprises.py` 的 `delete_enterprise`：

```python
from app.services.enterprise_cleanup_service import delete_enterprise_complete

@router.delete("/{enterprise_id}")
async def delete_enterprise(enterprise_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="企业不存在")
    await delete_enterprise_complete(db, enterprise_id)
    await db.commit()
    return {"code": 0, "message": "已删除"}
```

- [ ] **步骤 3.5：测试上传与级联**

创建 `backend/tests/test_floor_plan_upload.py`：

```python
from io import BytesIO
from fastapi import HTTPException
from app.services.floor_plan_storage_service import save_floor_plan

async def test_reject_non_image():
    class FakeUpload:
        content_type = "text/plain"
        filename = "a.txt"
        async def read(self):
            return b"x"
    try:
        await save_floor_plan("e", "f", FakeUpload())
        assert False
    except HTTPException as exc:
        assert exc.status_code == 422
```

创建 `backend/tests/test_risk_mapping_cascade.py`：

```python
from app.services.enterprise_cleanup_service import delete_enterprise_risk_mapping

def test_cleanup_service_imports():
    assert callable(delete_enterprise_risk_mapping)
```

- [ ] **步骤 3.6：运行测试**

运行：`cd backend && python -m pytest tests/test_floor_plan_upload.py tests/test_risk_mapping_cascade.py -v`

预期：全部 PASS。

- [ ] **步骤 3.7：Commit**

```bash
git add backend/requirements.txt backend/app/services/floor_plan_storage_service.py backend/app/services/enterprise_cleanup_service.py backend/app/routers/risk_management.py backend/app/routers/enterprises.py backend/tests
git commit -m "feat(risk-mapping): add floors CRUD, upload, and enterprise cleanup"
```

---

## 任务 4：Workbench 聚合加载、批量保存与总览

**文件：**
- 创建：`backend/tests/test_risk_mapping_workbench.py`
- 修改：`backend/app/routers/risk_management.py`

- [ ] **步骤 4.1：实现 Workbench 加载**

在 `backend/app/routers/risk_management.py` 的 `list_zones` 之前新增：

```python
from app.schemas.risk_management import WorkbenchResponse, WorkbenchZone, BatchSaveRequest, BatchSaveResponse, OverviewResponse
from app.services.risk_mapping_service import normalize_polygon, effective_color, max_risk_level, cascade_counts, validate_polygon_v2

@router.get("/workbench", response_model=ApiResponse[WorkbenchResponse])
async def load_workbench(enterprise_id: str, floor_id: str | None = Query(None), current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floor = await _default_floor(db, enterprise_id)
    if not floor_id:
        floor_id = floor.id
    current = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.id == floor_id, EnterpriseFloor.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not current:
        raise HTTPException(404, "楼层不存在")
    await db.commit()
    floors = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.enterprise_id == enterprise_id).order_by(EnterpriseFloor.sort_order))).scalars().all()
    zones = (await db.execute(
        select(RiskZone).where(RiskZone.enterprise_id == enterprise_id, RiskZone.floor_id == floor_id)
        .options(
            selectinload(RiskZone.objects).selectinload(RiskObject.events),
            selectinload(RiskZone.objects).selectinload(RiskObject.units).selectinload(RiskUnit.events),
        ).order_by(RiskZone.sort_order)
    )).scalars().all()
    risk_points = (await db.execute(
        select(RiskObject).where(RiskObject.enterprise_id == enterprise_id, RiskObject.floor_id == floor_id, RiskObject.is_risk_point.is_(True))
    )).scalars().all()
    zone_responses = []
    for z in zones:
        resp = RiskZoneResponse.model_validate(z)
        resp.floor_name = current.name
        resp.max_risk_level = max_risk_level(z)
        normalized = normalize_polygon(z.floor_plan_polygon, z.name)
        resp.floor_plan_polygon = RiskZoneFloorPlanPolygon.model_validate(normalized) if normalized else None
        resp.effective_color = effective_color(resp.floor_plan_polygon, resp.max_risk_level)
        zone_responses.append(WorkbenchZone(
            id=resp.id,
            enterprise_id=resp.enterprise_id,
            floor_id=resp.floor_id,
            floor_name=resp.floor_name,
            name=resp.name,
            description=resp.description,
            sort_order=resp.sort_order,
            floor_plan_polygon=resp.floor_plan_polygon,
            max_risk_level=resp.max_risk_level,
            effective_color=resp.effective_color,
            object_count=resp.object_count,
            created_at=resp.created_at,
            updated_at=resp.updated_at,
            objects=[RiskObjectResponse.model_validate(o) for o in z.objects],
        ))
    return ApiResponse(data=WorkbenchResponse(
        floors=[await _floor_response(db, f) for f in floors],
        current_floor_id=current.id,
        zones=zone_responses,
        risk_points=[RiskObjectResponse.model_validate(o) for o in risk_points],
        texts=current.canvas_texts or [],
    ))
```

若 `RiskZoneResponse.model_validate(z)` 与 `WorkbenchZone` 字段映射繁琐，优先保留该显式构造，避免 Pydantic 隐式字段不一致。

- [ ] **步骤 4.2：实现批量保存**

在 `load_workbench` 之后新增：

```python
def _same_ts(a, b):
    if not a or not b:
        return not a and not b
    from datetime import datetime, timezone
    def parse(v):
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(timezone.utc)
    return parse(a) == parse(b)

@router.post("/workbench/batch-save", response_model=ApiResponse[BatchSaveResponse])
async def batch_save_workbench(body: BatchSaveRequest, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floor = (await db.execute(
        select(EnterpriseFloor).where(EnterpriseFloor.id == body.floor_id, EnterpriseFloor.enterprise_id == enterprise_id).with_for_update()
    )).scalar_one_or_none()
    if not floor:
        raise HTTPException(404, "楼层不存在")
    if not _same_ts(floor.updated_at, body.floor_updated_at):
        raise HTTPException(409, detail={"code": "SAVE_CONFLICT", "message": "楼层数据已变更，请刷新"})

    client_ids = [z.client_id for z in body.zones if z.client_id] + [r.client_id for r in body.risk_points if r.client_id]
    if len(client_ids) != len(set(client_ids)):
        raise HTTPException(422, detail={"code": "INVALID_PAYLOAD", "message": "client_id 重复"})

    existing_zones = {z.id: z for z in (await db.execute(select(RiskZone).where(RiskZone.floor_id == floor.id).with_for_update())).scalars()}
    existing_points = {o.id: o for o in (await db.execute(select(RiskObject).where(RiskObject.floor_id == floor.id, RiskObject.is_risk_point.is_(True)).with_for_update())).scalars()}

    submitted_zone_ids = {item.zone_id for item in body.zones if item.zone_id}
    missing_zone_ids = set(existing_zones) - submitted_zone_ids - set(body.deleted_zone_ids)
    if missing_zone_ids:
        raise HTTPException(422, detail={"code": "ZONE_NOT_BOUND", "message": "当前楼层存在缺失分区", "data": {"missing_zone_ids": sorted(missing_zone_ids)}})

    created_zone_map: dict[str, str] = {}
    for item in body.zones:
        polygon_errors = validate_polygon_v2(item.floor_plan_polygon.model_dump())
        if polygon_errors:
            raise HTTPException(422, detail={"code": "POLYGON_INVALID", "message": "；".join(polygon_errors)})
        if item.zone_id:
            zone = existing_zones.get(item.zone_id)
            if not zone:
                raise HTTPException(404, detail={"code": "ZONE_NOT_FOUND", "message": "分区不存在"})
            if not _same_ts(zone.updated_at, item.updated_at):
                raise HTTPException(409, detail={"code": "SAVE_CONFLICT", "message": "分区已变更，请刷新"})
            zone.name = item.name or zone.name
            zone.description = item.description
            zone.sort_order = item.sort_order
            zone.floor_plan_polygon = item.floor_plan_polygon.model_dump()
        else:
            zone = RiskZone(
                enterprise_id=enterprise_id,
                floor_id=floor.id,
                name=item.name or "",
                description=item.description,
                sort_order=item.sort_order,
                floor_plan_polygon=item.floor_plan_polygon.model_dump(),
            )
            db.add(zone)
            await db.flush()
            if item.client_id:
                created_zone_map[item.client_id] = zone.id

    created_risk_point_map: dict[str, str] = {}
    for item in body.risk_points:
        target_zone_id = item.zone_id or created_zone_map.get(item.zone_client_id or "")
        if not target_zone_id:
            raise HTTPException(422, detail={"code": "ZONE_NOT_FOUND", "message": "风险点必须绑定分区"})
        if item.id:
            point = existing_points.get(item.id)
            if not point:
                raise HTTPException(404, detail={"code": "RISK_POINT_NOT_FOUND", "message": "风险点不存在"})
            if not _same_ts(point.updated_at, item.updated_at):
                raise HTTPException(409, detail={"code": "SAVE_CONFLICT", "message": "风险点已变更，请刷新"})
            point.zone_id = target_zone_id
            point.floor_id = floor.id
            point.location_x = item.location_x
            point.location_y = item.location_y
            point.name = item.name or point.name
            point.category = item.category
            point.description = item.description
        else:
            point = RiskObject(
                enterprise_id=enterprise_id,
                zone_id=target_zone_id,
                floor_id=floor.id,
                name=item.name or "",
                category=item.category,
                description=item.description,
                location_x=item.location_x,
                location_y=item.location_y,
                is_risk_point=True,
            )
            db.add(point)
            await db.flush()
            if item.client_id:
                created_risk_point_map[item.client_id] = point.id

    for pid in body.deleted_risk_point_ids:
        point = existing_points.get(pid)
        if point:
            await db.delete(point)

    for zid in body.deleted_zone_ids:
        zone = existing_zones.get(zid)
        if not zone:
            continue
        counts = await cascade_counts(db, zid)
        if counts["object_count"] and zid not in body.confirm_cascade_zone_ids:
            raise HTTPException(409, detail={"code": "CASCADE_CONFIRM_REQUIRED", "message": "删除分区需要确认", "data": counts})
        await db.delete(zone)

    floor.canvas_texts = [t.model_dump() for t in body.texts]
    await db.commit()

    saved_zones = (await db.execute(select(RiskZone).where(RiskZone.floor_id == floor.id).order_by(RiskZone.sort_order))).scalars().all()
    saved_points = (await db.execute(select(RiskObject).where(RiskObject.floor_id == floor.id, RiskObject.is_risk_point.is_(True)))).scalars().all()
    await db.refresh(floor)
    return ApiResponse(data=BatchSaveResponse(
        floor=await _floor_response(db, floor),
        zones=[RiskZoneResponse.model_validate(z) for z in saved_zones],
        risk_points=[RiskObjectResponse.model_validate(o) for o in saved_points],
        texts=floor.canvas_texts or [],
        created_zone_map=created_zone_map,
        created_risk_point_map=created_risk_point_map,
    ))
```

说明：`updated_at` 比较统一使用上面的 `_same_ts`，避免时区偏移导致误判。

- [ ] **步骤 4.3：实现 Overview 与 Hierarchy 扩展**

在 `risk_management.py` 新增：

```python
@router.get("/overview", response_model=ApiResponse[OverviewResponse])
async def get_overview(enterprise_id: str, floor_id: str | None = Query(None), current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    default = await _default_floor(db, enterprise_id)
    current = default if not floor_id else (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.id == floor_id, EnterpriseFloor.enterprise_id == enterprise_id))).scalar_one()
    await db.commit()
    zones = (await db.execute(select(RiskZone).where(RiskZone.floor_id == current.id).options(selectinload(RiskZone.objects)))).scalars().all()
    points = (await db.execute(select(RiskObject).where(RiskObject.floor_id == current.id, RiskObject.is_risk_point.is_(True)))).scalars().all()
    return ApiResponse(data=OverviewResponse(
        floor=await _floor_response(db, current),
        zones=[_to_workbench_zone(z, current) for z in zones],
        risk_points=[RiskObjectResponse.model_validate(o) for o in points],
    ))
```

修改 `GET /hierarchy`，增加 `floor_id` 过滤，并让 `HierarchyZoneResponse`/`HierarchyObjectResponse` 包含 `floor_id`、`floor_name`、`floor_plan_polygon`、`max_risk_level`、`effective_color`、`location_x`、`location_y`。

- [ ] **步骤 4.4：修改既有 CRUD 兼容**

修改现有 `create_zone`：

```python
@router.post("/zones", response_model=ApiResponse[RiskZoneResponse], status_code=201)
async def create_zone(body: RiskZoneCreate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    if body.floor_id:
        floor = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.id == body.floor_id, EnterpriseFloor.enterprise_id == enterprise_id))).scalar_one_or_none()
        if not floor:
            raise HTTPException(404, "楼层不存在")
    else:
        floor = await _default_floor(db, enterprise_id)
    z = RiskZone(enterprise_id=enterprise_id, floor_id=floor.id, **body.model_dump(exclude_unset=True, exclude={"floor_id"}))
    db.add(z)
    await db.commit()
    await db.refresh(z)
    return ApiResponse(data=RiskZoneResponse.model_validate(z))
```

修改 `update_zone`，在保存前处理楼层移动：

```python
@router.put("/zones/{zone_id}", response_model=ApiResponse[RiskZoneResponse])
async def update_zone(zone_id: str, body: RiskZoneUpdate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    z = (await db.execute(select(RiskZone).where(RiskZone.id == zone_id, RiskZone.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not z:
        raise HTTPException(404, "分区不存在")
    values = body.model_dump(exclude_unset=True)
    new_floor_id = values.pop("floor_id", None)
    if new_floor_id is not None and new_floor_id != z.floor_id:
        floor = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.id == new_floor_id, EnterpriseFloor.enterprise_id == enterprise_id))).scalar_one_or_none()
        if not floor:
            raise HTTPException(404, "楼层不存在")
        z.floor_id = new_floor_id
        await db.execute(update(RiskObject).where(RiskObject.zone_id == z.id).values(floor_id=new_floor_id))
    for k, v in values.items():
        setattr(z, k, v)
    await db.commit()
    await db.refresh(z)
    return ApiResponse(data=RiskZoneResponse.model_validate(z))
```

修改 `create_object`，让 `floor_id` 缺省时沿用分区：

```python
@router.post("/objects", response_model=ApiResponse[RiskObjectResponse], status_code=201)
async def create_object(body: RiskObjectCreate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floor_id = body.floor_id
    if not floor_id and body.zone_id:
        zone = (await db.execute(select(RiskZone).where(RiskZone.id == body.zone_id, RiskZone.enterprise_id == enterprise_id))).scalar_one_or_none()
        if not zone:
            raise HTTPException(404, "分区不存在")
        floor_id = zone.floor_id
    if body.is_risk_point and (not body.zone_id or body.location_x is None or body.location_y is None):
        raise HTTPException(422, "风险点必须绑定分区和坐标")
    o = RiskObject(enterprise_id=enterprise_id, floor_id=floor_id, **body.model_dump(exclude_unset=True, exclude={"floor_id"}))
    db.add(o)
    await db.commit()
    await db.refresh(o)
    return ApiResponse(data=RiskObjectResponse.model_validate(o))
```

`RiskZoneUpdate` 与 `RiskObjectUpdate` 的 Schema 需要补 `floor_id` 字段。

- [ ] **步骤 4.5：编写工作台 Schema 测试**

创建 `backend/tests/test_risk_mapping_workbench.py`：

```python
from app.schemas.risk_management import (
    BatchSaveRequest,
    BatchSaveZoneItem,
    RiskPolygon,
    RiskPolygonPoint,
    RiskZoneFloorPlanPolygon,
)

def test_batch_save_schema_accepts_v2_polygon():
    polygon = RiskZoneFloorPlanPolygon(
        version=2,
        color_source="auto",
        color=None,
        polygons=[RiskPolygon(
            id="p1",
            label="原料库",
            points=[
                RiskPolygonPoint(x=10, y=10),
                RiskPolygonPoint(x=30, y=10),
                RiskPolygonPoint(x=30, y=40),
            ],
        )],
    )
    payload = BatchSaveRequest(
        floor_id="floor-1",
        floor_updated_at="2026-08-04T10:00:00+08:00",
        zones=[BatchSaveZoneItem(zone_id="zone-1", updated_at="2026-08-04T10:00:00+08:00", floor_plan_polygon=polygon)],
    )
    assert payload.floor_id == "floor-1"
    assert payload.zones[0].floor_plan_polygon.polygons[0].points[0].x == 10
```

运行：`cd backend && python -m pytest tests/test_risk_mapping_workbench.py -v`

预期：1 个测试 PASS。

- [ ] **步骤 4.6：API 冒烟验证**

启动后端：

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

用现有登录接口取得 token 后执行：

```powershell
$h = @{ Authorization = "Bearer $token" }
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/v1/enterprises/$eid/risk-management/floors" -Headers $h
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/v1/enterprises/$eid/risk-management/workbench" -Headers $h
```

预期：返回默认楼层与空工作台数据，HTTP 200。

- [ ] **步骤 4.7：Commit**

```bash
git add backend/app/routers/risk_management.py backend/app/schemas/risk_management.py backend/tests/test_risk_mapping_workbench.py
git commit -m "feat(risk-mapping): add workbench load, batch save, and overview APIs"
```

---

## 任务 5：前端类型、服务与路由

**文件：**
- 创建：`frontend/src/types/riskMappingWorkbench.ts`
- 创建：`frontend/src/services/riskMappingWorkbenchService.ts`
- 修改：`frontend/src/types/riskManagement.ts`
- 修改：`frontend/src/types/enterprise.ts`
- 修改：`frontend/src/services/riskManagementService.ts`
- 修改：`frontend/src/routes/index.tsx`

- [ ] **步骤 5.1：创建工作台类型**

创建 `frontend/src/types/riskMappingWorkbench.ts`：

```ts
export type RiskLevel = "重大" | "较大" | "一般" | "低" | "未评估";
export type ColorSource = "auto" | "manual";

export interface RiskPolygonPoint { x: number; y: number }
export interface RiskPolygon { id: string; label?: string; points: RiskPolygonPoint[] }
export interface RiskZoneFloorPlanPolygon {
  version: 2;
  color_source: ColorSource;
  color: string | null;
  polygons: RiskPolygon[];
}
export interface RiskCanvasText {
  id: string;
  content: string;
  x: number;
  y: number;
  font_size: number;
  color: string;
  rotation: number;
  sort_order: number;
}
export interface EnterpriseFloor {
  id: string;
  enterprise_id: string;
  name: string;
  sort_order: number;
  floor_plan_url: string | null;
  description?: string | null;
  canvas_width?: number | null;
  canvas_height?: number | null;
  canvas_texts: RiskCanvasText[];
  is_default: boolean;
  zone_count?: number;
  risk_point_count?: number;
  updated_at: string;
}
export interface WorkbenchZone {
  id: string;
  enterprise_id: string;
  floor_id: string;
  floor_name: string;
  name: string;
  description: string | null;
  sort_order: number;
  floor_plan_polygon: RiskZoneFloorPlanPolygon | null;
  max_risk_level: RiskLevel | null;
  effective_color: string | null;
  object_count: number;
  created_at: string;
  updated_at: string;
  objects?: import("@/types/riskManagement").RiskObject[];
}
export interface PendingRegion {
  id: string;
  floor_id: string;
  points: RiskPolygonPoint[];
  created_at: string;
}
export interface WorkbenchSnapshot {
  floors: EnterpriseFloor[];
  currentFloorId: string;
  zones: WorkbenchZone[];
  riskPoints: import("@/types/riskManagement").RiskObject[];
  texts: RiskCanvasText[];
  pendingRegions: PendingRegion[];
}
export interface RawWorkbenchSnapshot {
  floors: EnterpriseFloor[];
  current_floor_id: string;
  zones: WorkbenchZone[];
  risk_points: import("@/types/riskManagement").RiskObject[];
  texts: RiskCanvasText[];
  pending_regions?: PendingRegion[];
}
export interface RawOverviewResponse {
  floor: EnterpriseFloor;
  zones: WorkbenchZone[];
  risk_points: import("@/types/riskManagement").RiskObject[];
}
export interface BatchSaveZoneItem {
  client_id?: string;
  zone_id?: string | null;
  name?: string;
  description?: string;
  sort_order?: number;
  updated_at?: string | null;
  floor_plan_polygon: RiskZoneFloorPlanPolygon;
}
export interface BatchSaveRiskPointItem {
  client_id?: string;
  id?: string | null;
  name?: string;
  category?: string;
  description?: string;
  zone_id?: string | null;
  zone_client_id?: string | null;
  floor_id?: string | null;
  location_x: number;
  location_y: number;
  updated_at?: string | null;
}
export interface BatchSavePayload {
  floor_id: string;
  floor_updated_at: string;
  zones: BatchSaveZoneItem[];
  risk_points: BatchSaveRiskPointItem[];
  deleted_risk_point_ids: string[];
  deleted_zone_ids: string[];
  confirm_cascade_zone_ids: string[];
  texts: RiskCanvasText[];
}
export interface BatchSaveResponse {
  floor: EnterpriseFloor;
  zones: WorkbenchZone[];
  risk_points: import("@/types/riskManagement").RiskObject[];
  texts: RiskCanvasText[];
  created_zone_map: Record<string, string>;
  created_risk_point_map: Record<string, string>;
}
```

- [ ] **步骤 5.2：创建服务**

创建 `frontend/src/services/riskMappingWorkbenchService.ts`：

```ts
import api from "./api";
import type { ApiResponse } from "@/types/common";
import type { RawWorkbenchSnapshot, RawOverviewResponse, BatchSavePayload, BatchSaveResponse, EnterpriseFloor } from "@/types/riskMappingWorkbench";

const BASE = (eid: string) => `/enterprises/${eid}/risk-management`;

export const getRiskMappingWorkbench = (eid: string, floorId?: string) =>
  api.get<ApiResponse<RawWorkbenchSnapshot>>(`${BASE(eid)}/workbench`, { params: floorId ? { floor_id: floorId } : {} }).then(r => {
    const d = r.data.data;
    return {
      floors: d.floors,
      currentFloorId: d.current_floor_id,
      zones: d.zones,
      riskPoints: d.risk_points,
      texts: d.texts,
      pendingRegions: d.pendingRegions ?? [],
    };
  });

export const saveRiskMappingWorkbench = (eid: string, payload: BatchSavePayload) =>
  api.post<ApiResponse<BatchSaveResponse>>(`${BASE(eid)}/workbench/batch-save`, payload).then(r => r.data.data);

export const listEnterpriseFloors = (eid: string) =>
  api.get<ApiResponse<EnterpriseFloor[]>>(`${BASE(eid)}/floors`).then(r => r.data.data);

export const createEnterpriseFloor = (eid: string, data: Partial<EnterpriseFloor>) =>
  api.post<ApiResponse<EnterpriseFloor>>(`${BASE(eid)}/floors`, data).then(r => r.data.data);

export const updateEnterpriseFloor = (eid: string, floorId: string, data: Partial<EnterpriseFloor>) =>
  api.put<ApiResponse<EnterpriseFloor>>(`${BASE(eid)}/floors/${floorId}`, data).then(r => r.data.data);

export const deleteEnterpriseFloor = (eid: string, floorId: string) =>
  api.delete(`${BASE(eid)}/floors/${floorId}`);

export const uploadEnterpriseFloorPlan = (eid: string, floorId: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api.post<ApiResponse<EnterpriseFloor>>(`${BASE(eid)}/floors/${floorId}/plan`, form).then(r => r.data.data);
};
```

- [ ] **步骤 5.3：扩展既有类型与服务**

在 `frontend/src/types/riskManagement.ts` 中：

```ts
export interface RiskZone {
  id: string;
  enterprise_id: string;
  floor_id: string | null;
  floor_name: string | null;
  name: string;
  description: string | null;
  sort_order: number;
  floor_plan_polygon: { version: 2; color_source: "auto" | "manual"; color: string | null; polygons: { id: string; label?: string; points: { x: number; y: number }[] }[] } | null;
  max_risk_level: string | null;
  effective_color: string | null;
  object_count: number;
  created_at: string;
  updated_at: string;
}
export interface RiskObject {
  id: string;
  enterprise_id: string;
  zone_id: string | null;
  floor_id: string | null;
  name: string;
  category: string | null;
  location: string | null;
  location_x: number | null;
  location_y: number | null;
  description: string | null;
  image_url: string | null;
  is_risk_point: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
  unit_count: number;
}
export interface HierarchyObject extends Pick<RiskObject, "id" | "name" | "category" | "is_risk_point" | "floor_id" | "location_x" | "location_y"> {
  units: HierarchyUnit[];
  events: HierarchyEvent[];
}
export interface HierarchyZone extends Pick<RiskZone, "id" | "name" | "description" | "floor_id" | "floor_name" | "floor_plan_polygon" | "max_risk_level" | "effective_color"> {
  objects: HierarchyObject[];
}
```

在 `frontend/src/services/riskManagementService.ts` 增加：

```ts
export const getRiskMappingOverview = (eid: string, floorId?: string) =>
  api.get<ApiResponse<import("@/types/riskMappingWorkbench").RawOverviewResponse>>(`${BASE(eid)}/overview`, { params: floorId ? { floor_id: floorId } : {} }).then(r => {
    const d = r.data.data;
    return {
      floors: [d.floor],
      currentFloorId: d.floor.id,
      zones: d.zones,
      riskPoints: d.risk_points,
      texts: d.floor.canvas_texts,
      pendingRegions: [],
    };
  });
```

- [ ] **步骤 5.4：增加路由**

在 `frontend/src/routes/index.tsx` 增加 import 和 route：

```tsx
import RiskMappingWorkbenchPage from "@/pages/Enterprise/RiskMappingWorkbenchPage";
...
{ path: "/enterprises/:id/risk-mapping-workbench", element: <RiskMappingWorkbenchPage /> },
```

- [ ] **步骤 5.5：验证**

运行：`cd frontend && npm run build`

预期：TypeScript 编译通过，Vite 构建成功。

- [ ] **步骤 5.6：Commit**

```bash
git add frontend/src/types frontend/src/services frontend/src/routes/index.tsx
git commit -m "feat(risk-mapping): add frontend types, services, and workbench route"
```

---

## 任务 6：Zustand Store 与几何工具

**文件：**
- 创建：`frontend/src/utils/riskMappingGeometry.ts`
- 创建：`frontend/src/store/riskMappingWorkbenchStore.ts`
- 创建：`frontend/src/store/riskMappingWorkbenchStore.test.ts`

- [ ] **步骤 6.1：创建几何工具**

创建 `frontend/src/utils/riskMappingGeometry.ts`：

```ts
import type { RiskPolygonPoint, RiskPolygon } from "@/types/riskMappingWorkbench";

export const toPercent = (value: number, max: number) => Math.min(100, Math.max(0, (value / max) * 100));
export const toCanvasX = (value: number, width = 1200) => (value / 100) * width;
export const toCanvasY = (value: number, height = 900) => (value / 100) * height;

export const clampPoint = (p: RiskPolygonPoint): RiskPolygonPoint => ({
  x: Math.min(100, Math.max(0, p.x)),
  y: Math.min(100, Math.max(0, p.y)),
});

export const pointsToKonva = (points: RiskPolygonPoint[], width = 1200, height = 900) =>
  points.flatMap(p => [toCanvasX(p.x, width), toCanvasY(p.y, height)]);

export const polygonArea = (points: RiskPolygonPoint[]) => {
  let area = 0;
  for (let i = 0; i < points.length; i++) {
    const a = points[i];
    const b = points[(i + 1) % points.length];
    area += a.x * b.y - b.x * a.y;
  }
  return Math.abs(area) / 2;
};

export const validatePolygon = (points: RiskPolygonPoint[]) => {
  if (points.length < 3) return "至少需要 3 个顶点";
  if (polygonArea(points) <= 0.001) return "多边形面积必须大于 0";
  return null;
};

export const simplifyPolygon = (points: RiskPolygonPoint[], tolerance = 0.15) => {
  if (points.length <= 3) return points;
  return points.filter((_, i) => i % 2 === 0 || i === points.length - 1);
};
```

- [ ] **步骤 6.2：创建 Store**

创建 `frontend/src/store/riskMappingWorkbenchStore.ts`：

```ts
import { create } from "zustand";
import type { WorkbenchZone, PendingRegion, RiskCanvasText, RiskPolygonPoint } from "@/types/riskMappingWorkbench";
import type { RiskObject } from "@/types/riskManagement";

interface WorkbenchState {
  floors: import("@/types/riskMappingWorkbench").EnterpriseFloor[];
  currentFloorId: string;
  zones: WorkbenchZone[];
  riskPoints: RiskObject[];
  texts: RiskCanvasText[];
  pendingRegions: PendingRegion[];
  deletedZoneIds: string[];
  deletedRiskPointIds: string[];
  selectedZoneId: string | null;
  selectedRegionId: string | null;
  tool: "select" | "rect" | "polygon" | "freehand" | "risk-point" | "text";
  gridEnabled: boolean;
  snapEnabled: boolean;
  guideEnabled: boolean;
  dirty: boolean;
  past: WorkbenchState[];
  future: WorkbenchState[];
  setSnapshot: (data: Partial<WorkbenchState>) => void;
  commit: () => void;
  reset: () => void;
}

const initial = {
  floors: [],
  currentFloorId: "",
  zones: [],
  riskPoints: [],
  texts: [],
  pendingRegions: [],
  deletedZoneIds: [],
  deletedRiskPointIds: [],
  selectedZoneId: null,
  selectedRegionId: null,
  tool: "select" as const,
  gridEnabled: true,
  snapEnabled: true,
  guideEnabled: true,
  dirty: false,
  past: [],
  future: [],
};

export const useRiskMappingWorkbenchStore = create<WorkbenchState>((set, get) => ({
  ...initial,
  setSnapshot: (data) => set({ ...data }),
  commit: () => {
    const state = get();
    set({ past: [...state.past.slice(-49), state], future: [], dirty: true });
  },
  reset: () => set({ ...initial }),
}));

export const undo = () => useRiskMappingWorkbenchStore.setState(state => {
  if (!state.past.length) return state;
  const previous = state.past[state.past.length - 1];
  return {
    ...previous,
    past: state.past.slice(0, -1),
    future: [state, ...state.future],
    dirty: true,
  };
});

export const redo = () => useRiskMappingWorkbenchStore.setState(state => {
  if (!state.future.length) return state;
  const next = state.future[0];
  return {
    ...next,
    past: [...state.past, state],
    future: state.future.slice(1),
    dirty: true,
  };
});
```

- [ ] **步骤 6.3：Store 测试**

创建 `frontend/src/store/riskMappingWorkbenchStore.test.ts`：

```ts
import { describe, it, expect } from "vitest";
import { useRiskMappingWorkbenchStore } from "./riskMappingWorkbenchStore";

describe("riskMappingWorkbenchStore", () => {
  it("commit marks dirty and pushes history", () => {
    useRiskMappingWorkbenchStore.setState({ past: [], future: [], dirty: false });
    useRiskMappingWorkbenchStore.getState().commit();
    expect(useRiskMappingWorkbenchStore.getState().dirty).toBe(true);
    expect(useRiskMappingWorkbenchStore.getState().past.length).toBe(1);
  });
});
```

如项目当前没有 `vitest`，在 `frontend/package.json` devDependencies 增加 `vitest`，脚本增加 `"test": "vitest run"`。

- [ ] **步骤 6.4：验证**

运行：`cd frontend && npx vitest run src/store/riskMappingWorkbenchStore.test.ts`

预期：1 个测试 PASS。

- [ ] **步骤 6.5：Commit**

```bash
git add frontend/src/utils/riskMappingGeometry.ts frontend/src/store/riskMappingWorkbenchStore.ts frontend/src/store/riskMappingWorkbenchStore.test.ts frontend/package.json
git commit -m "feat(risk-mapping): add workbench store and geometry helpers"
```

---

## 任务 7：工作台页面壳与楼层管理

**文件：**
- 创建：`frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx`
- 创建：`frontend/src/components/enterprise/EnterpriseFloorManager.tsx`
- 创建：`frontend/src/components/enterprise/riskMapping/WorkbenchZonePanel.tsx`
- 创建：`frontend/src/components/enterprise/riskMapping/WorkbenchLegend.tsx`

- [ ] **步骤 7.1：创建页面壳**

创建 `frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx`：

```tsx
import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { Spin, Space, Button } from "antd";
import { SaveOutlined, UndoOutlined, RedoOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getRiskMappingWorkbench } from "@/services/riskMappingWorkbenchService";
import { useRiskMappingWorkbenchStore, undo, redo } from "@/store/riskMappingWorkbenchStore";
import WorkbenchToolbar from "@/components/enterprise/riskMapping/WorkbenchToolbar";
import WorkbenchZonePanel from "@/components/enterprise/riskMapping/WorkbenchZonePanel";
import WorkbenchPropertiesPanel from "@/components/enterprise/riskMapping/WorkbenchPropertiesPanel";
import WorkbenchCanvas from "@/components/enterprise/riskMapping/WorkbenchCanvas";
import WorkbenchLegend from "@/components/enterprise/riskMapping/WorkbenchLegend";
import EnterpriseFloorManager from "@/components/enterprise/EnterpriseFloorManager";

export default function RiskMappingWorkbenchPage() {
  const { id: enterpriseId } = useParams<{ id: string }>();
  const currentFloorId = useRiskMappingWorkbenchStore(s => s.currentFloorId);
  const { data, isLoading } = useQuery({
    queryKey: ["risk-workbench", enterpriseId, currentFloorId],
    queryFn: () => getRiskMappingWorkbench(enterpriseId!, currentFloorId || undefined),
    enabled: !!enterpriseId,
  });
  const setSnapshot = useRiskMappingWorkbenchStore(s => s.setSnapshot);
  const dirty = useRiskMappingWorkbenchStore(s => s.dirty);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (data) setSnapshot({
      floors: data.floors,
      currentFloorId: data.currentFloorId,
      zones: data.zones,
      riskPoints: data.riskPoints,
      texts: data.texts,
      pendingRegions: data.pendingRegions ?? [],
      deletedRiskPointIds: [],
      deletedZoneIds: [],
      dirty: false,
    });
  }, [data, setSnapshot]);

  if (isLoading) return <Spin size="large" />;

  return (
    <div style={{ height: "calc(100vh - 80px)", display: "flex", flexDirection: "column", gap: 8 }}>
      <Space wrap>
        <EnterpriseFloorManager enterpriseId={enterpriseId!} />
        <WorkbenchToolbar />
        <Button icon={<UndoOutlined />} onClick={undo} />
        <Button icon={<RedoOutlined />} onClick={redo} />
        <Button type="primary" icon={<SaveOutlined />} disabled={!dirty}>保存</Button>
      </Space>
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "260px 1fr 300px", gap: 8, minHeight: 0 }}>
        <WorkbenchZonePanel />
        <div style={{ position: "relative", background: "#f5f5f5", borderRadius: 8, overflow: "hidden" }}>
          <WorkbenchCanvas />
          <WorkbenchLegend />
        </div>
        <WorkbenchPropertiesPanel />
      </div>
    </div>
  );
}
```

- [ ] **步骤 7.2：创建楼层管理器**

创建 `frontend/src/components/enterprise/EnterpriseFloorManager.tsx`：

```tsx
import { useState } from "react";
import { Button, Input, Modal, Select, Space, Upload, message } from "antd";
import { PlusOutlined, UploadOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listEnterpriseFloors,
  createEnterpriseFloor,
  updateEnterpriseFloor,
  deleteEnterpriseFloor,
  uploadEnterpriseFloorPlan,
} from "@/services/riskMappingWorkbenchService";
import { useRiskMappingWorkbenchStore } from "@/store/riskMappingWorkbenchStore";

export default function EnterpriseFloorManager({ enterpriseId }: { enterpriseId: string }) {
  const queryClient = useQueryClient();
  const currentFloorId = useRiskMappingWorkbenchStore(s => s.currentFloorId);
  const setSnapshot = useRiskMappingWorkbenchStore.getState().setSnapshot;
  const { data: floors = [] } = useQuery({
    queryKey: ["risk-floors", enterpriseId],
    queryFn: () => listEnterpriseFloors(enterpriseId),
  });
  const [modalOpen, setModalOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [name, setName] = useState("");

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["risk-floors", enterpriseId] });
    queryClient.invalidateQueries({ queryKey: ["risk-workbench", enterpriseId] });
  };

  const submit = async () => {
    if (!name.trim()) return;
    if (editId) {
      await updateEnterpriseFloor(enterpriseId, editId, { name: name.trim() });
    } else {
      await createEnterpriseFloor(enterpriseId, { name: name.trim(), sort_order: floors.length });
    }
    setModalOpen(false);
    setName("");
    setEditId(null);
    refresh();
  };

  return (
    <Space wrap>
      <Select
        style={{ width: 160 }}
        placeholder="选择楼层"
        value={currentFloorId || undefined}
        options={floors.map(f => ({ label: f.name, value: f.id }))}
        onChange={id => {
          setSnapshot({ currentFloorId: id, dirty: false, deletedZoneIds: [], deletedRiskPointIds: [] });
          queryClient.invalidateQueries({ queryKey: ["risk-workbench", enterpriseId] });
        }}
      />
      <Button
        icon={<PlusOutlined />}
        onClick={() => {
          setEditId(null);
          setName("");
          setModalOpen(true);
        }}
      >
        新建楼层
      </Button>
      <Upload
        accept="image/png,image/jpeg,image/webp"
        showUploadList={false}
        customRequest={async ({ file, onSuccess, onError }) => {
          const currentFloorId = useRiskMappingWorkbenchStore.getState().currentFloorId;
          const current = floors.find(f => f.id === currentFloorId) || floors[0];
          if (!current) {
            onError?.(new Error("请先选择楼层"));
            return;
          }
          try {
            await uploadEnterpriseFloorPlan(enterpriseId, current.id, file as File);
            message.success("平面图上传成功");
            refresh();
            onSuccess?.(null);
          } catch (e) {
            onError?.(e as Error);
          }
        }}
      >
        <Button icon={<UploadOutlined />}>上传当前楼层平面图</Button>
      </Upload>
      <Modal
        title={editId ? "编辑楼层" : "新建楼层"}
        open={modalOpen}
        onOk={submit}
        onCancel={() => setModalOpen(false)}
      >
        <Input value={name} onChange={e => setName(e.target.value)} placeholder="楼层名称，如一层" />
      </Modal>
    </Space>
  );
}
```

- [ ] **步骤 7.3：创建分区面板与图例**

创建 `WorkbenchZonePanel.tsx`：

```tsx
import { Button, Divider, Empty, Space } from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";
import { useRiskMappingWorkbenchStore } from "@/store/riskMappingWorkbenchStore";
import type { WorkbenchZone } from "@/types/riskMappingWorkbench";

export default function WorkbenchZonePanel() {
  const zones = useRiskMappingWorkbenchStore(s => s.zones);
  const pendingRegions = useRiskMappingWorkbenchStore(s => s.pendingRegions);
  const selectedZoneId = useRiskMappingWorkbenchStore(s => s.selectedZoneId);
  const setSnapshot = useRiskMappingWorkbenchStore.getState().setSnapshot;
  const commit = useRiskMappingWorkbenchStore.getState().commit;

  const addZone = () => {
    const zone: WorkbenchZone = {
      id: `new-zone-${Date.now()}`,
      enterprise_id: "",
      floor_id: useRiskMappingWorkbenchStore.getState().currentFloorId,
      floor_name: "",
      name: "未命名分区",
      description: null,
      sort_order: zones.length,
      floor_plan_polygon: null,
      max_risk_level: "未评估",
      effective_color: "#d9d9d9",
      object_count: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      objects: [],
    };
    setSnapshot({ zones: [...zones, zone], selectedZoneId: zone.id });
    commit();
  };

  return (
    <div style={{ background: "#fff", borderRadius: 8, padding: 8, overflow: "auto" }}>
      <Space style={{ width: "100%", justifyContent: "space-between" }}>
        <strong>分区</strong>
        <Button size="small" icon={<PlusOutlined />} onClick={addZone}>新增</Button>
      </Space>
      {zones.length === 0 ? <Empty description="暂无分区" /> : zones.map(z => (
        <div
          key={z.id}
          onClick={() => setSnapshot({ selectedZoneId: z.id })}
          style={{
            marginTop: 6,
            padding: 8,
            borderRadius: 6,
            cursor: "pointer",
            border: selectedZoneId === z.id ? "2px solid #1677ff" : "1px solid #d9d9d9",
            background: z.effective_color ? z.effective_color + "18" : "#fff",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>{z.name}</span>
            <Button
              size="small"
              type="text"
              icon={<DeleteOutlined />}
              onClick={e => {
                e.stopPropagation();
                const isPersisted = !z.id.startsWith("new-zone-");
                setSnapshot({
                  zones: zones.filter(item => item.id !== z.id),
                  selectedZoneId: null,
                  deletedZoneIds: isPersisted
                    ? [...useRiskMappingWorkbenchStore.getState().deletedZoneIds, z.id]
                    : useRiskMappingWorkbenchStore.getState().deletedZoneIds,
                });
                commit();
              }}
            />
          </div>
          <div style={{ fontSize: 12, color: "#8c8c8c" }}>
            {(z.floor_plan_polygon?.polygons || []).length} 个区域 · {z.max_risk_level || "未评估"}风险
          </div>
        </div>
      ))}
      <Divider style={{ margin: "12px 0" }}>待绑定区域</Divider>
      {pendingRegions.length === 0 ? <div style={{ color: "#999", fontSize: 12 }}>暂无待绑定区域</div> : pendingRegions.map(r => (
        <div key={r.id} style={{ padding: 6, border: "1px dashed #fa8c16", borderRadius: 6, marginTop: 4 }}>
          未绑定区域 · {r.points.length} 个顶点
        </div>
      ))}
    </div>
  );
}
```

创建 `WorkbenchLegend.tsx`：

```tsx
import { RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";

export default function WorkbenchLegend() {
  return (
    <div style={{ position: "absolute", left: 12, bottom: 12, background: "rgba(255,255,255,.92)", borderRadius: 8, padding: 8, fontSize: 12 }}>
      {Object.entries(RISK_LEVEL_COLORS).map(([level, color]) => (
        <div key={level} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 14, height: 14, background: color, borderRadius: 3, display: "inline-block" }} />
          {level}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **步骤 7.4：验证**

运行：`cd frontend && npm run build`

预期：构建通过。

- [ ] **步骤 7.5：Commit**

```bash
git add frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx frontend/src/components/enterprise/EnterpriseFloorManager.tsx frontend/src/components/enterprise/riskMapping
git commit -m "feat(risk-mapping): add workbench page shell and floor manager"
```

---

## 任务 8：Konva 画布与绘图工具

**文件：**
- 创建：`frontend/src/components/enterprise/riskMapping/WorkbenchToolbar.tsx`
- 创建：`frontend/src/components/enterprise/riskMapping/WorkbenchCanvas.tsx`
- 创建：`frontend/src/components/enterprise/riskMapping/WorkbenchRiskPointLayer.tsx`

- [ ] **步骤 8.1：安装 Konva**

```bash
cd frontend && npm install konva react-konva
```

- [ ] **步骤 8.2：创建工具栏**

创建 `frontend/src/components/enterprise/riskMapping/WorkbenchToolbar.tsx`：

```tsx
import { Button, Space, Switch, Tooltip } from "antd";
import {
  AimOutlined,
  BorderOutlined,
  EditOutlined,
  HighlightOutlined,
  EnvironmentOutlined,
  FontSizeOutlined,
  DragOutlined,
} from "@ant-design/icons";
import { useRiskMappingWorkbenchStore } from "@/store/riskMappingWorkbenchStore";

const TOOLS = [
  { value: "select", label: "选择", icon: <DragOutlined /> },
  { value: "rect", label: "矩形", icon: <BorderOutlined /> },
  { value: "polygon", label: "多边形", icon: <EditOutlined /> },
  { value: "freehand", label: "自由画笔", icon: <HighlightOutlined /> },
  { value: "risk-point", label: "风险点", icon: <EnvironmentOutlined /> },
  { value: "text", label: "文字", icon: <FontSizeOutlined /> },
] as const;

export default function WorkbenchToolbar() {
  const tool = useRiskMappingWorkbenchStore(s => s.tool);
  const setTool = (value: typeof TOOLS[number]["value"]) => useRiskMappingWorkbenchStore.setState({ tool: value });
  const gridEnabled = useRiskMappingWorkbenchStore(s => s.gridEnabled);
  const snapEnabled = useRiskMappingWorkbenchStore(s => s.snapEnabled);
  const guideEnabled = useRiskMappingWorkbenchStore(s => s.guideEnabled);
  return (
    <Space wrap>
      {TOOLS.map(item => (
        <Tooltip key={item.value} title={item.label}>
          <Button
            icon={item.icon}
            type={tool === item.value ? "primary" : "default"}
            onClick={() => setTool(item.value)}
          />
        </Tooltip>
      ))}
      <Space size={4}>
        <Switch checked={gridEnabled} onChange={v => useRiskMappingWorkbenchStore.setState({ gridEnabled: v })} size="small" />
        <span style={{ fontSize: 12 }}>网格</span>
      </Space>
      <Space size={4}>
        <Switch checked={snapEnabled} onChange={v => useRiskMappingWorkbenchStore.setState({ snapEnabled: v })} size="small" />
        <span style={{ fontSize: 12 }}>吸附</span>
      </Space>
      <Space size={4}>
        <Switch checked={guideEnabled} onChange={v => useRiskMappingWorkbenchStore.setState({ guideEnabled: v })} size="small" />
        <span style={{ fontSize: 12 }}>辅助线</span>
      </Space>
      <Button icon={<AimOutlined />} onClick={() => useRiskMappingWorkbenchStore.setState({ tool: "select" })} />
    </Space>
  );
}
```

`gridEnabled`、`snapEnabled`、`guideEnabled` 需要在 `riskMappingWorkbenchStore` 中补齐。

- [ ] **步骤 8.3：创建画布**

创建 `frontend/src/components/enterprise/riskMapping/WorkbenchCanvas.tsx`：

```tsx
import { useEffect, useState } from "react";
import { Stage, Layer, Image as KonvaImage, Line, Rect, Text as KonvaText } from "react-konva";
import { useRiskMappingWorkbenchStore } from "@/store/riskMappingWorkbenchStore";
import { pointsToKonva, toCanvasX, toCanvasY } from "@/utils/riskMappingGeometry";
import type { RiskPolygonPoint, RiskCanvasText } from "@/types/riskMappingWorkbench";
import type { RiskObject } from "@/types/riskManagement";
import WorkbenchRiskPointLayer from "./WorkbenchRiskPointLayer";

export default function WorkbenchCanvas() {
  const zones = useRiskMappingWorkbenchStore(s => s.zones);
  const pendingRegions = useRiskMappingWorkbenchStore(s => s.pendingRegions);
  const texts = useRiskMappingWorkbenchStore(s => s.texts);
  const riskPoints = useRiskMappingWorkbenchStore(s => s.riskPoints);
  const tool = useRiskMappingWorkbenchStore(s => s.tool);
  const gridEnabled = useRiskMappingWorkbenchStore(s => s.gridEnabled);
  const snapEnabled = useRiskMappingWorkbenchStore(s => s.snapEnabled);
  const floor = useRiskMappingWorkbenchStore(s => s.floors.find(f => f.id === s.currentFloorId));
  const currentFloorId = useRiskMappingWorkbenchStore(s => s.currentFloorId);
  const setSnapshot = useRiskMappingWorkbenchStore.getState().setSnapshot;
  const commit = useRiskMappingWorkbenchStore.getState().commit;
  const [draftPoints, setDraftPoints] = useState<RiskPolygonPoint[]>([]);
  const [draftStart, setDraftStart] = useState<RiskPolygonPoint | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  useEffect(() => {
    if (!floor?.floor_plan_url) {
      setImage(null);
      return;
    }
    const img = new window.Image();
    img.onload = () => setImage(img);
    img.src = floor.floor_plan_url;
    return () => { img.onload = null; };
  }, [floor?.floor_plan_url]);

  const pointFromEvent = (e: any): RiskPolygonPoint => {
    const rawX = (e.evt.offsetX / 1200) * 100;
    const rawY = (e.evt.offsetY / 900) * 100;
    const rounded = (v: number) => snapEnabled ? Math.round(v / 5) * 5 : Math.round(v * 100) / 100;
    return { x: Math.min(100, Math.max(0, rounded(rawX))), y: Math.min(100, Math.max(0, rounded(rawY))) };
  };

  const addPending = (points: RiskPolygonPoint[]) => {
    const region = {
      id: `pending-${Date.now()}`,
      floor_id: currentFloorId,
      points,
      created_at: new Date().toISOString(),
    };
    setSnapshot({ pendingRegions: [...useRiskMappingWorkbenchStore.getState().pendingRegions, region] });
    commit();
  };

  const handleClick = (e: any) => {
    if (tool === "select") return;
    const p = pointFromEvent(e);
    if (tool === "rect") {
      if (!draftStart) {
        setDraftStart(p);
        return;
      }
      addPending([draftStart, { x: p.x, y: draftStart.y }, p, { x: draftStart.x, y: p.y }]);
      setDraftStart(null);
      return;
    }
    if (tool === "polygon" || tool === "freehand") {
      setDraftPoints([...draftPoints, p]);
      return;
    }
    if (tool === "risk-point") {
      const riskPoint: RiskObject = {
        id: `new-point-${Date.now()}`,
        enterprise_id: "",
        zone_id: null,
        floor_id: currentFloorId,
        name: "新风险点",
        category: null,
        location: null,
        location_x: p.x,
        location_y: p.y,
        description: null,
        image_url: null,
        is_risk_point: true,
        sort_order: riskPoints.length,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        unit_count: 0,
      };
      setSnapshot({ riskPoints: [...useRiskMappingWorkbenchStore.getState().riskPoints, riskPoint] });
      commit();
      return;
    }
    if (tool === "text") {
      const item: RiskCanvasText = {
        id: `text-${Date.now()}`,
        content: "双击编辑文字",
        x: p.x,
        y: p.y,
        font_size: 14,
        color: "#333333",
        rotation: 0,
        sort_order: texts.length,
      };
      setSnapshot({ texts: [...useRiskMappingWorkbenchStore.getState().texts, item] });
      commit();
    }
  };

  const finishDrawing = () => {
    if ((tool === "polygon" || tool === "freehand") && draftPoints.length >= 3) {
      addPending(draftPoints);
    }
    setDraftPoints([]);
    setDraftStart(null);
  };

  const handleMouseDown = (e: any) => {
    if (tool === "freehand") {
      setIsDrawing(true);
      handleClick(e);
    }
  };

  const handleMouseMove = (e: any) => {
    if (tool === "freehand" && isDrawing) {
      setDraftPoints(prev => [...prev, pointFromEvent(e)]);
    }
  };

  const handleMouseUp = () => {
    if (tool === "freehand" && draftPoints.length >= 3) {
      finishDrawing();
    }
    setIsDrawing(false);
  };

  return (
    <Stage
      width={1200}
      height={900}
      style={{ maxWidth: "100%", maxHeight: "100%" }}
      onClick={handleClick}
      onDblClick={finishDrawing}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
    >
      <Layer>
        {image && <KonvaImage image={image} x={0} y={0} width={1200} height={900} />}
        {gridEnabled && Array.from({ length: 13 }, (_, i) => (
          <Line key={`gv-${i}`} points={[i * 100, 0, i * 100, 900]} stroke="#e8e8e8" strokeWidth={1} />
        ))}
        {gridEnabled && Array.from({ length: 10 }, (_, i) => (
          <Line key={`gh-${i}`} points={[0, i * 100, 1200, i * 100]} stroke="#e8e8e8" strokeWidth={1} />
        ))}
        {pendingRegions.map(r => (
          <Line key={r.id} points={pointsToKonva(r.points, 1200, 900)} closed stroke="#fa8c16" dash={[6, 4]} strokeWidth={2} />
        ))}
        {draftStart && (
          <Rect x={toCanvasX(draftStart.x, 1200)} y={toCanvasY(draftStart.y, 900)} width={100} height={100} dash={[4, 4]} stroke="#1677ff" />
        )}
        {draftPoints.length > 0 && (
          <Line points={pointsToKonva(draftPoints, 1200, 900)} closed={tool === "polygon"} stroke="#1677ff" dash={[4, 4]} strokeWidth={2} />
        )}
        {zones.map(z => (z.floor_plan_polygon?.polygons || []).map(p => (
          <Line key={p.id} points={pointsToKonva(p.points, 1200, 900)} closed fill={z.effective_color || "#d9d9d9"} opacity={0.35} stroke={z.effective_color || "#d9d9d9"} strokeWidth={2} draggable />
        )))}
        {texts.map(t => (
          <KonvaText key={t.id} x={toCanvasX(t.x, 1200)} y={toCanvasY(t.y, 900)} text={t.content} fontSize={t.font_size} fill={t.color} rotation={t.rotation} />
        ))}
        <WorkbenchRiskPointLayer />
      </Layer>
    </Stage>
  );
}
```

- [ ] **步骤 8.4：创建风险点图层**

创建 `frontend/src/components/enterprise/riskMapping/WorkbenchRiskPointLayer.tsx`：

```tsx
import { Group, Circle, Text } from "react-konva";
import { useRiskMappingWorkbenchStore } from "@/store/riskMappingWorkbenchStore";
import { toCanvasX, toCanvasY } from "@/utils/riskMappingGeometry";

export default function WorkbenchRiskPointLayer() {
  const points = useRiskMappingWorkbenchStore(s => s.riskPoints);
  const setPoints = useRiskMappingWorkbenchStore.getState().setSnapshot;
  return (
    <>
      {points.map(p => (
        <Group key={p.id} draggable onDragEnd={e => {
          const x = e.target.x();
          const y = e.target.y();
          setPoints({
            riskPoints: points.map(item => item.id === p.id ? {
              ...item,
              location_x: Math.round((x / 1200) * 10000) / 100,
              location_y: Math.round((y / 900) * 10000) / 100,
            } : item),
          });
          useRiskMappingWorkbenchStore.getState().commit();
        }}>
          <Circle x={toCanvasX(p.location_x ?? 0, 1200)} y={toCanvasY(p.location_y ?? 0, 900)} radius={6} fill="#1677ff" stroke="#fff" strokeWidth={2} />
          <Text x={toCanvasX(p.location_x ?? 0, 1200) + 8} y={toCanvasY(p.location_y ?? 0, 900) - 8} text={p.name} fontSize={12} />
        </Group>
      ))}
    </>
  );
}
```

- [ ] **步骤 8.5：验证构建**

运行：`cd frontend && npm run build`

预期：构建通过，无 Konva 类型错误。

- [ ] **步骤 8.6：Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/components/enterprise/riskMapping
git commit -m "feat(risk-mapping): add konva canvas and drawing toolbar"
```

---

## 任务 9：绑定、属性、文字与保存

**文件：**
- 创建：`frontend/src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx`
- 修改：`frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx`
- 修改：`frontend/src/store/riskMappingWorkbenchStore.ts`

- [ ] **步骤 9.1：创建属性面板**

创建 `frontend/src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx`：

```tsx
import { useState } from "react";
import { Button, Input, InputNumber, Select, Space } from "antd";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { useRiskMappingWorkbenchStore } from "@/store/riskMappingWorkbenchStore";
import type { RiskCanvasText, WorkbenchZone } from "@/types/riskMappingWorkbench";

export default function WorkbenchPropertiesPanel() {
  const zones = useRiskMappingWorkbenchStore(s => s.zones);
  const riskPoints = useRiskMappingWorkbenchStore(s => s.riskPoints);
  const pendingRegions = useRiskMappingWorkbenchStore(s => s.pendingRegions);
  const texts = useRiskMappingWorkbenchStore(s => s.texts);
  const selectedZoneId = useRiskMappingWorkbenchStore(s => s.selectedZoneId);
  const setSnapshot = useRiskMappingWorkbenchStore.getState().setSnapshot;
  const commit = useRiskMappingWorkbenchStore.getState().commit;
  const [textContent, setTextContent] = useState("");
  const zone = zones.find(z => z.id === selectedZoneId);

  const updateZone = (patch: Partial<WorkbenchZone>) => {
    if (!zone) return;
    setSnapshot({ zones: zones.map(z => z.id === zone.id ? { ...z, ...patch } : z) });
    commit();
  };

  const bindFirstPending = () => {
    if (!zone || !pendingRegions.length) return;
    const region = pendingRegions[0];
    const polygon = zone.floor_plan_polygon || { version: 2, color_source: "auto" as const, color: null, polygons: [] };
    updateZone({
      floor_plan_polygon: {
        ...polygon,
        polygons: [...polygon.polygons, { id: region.id, label: `${zone.name}-区域${polygon.polygons.length + 1}`, points: region.points }],
      },
    });
    setSnapshot({ pendingRegions: pendingRegions.slice(1) });
    commit();
  };

  const addText = () => {
    if (!textContent.trim()) return;
    const item: RiskCanvasText = {
      id: `text-${Date.now()}`,
      content: textContent.trim(),
      x: 50,
      y: 50,
      font_size: 14,
      color: "#333333",
      rotation: 0,
      sort_order: texts.length,
    };
    setSnapshot({ texts: [...texts, item] });
    commit();
    setTextContent("");
  };

  return (
    <div style={{ background: "#fff", borderRadius: 8, padding: 12, overflow: "auto" }}>
      <h4 style={{ fontSize: 14, marginBottom: 12 }}>属性</h4>
      {!zone ? (
        <div style={{ color: "#999" }}>请先选择分区</div>
      ) : (
        <>
          <Input value={zone.name} onChange={e => updateZone({ name: e.target.value })} />
          <Input.TextArea
            style={{ marginTop: 8 }}
            rows={3}
            value={zone.description || ""}
            onChange={e => updateZone({ description: e.target.value })}
          />
          <Select
            style={{ width: "100%", marginTop: 8 }}
            value={zone.floor_plan_polygon?.color_source || "auto"}
            options={[{ value: "auto", label: "自动颜色" }, { value: "manual", label: "手动覆盖" }]}
            onChange={value => {
              const polygon = zone.floor_plan_polygon || { version: 2, color_source: "auto" as const, color: null, polygons: [] };
              updateZone({
                floor_plan_polygon: {
                  ...polygon,
                  color_source: value as "auto" | "manual",
                  color: value === "manual" ? polygon.color || "#ff4d4f" : null,
                },
              });
            }}
          />
          {zone.floor_plan_polygon?.color_source === "manual" && (
            <Input
              type="color"
              style={{ width: "100%", marginTop: 8 }}
              value={zone.floor_plan_polygon.color || "#ff4d4f"}
              onChange={e => updateZone({
                floor_plan_polygon: { ...zone.floor_plan_polygon!, color: e.target.value },
              })}
            />
          )}
          {pendingRegions.length > 0 && (
            <Button block style={{ marginTop: 8 }} onClick={bindFirstPending}>绑定待处理区域</Button>
          )}
          <Button
            danger
            block
            style={{ marginTop: 8 }}
            icon={<DeleteOutlined />}
            onClick={() => {
              const isPersisted = !zone.id.startsWith("new-zone-");
              setSnapshot({
                zones: zones.filter(z => z.id !== zone.id),
                selectedZoneId: null,
                deletedZoneIds: isPersisted
                  ? [...useRiskMappingWorkbenchStore.getState().deletedZoneIds, zone.id]
                  : useRiskMappingWorkbenchStore.getState().deletedZoneIds,
              });
              commit();
            }}
          >
            删除分区
          </Button>
        </>
      )}
      <h4 style={{ fontSize: 14, marginTop: 16 }}>风险点</h4>
      {riskPoints.map(p => (
        <div key={p.id} style={{ marginTop: 4 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>{p.name}</span>
            <Button
              size="small"
              type="text"
              icon={<DeleteOutlined />}
              onClick={() => {
                setSnapshot({
                  riskPoints: riskPoints.filter(item => item.id !== p.id),
                  deletedRiskPointIds: [...useRiskMappingWorkbenchStore.getState().deletedRiskPointIds, p.id],
                });
                commit();
              }}
            />
          </div>
          <Select
            size="small"
            style={{ width: "100%", marginTop: 4 }}
            value={p.zone_id || undefined}
            placeholder="绑定分区"
            options={zones.map(z => ({ value: z.id, label: z.name }))}
            onChange={zone_id => {
              setSnapshot({ riskPoints: riskPoints.map(item => item.id === p.id ? { ...item, zone_id } : item) });
              commit();
            }}
          />
        </div>
      ))}
      <h4 style={{ fontSize: 14, marginTop: 16 }}>文字标注</h4>
      <Space.Compact style={{ width: "100%" }}>
        <Input value={textContent} onChange={e => setTextContent(e.target.value)} placeholder="标注内容" />
        <Button icon={<PlusOutlined />} onClick={addText} />
      </Space.Compact>
      {texts.map(t => <div key={t.id} style={{ fontSize: 12, marginTop: 4 }}>{t.content}</div>)}
    </div>
  );
}
```

保存动作在页面壳的“保存”按钮中调用 `saveRiskMappingWorkbench`，并处理 `SAVE_CONFLICT`：

```tsx
const onSave = async () => {
  try {
    const state = useRiskMappingWorkbenchStore.getState();
    const floor = state.floors.find(f => f.id === state.currentFloorId);
    if (!floor) return;
    if (state.pendingRegions.length) {
      message.error("存在待绑定区域，请先绑定");
      return;
    }
    if (state.zones.some(z => !z.floor_plan_polygon?.polygons.length)) {
      message.error("所有分区必须至少绘制一个区域");
      return;
    }
    if (state.riskPoints.some(p => !p.zone_id)) {
      message.error("所有风险点必须绑定分区");
      return;
    }
    const payload: BatchSavePayload = {
      floor_id: floor.id,
      floor_updated_at: floor.updated_at,
      zones: state.zones.map(z => {
        const isNew = z.id.startsWith("new-zone-");
        return {
          client_id: isNew ? z.id : undefined,
          zone_id: isNew ? null : z.id,
          name: z.name,
          description: z.description,
          updated_at: isNew ? undefined : z.updated_at,
          floor_plan_polygon: z.floor_plan_polygon!,
        };
      }),
      risk_points: state.riskPoints.map(p => {
        const isNew = p.id.startsWith("new-point-");
        const targetZone = state.zones.find(z => z.id === p.zone_id);
        const targetZoneIsNew = targetZone?.id.startsWith("new-zone-") ?? false;
        return {
          client_id: isNew ? p.id : undefined,
          id: isNew ? null : p.id,
          name: p.name,
          zone_id: targetZoneIsNew ? null : p.zone_id,
          zone_client_id: targetZoneIsNew ? p.zone_id : undefined,
          location_x: p.location_x ?? 0,
          location_y: p.location_y ?? 0,
          updated_at: isNew ? undefined : p.updated_at,
        };
      }),
      deleted_risk_point_ids: state.deletedRiskPointIds,
      deleted_zone_ids: state.deletedZoneIds,
      confirm_cascade_zone_ids: [],
      texts: state.texts,
    };
    const saved = await saveRiskMappingWorkbench(enterpriseId!, payload);
    useRiskMappingWorkbenchStore.getState().setSnapshot({
      floors: state.floors.map(f => f.id === saved.floor.id ? saved.floor : f),
      zones: saved.zones,
      riskPoints: saved.risk_points,
      texts: saved.texts,
      deletedRiskPointIds: [],
      deletedZoneIds: [],
      dirty: false,
    });
    queryClient.invalidateQueries({ queryKey: ["risk-hierarchy", enterpriseId] });
    queryClient.invalidateQueries({ queryKey: ["risk-overview", enterpriseId] });
  } catch (e: any) {
    if (e?.response?.data?.detail?.code === "SAVE_CONFLICT") {
      message.error("数据已被其他人修改，请刷新后重试");
    }
  }
};
```

将上面的 `onSave` 放入 `RiskMappingWorkbenchPage.tsx`，并把“保存”按钮改为 `onClick={onSave}`。

若保存时存在 `pendingRegions`，先弹出待绑定清单并阻止保存。

- [ ] **步骤 9.2：接入 Store 历史**

`undo/redo` 已在任务 6 定义，页面壳按钮已绑定。本步骤只需确认 `commit()` 在绘制、拖拽、绑定、文字和颜色修改完成后被调用，且 `setSnapshot` 不自动触发历史记录。

- [ ] **步骤 9.3：验证**

运行：`cd frontend && npm run build`

预期：构建通过。

- [ ] **步骤 9.4：Commit**

```bash
git add frontend/src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx frontend/src/store/riskMappingWorkbenchStore.ts
git commit -m "feat(risk-mapping): add binding, properties, text, and save flow"
```

---

## 任务 10：总览联动与旧入口兼容

**文件：**
- 创建：`frontend/src/components/enterprise/riskMapping/RiskDistributionStage.tsx`
- 修改：`frontend/src/pages/Enterprise/RiskOverviewPage.tsx`
- 修改：`frontend/src/pages/Enterprise/RiskManagementTab.tsx`
- 修改：`frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx`
- 修改：`frontend/src/components/enterprise/RiskZoneForm.tsx`

- [ ] **步骤 10.1：创建总览分布图**

创建 `frontend/src/components/enterprise/riskMapping/RiskDistributionStage.tsx`：

```tsx
import { useMemo } from "react";
import { useParams } from "react-router-dom";
import { Stage, Layer, Line, Circle, Text as KonvaText, Image as KonvaImage } from "react-konva";
import { Spin } from "antd";
import { useQuery } from "@tanstack/react-query";
import { getRiskMappingOverview } from "@/services/riskManagementService";
import { pointsToKonva, toCanvasX, toCanvasY } from "@/utils/riskMappingGeometry";

function useFloorImage(url?: string | null) {
  return useMemo(() => {
    if (!url) return null;
    const image = new window.Image();
    image.src = url;
    return image;
  }, [url]);
}

export default function RiskDistributionStage({ floorId, onZoneClick }: { floorId?: string; onZoneClick?: (zoneId: string) => void }) {
  const { id: enterpriseId } = useParams<{ id: string }>();
  const { data, isLoading } = useQuery({
    queryKey: ["risk-overview-stage", enterpriseId, floorId],
    queryFn: () => getRiskMappingOverview(enterpriseId!, floorId),
    enabled: !!enterpriseId,
  });
  const image = useFloorImage(data?.floors[0]?.floor_plan_url);
  if (isLoading) return <Spin />;
  if (!data) return null;
  return (
    <div style={{ width: "100%", height: "100%", overflow: "hidden", background: "#fafafa" }}>
      <Stage width={900} height={600}>
        <Layer>
          {image && <KonvaImage image={image} x={0} y={0} width={900} height={600} />}
          {data.zones.map(z => (z.floor_plan_polygon?.polygons || []).map(p => (
            <Line
              key={p.id}
              points={pointsToKonva(p.points, 900, 600)}
              closed
              fill={z.effective_color || "#d9d9d9"}
              opacity={0.35}
              stroke={z.effective_color || "#d9d9d9"}
              strokeWidth={2}
              onClick={() => onZoneClick?.(z.id)}
            />
          )))}
          {data.riskPoints.map(p => (
            <Circle key={p.id} x={toCanvasX(p.location_x ?? 0, 900)} y={toCanvasY(p.location_y ?? 0, 600)} radius={6} fill="#1677ff" stroke="#fff" strokeWidth={2} />
          ))}
          {data.zones.map(z => {
            const first = z.floor_plan_polygon?.polygons?.[0]?.points?.[0];
            return first ? <KonvaText key={z.id} x={toCanvasX(first.x, 900)} y={toCanvasY(first.y, 600) - 14} text={z.name} fontSize={13} fill="#333" /> : null;
          })}
        </Layer>
      </Stage>
    </div>
  );
}
```

- [ ] **步骤 10.2：替换总览占位**

修改 `frontend/src/pages/Enterprise/RiskOverviewPage.tsx`：

```tsx
import { Select } from "antd";
import { getRiskMappingOverview } from "@/services/riskManagementService";
import RiskDistributionStage from "@/components/enterprise/riskMapping/RiskDistributionStage";

const [floorId, setFloorId] = useState<string | undefined>();
const { data: overview } = useQuery({
  queryKey: ["risk-overview", enterpriseId, floorId],
  queryFn: () => getRiskMappingOverview(enterpriseId!, floorId),
  enabled: !!enterpriseId,
});

<Space style={{ marginBottom: 16 }}>
  <Select
    value={floorId}
    placeholder="选择楼层"
    style={{ width: 180 }}
    options={(overview?.floors || []).map(f => ({ label: f.name, value: f.id }))}
    onChange={setFloorId}
  />
</Space>
```

将 `FloorPlanHeatmap` 替换为：

```tsx
<Card size="small" title="① 厂区平面图热区" style={{ overflow: "hidden" }}>
  <RiskDistributionStage floorId={floorId} onZoneClick={setHighlightZone} />
</Card>
```

- [ ] **步骤 10.3：加入工作台入口**

修改 `RiskManagementTab.tsx` 的操作按钮区：

```tsx
<Button icon={<EditOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-mapping-workbench`)}>
  四色分布图工作台
</Button>
```

同时 `EnterpriseDetailPage.tsx` 中 `RiskManagementTab` 的 `floorPlanUrl` 改为从企业默认楼层接口读取；若接口尚未就绪，继续使用 `enterprise.floor_plan_url` 作为兼容值。

- [ ] **步骤 10.4：旧表单 v2 兼容**

修改 `RiskZoneForm.tsx` 的 `RiskZoneFormValues`：

```ts
interface RiskZoneFormValues {
  name: string;
  description?: string;
  floor_plan_polygon?: {
    version: 2;
    color_source: "auto" | "manual";
    color: string | null;
    polygons: { id: string; label?: string; points: { x: number; y: number }[] }[];
  };
}
```

`handlePolygonConfirm` 写入 v2 结构：

```ts
form.setFieldsValue({
  floor_plan_polygon: {
    version: 2,
    color_source: "auto",
    color: null,
    polygons: [{
      id: crypto.randomUUID(),
      label: form.getFieldValue("name") || "未命名区域",
      points: polygonPoints,
    }],
  },
});
```

- [ ] **步骤 10.5：验证**

运行：`cd frontend && npm run build`

预期：构建通过。

- [ ] **步骤 10.6：Commit**

```bash
git add frontend/src/components/enterprise/riskMapping frontend/src/pages/Enterprise/RiskOverviewPage.tsx frontend/src/pages/Enterprise/RiskManagementTab.tsx frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx frontend/src/components/enterprise/RiskZoneForm.tsx
git commit -m "feat(risk-mapping): connect overview and legacy form to workbench data"
```

---

## 任务 11：E2E、性能与发布验证

**文件：**
- 创建：`frontend/e2e/risk-mapping-workbench.spec.ts`
- 修改：`TASKS.md`

- [ ] **步骤 11.1：编写 E2E**

创建 `frontend/e2e/risk-mapping-workbench.spec.ts`：

```ts
import { test, expect } from "@playwright/test";

test("risk mapping workbench opens and renders canvas", async ({ page }) => {
  await page.goto("/login");
  await page.getByPlaceholder("邮箱").fill("qa_e2e_test@test.com");
  await page.getByPlaceholder("密码").fill("123456");
  await page.getByRole("button", { name: "登录" }).click();
  await page.goto("/enterprises/test-enterprise/risk-mapping-workbench");
  await expect(page.locator("text=四色分布图工作台").first()).toBeVisible();
  await expect(page.locator("canvas").first()).toBeVisible();
});
```

若测试账号字段不同，先对齐 `frontend/e2e/comprehensive.spec.ts` 的登录 helper。

- [ ] **步骤 11.2：性能检查**

构建后运行 Playwright 性能 smoke：

```bash
cd frontend && npx playwright test e2e/risk-mapping-workbench.spec.ts --reporter=list
```

预期：工作台路由加载成功，画布渲染，控制台无未捕获错误。

- [ ] **步骤 11.3：更新 TASKS**

更新 `TASKS.md` 当前状态快照：记录完成的任务、剩余风险、发布前置条件。

- [ ] **步骤 11.4：Commit**

```bash
git add frontend/e2e/risk-mapping-workbench.spec.ts TASKS.md
git commit -m "test(risk-mapping): add workbench e2e and release verification"
```

---

## 验收映射

| AC | 覆盖任务 |
|---|---|
| AC-01 默认楼层 | 任务 1、3 |
| AC-02 楼层切换 | 任务 4、7、10 |
| AC-03 楼层维护 | 任务 3、7 |
| AC-04 跨楼层约束 | 任务 4 |
| AC-05 v2 多边形 | 任务 2、4、8 |
| AC-06 多区域分区 | 任务 8、9 |
| AC-07 未绑定限制 | 任务 9 |
| AC-08/09 自动/手动颜色 | 任务 2、9 |
| AC-10/11 风险点 | 任务 8、9 |
| AC-12 批量保存 | 任务 4、9 |
| AC-13 总览联动 | 任务 10 |
| AC-14 文字标注 | 任务 9 |
| AC-15 撤销/重做 | 任务 6、9 |
| AC-16/17/18 迁移 | 任务 1 |
| AC-19 同批新建映射 | 任务 4、9 |
| AC-20 并发冲突 | 任务 4、9 |
| AC-21 级联删除确认 | 任务 3、4 |
| AC-22 平面图上传 | 任务 3 |

---

## 发布前置条件

1. 在测试库执行 `backend/db_migration_risk_mapping_workbench.sql`，确认可幂等重跑。
2. 后端 pytest 全部通过。
3. `cd frontend && npm run build` 通过。
4. Playwright E2E 通过。
5. 旧企业总图迁移后抽查 3 个企业的分区坐标与总览色块。
