<!--
  文档元信息
  创建日期: 2026-08-04
  作者: Codex
  版本: 1.0
  状态: 待审查
  依赖: PRD-15, PRD-02, PRD-11
-->

# 风险分级管控模块四色分布图工作台 — 完整设计方案

## 1. 概述

### 1.1 背景

风险分级管控模块已经具备五层层级数据模型（分区 -> 对象 -> 单元 -> 事件 -> 措施），并预留了 `risk_zones.floor_plan_polygon`、`risk_objects.location_x/location_y` 等绘图字段。但当前实现只停留在“分区表单内点击绘制”和“总览页卡片占位”阶段，存在以下断点：

- `RiskManagementTab` 保存分区时没有提交 `floor_plan_polygon`。
- `HierarchyZoneResponse` 不返回多边形和风险点坐标，总览无法真实渲染。
- `RiskOverviewPage` 的 `FloorPlanHeatmap` 只是按分区数量生成色块，不是真正的平面图热区。
- 企业只有单张 `floor_plan_url`，无法表达多层厂房。
- 没有完整的绘图工作台，无法同时管理多个分区、多个不相邻区域、风险点和文字标注。

本方案在现有风险分级管控模块上新增独立“四色分布图工作台”，打通“绘制 -> 绑定 -> 保存 -> 总览联动”的完整链路。

### 1.2 目标

- 在风险分级管控模块内提供独立四色分布图工作台。
- 支持有平面图时叠加绘制，无平面图时使用空白画布。
- 支持完整多层厂房：楼层列表、每层平面图、工作台和总览按楼层切换。
- 支持一个风险分区包含多个不相邻区域。
- 支持颜色自动默认 + 手动覆盖。
- 支持已有风险点拖拽和新建风险点。
- 支持先选分区再画、先画再绑定两种绑定流程。
- 支持完整绘图工具：选择/移动、矩形、多边形、自由画笔、风险点、文字、网格/吸附、辅助线、撤销/重做、缩放/平移、图例。
- 工作台保存后，总览页能按楼层真实渲染分区多边形和风险点，并支持点击联动层级树。

### 1.3 非目标

- 首版不做多人实时协同编辑。
- 首版不做 GIS 地图坐标、经纬度、投影和比例尺校准。
- 首版不做三维厂房模型。
- 首版不实现自由导出 PNG/Word，但画布渲染层应预留导出能力。
- 首版不重做风险事件评级、措施管理、方法编辑器等既有功能。

### 1.4 已确认决策

| 决策项 | 结论 |
|---|---|
| 功能入口 | 风险分级管控模块内新增独立“四色分布图工作台”页面 |
| 首版范围 | 绘制 + 保存 + 总览联动 |
| 画布模式 | 有企业/楼层平面图时叠加平面图，无平面图时使用空白画布 |
| 技术方案 | Konva.js + react-konva |
| 绑定流程 | 先选分区再画、先画再绑定都支持 |
| 未绑定处理 | 待绑定清单；保存前必须处理 |
| 区域模型 | 一个风险分区可包含多个不相邻区域 |
| 跨楼层规则 | 风险分区不可跨楼层 |
| 楼层支持 | 首版完整支持多层厂房 |
| 颜色规则 | 自动默认 + 手动覆盖；手动覆盖按风险分区整体生效 |
| 风险点 | 已有风险点可拖，也允许新建风险点 |
| 新建风险点 | 创建 `risk_objects`，`is_risk_point=true`，必须绑定当前楼层分区 |
| 工具集 | 完整工具 |
| 保存方式 | 工作台批量保存，单事务提交 |
| 旧数据 | `enterprises.floor_plan_url` 迁移为默认楼层/总图 |

### 1.5 用户故事

**场景 A：单层企业**

企业已上传总平面图。安全员进入工作台，左侧选择“生产车间”，在平面图上画出两个不相邻区域，拖拽已有风险点到正确位置，设置手动颜色，点击保存。之后进入总览页，按当前楼层看到真实分区和风险点。

**场景 B：多层厂房**

企业维护“一层”“二层”“三层”楼层并分别上传平面图。安全员切到一层绘制一层分区，切到二层绘制二层分区。每层的分区列表、画布、风险点、总览互不混用。

**场景 C：没有平面图**

企业没有平面图。工作台仍可进入，使用空白画布、网格和辅助线绘制四色分布图；后期上传平面图后，百分比坐标仍可复用。

---

## 2. 现状与断点

### 2.1 现有基础

- 后端已存在 `risk_zones`、`risk_objects`、`risk_units`、`risk_events`、`risk_measures` 五层模型。
- `risk_zones.floor_plan_polygon` 为 JSONB，旧结构为 `{ "points": [{ "x": 12.5, "y": 34.2 }] }`。
- `risk_objects.location_x/location_y` 已存在，使用 0-100 百分比坐标。
- `enterprises.floor_plan_url` 已存在，但只有单张平面图。
- 前端已安装 `leaflet`、`react-leaflet`，但当前用于 GIS 定位场景。
- 前端已有 `RiskZoneForm` 的点选多边形弹窗、`FloorPlanPicker` 点选坐标弹窗。

### 2.2 需要修复的断点

| 位置 | 问题 |
|---|---|
| `RiskManagementTab.tsx` | 保存 zone 时未传 `floor_plan_polygon`，编辑 zone 时也未回填 |
| `riskManagementService.ts` | 类型和服务未完整传递 polygon、floor_id、风险点坐标 |
| `backend/app/schemas/risk_management.py` | `HierarchyZoneResponse` 不含 polygon、坐标、floor_id |
| `backend/app/routers/risk_management.py` | hierarchy 未返回工作台所需几何数据 |
| `RiskOverviewPage.tsx` | `FloorPlanHeatmap` 只是卡片占位 |
| `EnterpriseEditPage.tsx` | 只有单张平面图，没有楼层管理 |
| `RiskObjectForm.tsx` | 页面调用处未传入 `floorPlanUrl`，风险点坐标编辑不完整 |

---

## 3. 总体架构

### 3.1 技术选型

| 层 | 技术 | 说明 |
|---|---|---|
| 后端 | FastAPI + SQLAlchemy + PostgreSQL JSONB | 沿用现有技术栈 |
| 前端 | React 19 + TypeScript + Vite + Ant Design + Zustand | 沿用现有技术栈 |
| 绘图 | Konva.js + react-konva | 负责画布、图层、Transformer、自由画笔、网格等 |
| 测试 | pytest + Playwright | 沿用现有测试体系 |

### 3.2 组件架构

```text
RiskMappingWorkbenchPage
  ├── FloorSwitcher
  ├── RiskMappingToolbar
  ├── ZonePanel
  ├── PendingBindingPanel
  ├── RiskMappingCanvas
  │   ├── FloorImageLayer
  │   ├── GridLayer
  │   ├── ZoneLayer
  │   ├── RiskPointLayer
  │   ├── TextLayer
  │   ├── DrawingLayer
  │   ├── GuideLayer
  │   └── SelectionLayer
  └── PropertyPanel
```

### 3.3 数据流

```text
页面加载
  -> GET workbench 聚合接口
  -> 组装 WorkbenchSnapshot
  -> 写入 Zustand store

用户绘制/拖拽/绑定
  -> store commit
  -> 校验
  -> POST workbench/batch-save
  -> 后端单事务写库
  -> 失效 React Query 键
  -> 总览页重新读取
```

### 3.4 新增目录

```text
backend/app/services/risk_mapping_service.py
frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx
frontend/src/components/enterprise/riskMapping/
frontend/src/store/riskMappingWorkbenchStore.ts
frontend/src/types/riskMappingWorkbench.ts
frontend/src/utils/riskMappingGeometry.ts
```

---

## 4. 数据模型

### 4.1 enterprise_floors

新增表，表示企业楼层/总图。

```sql
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
```

字段说明：

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK | 楼层 ID |
| enterprise_id | UUID | NOT NULL, FK, RESTRICT | 所属企业 |
| name | VARCHAR(255) | NOT NULL | 楼层名称，如“一层”“总图” |
| sort_order | INTEGER | NOT NULL, default 0 | 排序值，升序展示 |
| floor_plan_url | VARCHAR(500) | NULL | 该楼层平面图 URL |
| description | TEXT | NULL | 楼层说明 |
| canvas_width | INTEGER | NULL | 画布基准宽度，由图片自然尺寸或默认 1200 初始化 |
| canvas_height | INTEGER | NULL | 画布基准高度，默认 900 |
| canvas_texts | JSONB | NOT NULL, default [] | 楼层文字标注 |
| is_default | BOOLEAN | NOT NULL, default false | 是否默认楼层/总图；每企业最多一个 true |

`canvas_texts` 结构：

```json
[
  {
    "id": "text-1",
    "content": "原料库",
    "x": 12.5,
    "y": 34.2,
    "font_size": 14,
    "color": "#333333",
    "rotation": 0,
    "sort_order": 0
  }
]
```

规则：

- 每个企业必须有且仅有一个默认楼层/总图。
- 默认楼层可编辑名称、说明和平面图；删除前必须先设置新的默认楼层。
- 有分区或风险点的楼层不允许删除，返回 `FLOOR_IN_USE`。
- 默认楼层由旧 `enterprises.floor_plan_url` 迁移产生。
- 更新默认楼层 `floor_plan_url` 时，同步写回 `enterprises.floor_plan_url`，保证旧字段兼容。
- 企业删除不允许由数据库静默级联触发，必须由应用层 `enterprise_cleanup_service` 按 `4.7` 顺序显式清理。

### 4.2 risk_zones 扩展

```sql
ALTER TABLE risk_zones
    ADD COLUMN IF NOT EXISTS floor_id UUID;

ALTER TABLE risk_zones
    ALTER COLUMN floor_id SET NOT NULL;

ALTER TABLE risk_zones
    ADD CONSTRAINT fk_risk_zones_floor
    FOREIGN KEY (floor_id) REFERENCES enterprise_floors(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_rz_floor ON risk_zones(floor_id);
```

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| floor_id | UUID | NOT NULL, FK | 风险分区所属楼层 |
| floor_plan_polygon | JSONB | NULL | 分区绘图数据，v2 结构，兼容旧结构 |

规则：

- 风险分区不可跨楼层。
- 分区移动到其他楼层时，同事务内同步更新该分区下所有风险对象的 `floor_id`。
- 分区创建时 `floor_plan_polygon` 可以为空；工作台批量保存时，当前楼层所有未删除分区必须绑定至少一个多边形区域。

### 4.3 risk_objects 扩展

```sql
ALTER TABLE risk_objects
    ADD COLUMN IF NOT EXISTS floor_id UUID;

ALTER TABLE risk_objects
    ADD CONSTRAINT fk_risk_objects_floor
    FOREIGN KEY (floor_id) REFERENCES enterprise_floors(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_ro_floor ON risk_objects(floor_id);
```

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| floor_id | UUID | NULL, FK | 风险对象所属楼层 |
| zone_id | UUID | NULL, FK, RESTRICT | 所属分区；迁移时替换现有 `SET NULL`，禁止删除分区后对象游离 |
| location_x | FLOAT | NULL | 百分比 X 坐标，0-100 |
| location_y | FLOAT | NULL | 百分比 Y 坐标，0-100 |
| is_risk_point | BOOLEAN | NOT NULL, default false | 是否工作台风险点 |

规则：

- `floor_id` 为空且 `zone_id` 非空时，服务端读取或写入时沿用所属分区 `floor_id`。
- `zone_id` 与 `floor_id` 同时提供时必须一致，否则返回 `ZONE_FLOOR_MISMATCH`。
- 工作台新建风险点必须设置 `zone_id`、`location_x`、`location_y`，`floor_id` 可省略并由服务端沿用分区楼层，并强制 `is_risk_point=true`。
- 工作台保存只处理风险点；普通风险对象仍通过现有对象 CRUD 管理。
- 删除分区时，风险对象由应用层级联删除，具体顺序与确认规则见 `4.7`。

### 4.4 floor_plan_polygon v2 结构

统一使用以下结构：

```json
{
  "version": 2,
  "color_source": "auto",
  "color": "#ff4d4f",
  "polygons": [
    {
      "id": "zone-region-1",
      "label": "原料库北区",
      "points": [
        { "x": 12.5, "y": 18.2 },
        { "x": 35.1, "y": 18.2 },
        { "x": 35.1, "y": 42.6 },
        { "x": 12.5, "y": 42.6 }
      ]
    }
  ]
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| version | integer | 是 | 固定为 2 |
| color_source | string | 是 | `auto` 或 `manual` |
| color | string/null | 条件 | `manual` 时必填；`auto` 时可为空，API 返回有效色值 |
| polygons | array | 是 | 分区内一个或多个不相邻区域 |
| polygons[].id | string | 是 | 区域 ID，同一分区内唯一 |
| polygons[].label | string | 否 | 区域标签 |
| polygons[].points | array | 是 | 至少 3 个 `{x, y}` 顶点 |

校验规则：

- `points` 至少包含 3 个顶点。
- 所有 `x`、`y` 必须为有限数值，范围 0-100。
- 同一 `floor_plan_polygon.polygons` 内 `id` 不允许重复。
- `color_source=manual` 时 `color` 必须为合法十六进制颜色。
- `color_source=auto` 时后端根据分区最高风险等级计算颜色，不接受客户端覆盖。
- 手动覆盖粒度按分区整体，同一分区所有区域共用同一展示色，避免与风险等级口径冲突。

### 4.5 颜色规则

自动色使用现有风险等级色值：

| 风险等级 | 色值 |
|---|---|
| 重大 | `#ff4d4f` |
| 较大 | `#fa8c16` |
| 一般 | `#fadb14` |
| 低 | `#52c41a` |
| 未评估/无事件 | `#d9d9d9` |

自动色计算规则：

- 收集分区下所有风险对象及其单元下的事件。
- 取事件 `risk_level` 最高等级，排序为：重大 > 较大 > 一般 > 低。
- 没有可识别事件时按“未评估/无事件”处理。
- `color_source=auto` 时后端每次返回都重新计算有效色值。
- `color_source=manual` 时保存用户选择色值，清除覆盖后恢复 `auto`。

### 4.6 旧数据兼容与迁移

兼容旧 `{ "points": [...] }` 结构：

- 读取时自动归一化为 v2：`version=2`，`color_source=auto`，`color=null`，生成一个 `polygon.id`。
- `label` 默认使用分区名称。
- 迁移后写入 v2 结构，保留原坐标顺序和闭合状态。

兼容旧 `enterprises.floor_plan_url`：

- 迁移时按企业创建默认楼层，名称“默认总图”，`is_default=true`，`floor_plan_url` 使用旧企业字段。
- `enterprises.floor_plan_url` 保留为兼容字段。
- 新业务统一读取 `enterprise_floors.floor_plan_url`。

迁移 SQL 要点：

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

DO $$
DECLARE fk_name text;
BEGIN
    SELECT conname INTO fk_name
    FROM pg_constraint
    WHERE conrelid = 'enterprise_floors'::regclass
      AND contype = 'f'
      AND confrelid = 'enterprises'::regclass
      AND conname <> 'fk_ef_enterprise';
    IF fk_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE enterprise_floors DROP CONSTRAINT %I', fk_name);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_ef_enterprise'
          AND conrelid = 'enterprise_floors'::regclass
    ) THEN
        ALTER TABLE enterprise_floors
            ADD CONSTRAINT fk_ef_enterprise
            FOREIGN KEY (enterprise_id) REFERENCES enterprises(id) ON DELETE RESTRICT;
    END IF;
END $$;

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

迁移脚本必须支持幂等重跑，并生成预检报告。

### 4.7 删除与级联规则

目标：不允许数据库静默把风险对象置为无分区对象；所有风险分级数据删除必须由应用层按明确顺序执行，并提供可审计的确认信息。

外键策略：

- `enterprise_floors.enterprise_id -> enterprises.id`：`ON DELETE RESTRICT`。
- `risk_zones.floor_id -> enterprise_floors.id`：`ON DELETE RESTRICT`。
- `risk_objects.floor_id -> enterprise_floors.id`：`ON DELETE RESTRICT`。
- `risk_objects.zone_id -> risk_zones.id`：迁移时由现有 `SET NULL` 替换为 `ON DELETE RESTRICT`。
- `risk_units`、`risk_events`、`risk_measures` 继续使用 `ON DELETE CASCADE`，由 ORM/应用层按依赖顺序删除。

分区删除流程：

1. 后端统计分区下 `risk_objects`、`risk_units`、`risk_events`、`risk_measures` 数量。
2. 分区下没有任何风险对象时，直接删除分区。
3. 分区下存在风险对象或风险事件时，返回 `CASCADE_CONFIRM_REQUIRED`，`detail.data` 包含 `object_count`、`unit_count`、`event_count`、`measure_count`。
4. 用户通过 `confirm_cascade_zone_ids` 二次确认后，同一事务内按“措施 -> 事件 -> 单元 -> 风险对象 -> 分区”顺序删除。
5. 删除分区不自动删除楼层；删除后不得保留 `zone_id=null` 的工作台风险点。

楼层删除规则：

- 楼层下存在分区或风险对象时返回 `FLOOR_IN_USE`，不提供级联删除。
- 必须先删除或迁移该楼层分区后，才能删除楼层。
- 唯一默认楼层不可直接删除，必须先设置新的默认楼层。

企业删除规则：

- 现有 `DELETE /enterprises/{enterprise_id}` 改为调用新增 `enterprise_cleanup_service`，不再仅依赖数据库级联。
- 应用层同一事务内按“措施 -> 事件 -> 单元 -> 风险对象 -> 分区 -> 楼层 -> 企业”顺序清理。
- 企业下其他历史业务数据仍沿用现有数据库级联；本服务只负责避免 `RESTRICT` 外键与新增楼层数据产生删除冲突。
- 平面图物理文件在业务事务提交成功后清理；清理失败只记录日志，不回滚业务删除。
- 企业删除接口返回待清理数量，前端必须二次确认。

---

## 5. API 设计

### 5.1 通用约定

继续使用现有路由前缀：

```text
/api/v1/enterprises/{enterprise_id}/risk-management
```

- 成功响应使用 `ApiResponse<T>`。
- 鉴权沿用 `get_current_user`，所有接口校验企业归属。
- 业务错误返回 HTTP 状态码 + `detail.code` + `detail.message` + 可选 `detail.data`。

错误示例：

```json
{
  "detail": {
    "code": "ZONE_NOT_BOUND",
    "message": "当前楼层存在未绑定区域，不能保存",
    "data": {
      "pending_region_ids": ["pending-region-1"]
    }
  }
}
```

### 5.2 Floors CRUD

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/floors` | 获取企业楼层列表 |
| POST | `/floors` | 新建楼层 |
| GET | `/floors/{floor_id}` | 获取单楼层 |
| PUT | `/floors/{floor_id}` | 更新楼层 |
| DELETE | `/floors/{floor_id}` | 删除楼层 |
| POST | `/floors/{floor_id}/plan` | 上传楼层平面图 |

`FloorCreate`：

```json
{
  "name": "一层",
  "sort_order": 1,
  "floor_plan_url": null,
  "description": "生产车间",
  "canvas_width": 1200,
  "canvas_height": 900,
  "canvas_texts": [],
  "is_default": false
}
```

`FloorUpdate` 使用同结构，字段可部分更新。

`FloorResponse`：

```json
{
  "id": "floor-id",
  "enterprise_id": "enterprise-id",
  "name": "一层",
  "sort_order": 1,
  "floor_plan_url": "/uploads/floors/floor-1.png",
  "description": "生产车间",
  "canvas_width": 1920,
  "canvas_height": 1080,
  "canvas_texts": [],
  "is_default": false,
  "zone_count": 5,
  "risk_point_count": 12,
  "created_at": "2026-08-04T10:00:00+08:00",
  "updated_at": "2026-08-04T10:00:00+08:00"
}
```

规则：

- `name` 必填，同一企业内唯一。
- 企业没有楼层时，`GET /floors`、`GET /workbench` 首次访问自动创建默认楼层，并复用 `enterprises.floor_plan_url`。
- 企业第一个楼层必须设置为默认楼层；已有默认楼层时，新楼层不能直接覆盖默认标记，必须先替换默认楼层。
- 设置 `is_default=true` 时，同一事务清除该企业其他默认楼层。
- 不允许删除唯一默认楼层；不允许直接删除存在分区或风险对象的楼层。
- 上传平面图成功后返回新的 `floor_plan_url`。
- 更新默认楼层平面图时同步写回 `enterprises.floor_plan_url`。

`POST /floors/{floor_id}/plan` 请求与行为：

- `Content-Type`：`multipart/form-data`，字段 `file` 必填，类型为图片文件。
- 支持类型：`image/png`、`image/jpeg`、`image/webp`。
- 文件大小限制：不超过 20 MB。
- 像素限制：长边不超过 12000 像素，短边不超过 12000 像素。
- 存储路径：`uploads/enterprises/{enterprise_id}/floors/{floor_id}/{yyyyMMdd}_{uuid}.{ext}`；如项目已有统一对象存储或上传服务，优先复用。
- 校验通过后写入 `floor_plan_url`，并从图片尺寸写入 `canvas_width`、`canvas_height`。
- 若该楼层 `is_default=true`，同一事务内同步写回 `enterprises.floor_plan_url`。
- 新文件提交成功后，尽力删除旧平面图文件；删除失败只记录日志，不影响本次更新。
- 上传过程中任一校验失败，必须清理临时文件。
- 响应为 `FloorResponse`，包含新 `floor_plan_url`、`canvas_width`、`canvas_height`、`updated_at`。

### 5.3 Workbench 聚合加载

```text
GET /workbench?floor_id={floor_id}
```

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "floors": [
      {
        "id": "floor-id",
        "enterprise_id": "enterprise-id",
        "name": "一层",
        "description": "生产车间",
        "floor_plan_url": "/uploads/floors/floor-1.png",
        "canvas_width": 1920,
        "canvas_height": 1080,
        "canvas_texts": [],
        "is_default": false,
        "sort_order": 1
      }
    ],
    "zones": [
      {
        "id": "zone-id",
        "enterprise_id": "enterprise-id",
        "floor_id": "floor-id",
        "name": "原料库",
        "description": "原料储存区域",
        "sort_order": 1,
        "updated_at": "2026-08-04T10:00:00+08:00",
        "floor_plan_polygon": {
          "version": 2,
          "color_source": "auto",
          "color": "#fa8c16",
          "polygons": []
        },
        "max_risk_level": "较大",
        "effective_color": "#fa8c16",
        "object_count": 3,
        "objects": []
      }
    ],
    "risk_points": [
      {
        "id": "object-id",
        "enterprise_id": "enterprise-id",
        "zone_id": "zone-id",
        "floor_id": "floor-id",
        "name": "储罐区风险点",
        "category": "危险化学品",
        "description": "新建风险点",
        "image_url": null,
        "location_x": 32.5,
        "location_y": 45.2,
        "is_risk_point": true,
        "updated_at": "2026-08-04T10:00:00+08:00"
      }
    ]
  }
}
```

规则：

- `floor_id` 缺省时返回默认楼层数据。
- 聚合接口返回当前楼层全部分区、风险点、楼层文字和全部楼层元数据。
- 分区和风险点响应必须包含 `updated_at`，前端保存时原样回传用于并发检测。
- `zones[].objects` 为可选的聚合明细；前端也可以只使用独立的 `risk_points` 列表，不强制重复挂载。
- 多边形统一规范化为 v2，并补齐有效色值。

### 5.4 Zones / Objects 扩展

`GET /zones` 新增 `floor_id` 查询参数。

`RiskZoneCreate`：

```json
{
  "floor_id": "floor-id",
  "name": "原料库",
  "description": "原料储存区域",
  "sort_order": 1,
  "floor_plan_polygon": {
    "version": 2,
    "color_source": "auto",
    "color": null,
    "polygons": []
  }
}
```

`RiskZoneResponse` 新增 `floor_id`、`floor_name`、`floor_plan_polygon`、`max_risk_level`、`effective_color`。

`RiskZoneUpdate` 支持更新 `floor_id`。移动分区到其他楼层时，同事务内同步更新该分区下所有风险对象的 `floor_id`。

`GET /objects` 新增 `floor_id` 查询参数。

`RiskObjectCreate` 支持新增 `floor_id`，工作台新建风险点示例：

```json
{
  "zone_id": "zone-id",
  "floor_id": "floor-id",
  "name": "储罐区风险点",
  "category": "危险化学品",
  "location": "罐区西北角",
  "location_x": 32.5,
  "location_y": 45.2,
  "is_risk_point": true
}
```

校验规则：

- `zone_id` 与 `floor_id` 同时提供时必须一致。
- `zone_id` 已提供但 `floor_id` 为空时，服务端自动沿用所属分区 `floor_id`。
- 新建风险点必须提供 `zone_id`、`location_x`、`location_y`；`floor_id` 可省略并由服务端推导。
- 坐标范围 0-100。

旧 CRUD 兼容规则：

- `RiskZoneCreate.floor_id` 兼容为空；为空时服务端自动解析企业默认楼层，避免旧表单创建无楼层分区。
- `RiskZoneUpdate.floor_id` 可为空表示不修改楼层；移动分区时同一事务内同步更新该分区下所有风险对象的 `floor_id`。
- `RiskObjectCreate.floor_id` 兼容为空；`zone_id` 非空时沿用分区楼层，`zone_id` 与 `floor_id` 均为空时允许普通对象暂不归属楼层。
- `RiskObjectCreate` 或 `RiskObjectUpdate` 设置 `is_risk_point=true` 时，`zone_id`、`location_x`、`location_y` 必须提供，否则返回 `RISK_POINT_INVALID`。
- 旧前端继续提交 `floor_plan_polygon` 时，后端统一归一化为 v2；迁移完成后写入结构应始终为 v2。

### 5.5 Hierarchy 与 Overview

`GET /hierarchy` 新增 `floor_id` 查询参数。

`HierarchyZoneResponse` 扩展：

- `floor_id`
- `floor_name`
- `floor_plan_polygon`
- `max_risk_level`
- `effective_color`

`HierarchyObjectResponse` 扩展：

- `floor_id`
- `location_x`
- `location_y`

新增 `GET /overview?floor_id={floor_id}`，返回按楼层聚合的只读数据，供总览页渲染。

`OverviewResponse`：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "floor": {
      "id": "floor-id",
      "enterprise_id": "enterprise-id",
      "name": "一层",
      "floor_plan_url": "/uploads/floors/floor-1.png",
      "canvas_width": 1920,
      "canvas_height": 1080,
      "is_default": false,
      "sort_order": 1
    },
    "zones": [
      {
        "id": "zone-id",
        "name": "原料库",
        "floor_id": "floor-id",
        "floor_plan_polygon": {
          "version": 2,
          "color_source": "auto",
          "color": "#fa8c16",
          "polygons": []
        },
        "max_risk_level": "较大",
        "effective_color": "#fa8c16",
        "object_count": 3,
        "objects": []
      }
    ],
    "risk_points": []
  }
}
```

规则：总览接口为只读数据源，不提供编辑能力；分区、风险点、颜色、多边形和楼层均按当前楼层过滤。

### 5.6 工作台批量保存

```text
POST /workbench/batch-save
```

请求体：

```json
{
  "floor_id": "floor-id",
  "floor_updated_at": "2026-08-04T10:00:00+08:00",
  "zones": [
    {
      "client_id": "zone-client-1",
      "zone_id": "zone-id",
      "name": "原料库",
      "description": "原料储存区域",
      "sort_order": 1,
      "updated_at": "2026-08-04T10:00:00+08:00",
      "floor_plan_polygon": {
        "version": 2,
        "color_source": "manual",
        "color": "#ff4d4f",
        "polygons": [
          {
            "id": "zone-region-1",
            "label": "原料库北区",
            "points": [
              { "x": 12.5, "y": 18.2 },
              { "x": 35.1, "y": 18.2 },
              { "x": 35.1, "y": 42.6 },
              { "x": 12.5, "y": 42.6 }
            ]
          }
        ]
      }
    }
  ],
  "risk_points": [
    {
      "client_id": "risk-point-client-1",
      "id": null,
      "name": "储罐区风险点",
      "category": "危险化学品",
      "description": "新建风险点",
      "zone_id": "zone-id",
      "zone_client_id": null,
      "floor_id": "floor-id",
      "location_x": 32.5,
      "location_y": 45.2
    },
    {
      "client_id": "risk-point-client-2",
      "id": "existing-object-id",
      "name": "既有风险点",
      "updated_at": "2026-08-04T10:00:00+08:00",
      "zone_id": "zone-id",
      "zone_client_id": null,
      "floor_id": "floor-id",
      "location_x": 33.1,
      "location_y": 46.0
    }
  ],
  "deleted_risk_point_ids": [],
  "deleted_zone_ids": [],
  "confirm_cascade_zone_ids": [],
  "texts": [
    {
      "id": "text-1",
      "content": "原料库",
      "x": 12.5,
      "y": 34.2,
      "font_size": 14,
      "color": "#333333",
      "rotation": 0,
      "sort_order": 0
    }
  ]
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| floor_id | UUID | 是 | 当前楼层 |
| floor_updated_at | datetime | 是 | 楼层 `updated_at`，用于画布相关数据并发检测 |
| zones | array | 是 | 保存后当前楼层应存在的全部分区 |
| zones[].client_id | string | 新建时必填 | 前端生成的临时 ID，用于同批风险点绑定 |
| zones[].zone_id | UUID/null | 条件 | null 表示新建分区 |
| zones[].name | string | 新建时必填 | 分区名称 |
| zones[].updated_at | datetime/null | 既有分区必填 | 用于并发冲突检测 |
| zones[].floor_plan_polygon | object | 是 | v2 结构，polygons 非空 |
| risk_points | array | 否 | 新建或更新风险点 |
| risk_points[].client_id | string | 新建时必填 | 前端生成的临时 ID，用于响应回填 |
| risk_points[].id | UUID/null | 条件 | null 表示新建 |
| risk_points[].name | string | 新建时必填 | 风险点名称 |
| risk_points[].zone_id | UUID/null | 条件 | 绑定已有分区；新建分区时可为 null |
| risk_points[].zone_client_id | string/null | 条件 | 绑定同批新建分区时填该分区的 client_id |
| risk_points[].updated_at | datetime/null | 既有风险点必填 | 用于并发冲突检测 |
| risk_points[].floor_id | UUID | 否 | 缺省时按 zone 推导 |
| risk_points[].location_x/y | number | 是 | 0-100 坐标 |
| deleted_risk_point_ids | array | 否 | 删除的风险点 ID |
| deleted_zone_ids | array | 否 | 删除的分区 ID |
| confirm_cascade_zone_ids | array | 否 | 确认级联删除的分区 ID |
| texts | array | 否 | 当前楼层文字标注全量 |

批量保存规则：

- 保存前校验当前楼层所有未删除分区都已出现在 `zones`，且 `polygons` 非空。
- 保存前锁定当前楼层，并比较请求 `floor_updated_at` 与数据库 `updated_at`；不一致返回 `SAVE_CONFLICT`。
- 请求内所有 `client_id` 必须唯一；`zones[].client_id` 与 `risk_points[].client_id` 不得互相冲突。
- `risk_points[].zone_id` 与 `risk_points[].zone_client_id` 不允许同时提供，且必须能解析到唯一分区。
- 分区 `zone_id=null` 时创建新分区；新分区必须提供 `client_id`，后端在事务内创建后生成 `client_id -> zone_id` 映射。
- 风险点 `zone_id=null` 且 `zone_client_id` 非空时，先按同批新建分区映射解析目标分区；找不到对应 `client_id` 返回 `ZONE_NOT_FOUND`。
- 风险点 `id=null` 时创建 `risk_objects`，强制 `is_risk_point=true`；新风险点必须提供 `client_id`，响应中回填 `client_id -> object_id` 映射。
- 风险点更新时校验对象存在且属于当前企业、当前楼层；同时比较请求中的 `updated_at` 与数据库 `updated_at`，不一致返回 `SAVE_CONFLICT`。
- 既有分区同样比较 `updated_at`，不一致返回 `SAVE_CONFLICT`。
- 删除分区时，若分区下存在风险事件，必须在 `confirm_cascade_zone_ids` 中显式确认；未确认返回 `CASCADE_CONFIRM_REQUIRED`。
- 本接口不处理楼层名称、平面图、画布尺寸、默认楼层等楼层元数据；楼层元数据通过 Floors CRUD 独立维护。
- 所有校验通过后单事务写入。
- 事务中使用 `SELECT ... FOR UPDATE` 锁定楼层、分区、风险点，防止并发覆盖。
- 任一步失败整体回滚。

响应返回更新后的楼层、分区、风险点、文字，以及新建实体映射：

```json
{
  "code": 0,
  "message": "保存成功",
  "data": {
    "floor": {
      "id": "floor-id",
      "name": "一层",
      "floor_plan_url": "/uploads/floors/floor-1.png",
      "canvas_texts": [],
      "updated_at": "2026-08-04T10:01:00+08:00"
    },
    "zones": [],
    "risk_points": [],
    "texts": [],
    "created_zone_map": {
      "zone-client-1": "new-zone-id"
    },
    "created_risk_point_map": {
      "risk-point-client-1": "new-object-id"
    }
  }
}
```

前端保存后使用映射替换本地临时 ID，并用响应刷新 store。
响应中的 `floor.updated_at` 必须回填到本地 `floor_updated_at`，作为下一次批量保存的并发基线。

### 5.7 错误码

| HTTP | code | 场景 |
|---|---|---|
| 400 | INVALID_PAYLOAD | 请求体结构不合法 |
| 404 | FLOOR_NOT_FOUND | 楼层不存在或不属于当前企业 |
| 404 | ZONE_NOT_FOUND | 分区不存在或不属于当前企业 |
| 404 | RISK_POINT_NOT_FOUND | 风险点不存在或不属于当前企业 |
| 409 | FLOOR_IN_USE | 楼层存在分区或风险对象，不允许删除 |
| 409 | SAVE_CONFLICT | 并发保存冲突 |
| 409 | CASCADE_CONFIRM_REQUIRED | 删除分区需要显式确认级联风险对象/风险事件，data 返回各层级影响数量 |
| 422 | ZONE_NOT_BOUND | 当前楼层存在未绑定区域 |
| 422 | ZONE_FLOOR_MISMATCH | 分区或风险点楼层不一致 |
| 422 | POLYGON_INVALID | v2 结构、点数、坐标范围不合法 |
| 422 | DUPLICATE_POLYGON_ID | 分区内多边形 ID 重复 |
| 422 | RISK_POINT_INVALID | 新建风险点缺少名称、分区或坐标 |
| 422 | POINT_OUT_OF_RANGE | 坐标不是 0-100 有限数值 |

---

## 6. 前端设计

### 6.1 路由与入口

新增路由：

```tsx
{ path: "/enterprises/:id/risk-mapping-workbench", element: <RiskMappingWorkbenchPage /> }
```

入口：

- `RiskManagementTab` 工具栏新增“四色分布图工作台”按钮。
- `RiskOverviewPage` 顶部新增“编辑四色图”按钮，可带 `floor_id`、`zone_id` 查询参数。
- 工作台顶部提供“返回风险分级管控”和“预览总览”。

### 6.2 数据加载

页面加载调用 `GET /workbench?floor_id=...`，并额外读取企业信息。

如果企业没有楼层数据，前端调用 `GET /floors` 或 `GET /workbench` 时由后端自动创建默认楼层；前端不得自行在本地伪造楼层。默认楼层创建后复用旧 `enterprise.floor_plan_url`。

### 6.3 工作台布局

```text
+--------------------------------------------------------------+
| 顶部：返回 / 标题 / 楼层切换 / 保存 / 预览总览                |
+--------------------------------------------------------------+
| 工具栏：选择 矩形 多边形 自由画笔 风险点 文字 网格 吸附 撤销... |
+----------+-----------------------------------------+----------+
| 左栏      | 画布                                     | 右栏      |
| 分区/风险点/待绑定 | 平面图或空白画布 + 四色区域 + 图例 | 属性/校验 |
+----------+-----------------------------------------+----------+
```

布局约束：

- 左栏 280px，右栏 320px，画布 `minmax(0, 1fr)`。
- 画布区域通过 `ResizeObserver` 适配容器。
- 待绑定数量在左栏和保存按钮旁同时展示。

### 6.4 工具栏

工具分组：

- 绘制：矩形、多边形、自由画笔、风险点、文字。
- 编辑：选择/移动、删除、撤销、重做。
- 辅助：网格、吸附、辅助线、缩放、平移、图例。

交互规则：

- 按钮使用图标 + Tooltip。
- 矩形绘制过程中显示 `Rect`，完成后转为四点多边形。
- 多边形逐点点击，双击或点击首顶点闭合。
- 自由画笔按住拖动画出轨迹，松开后转闭合多边形。
- 风险点工具点击画布创建风险点草稿。
- 文字工具点击画布创建文字草稿。
- 滚轮缩放，空格/中键平移，双击适配画布。

### 6.5 左侧分区面板

左栏使用 Tabs：

- 分区：只显示当前楼层分区；显示名称、风险等级、颜色、区域数、风险点数。
- 风险点：显示当前楼层 `is_risk_point=true` 对象；无坐标对象标记“未定位”。
- 待绑定：显示未绑定分区草稿区域，支持绑定已有分区、绑定新分区、删除。

### 6.6 画布与图层

图层顺序：

1. 楼层图片层
2. 网格层
3. 分区层
4. 风险点层
5. 文字层
6. 草图层
7. 辅助线层
8. 选中/顶点层

规则：

- 分区多边形使用闭合 `Line`。
- 风险点使用 `Circle` + `Text`。
- 文字使用 `Text`。
- 多边形选中显示自定义顶点手柄，不使用 Transformer。
- 文字和草稿矩形选中使用 Transformer。
- 所有节点设置 `perfectDrawEnabled={false}`。

### 6.7 右侧属性面板

按选中对象显示：

- 分区：名称、楼层、描述、最高风险等级、自动色、颜色来源、手动颜色、区域列表、风险点列表、删除分区。
- 区域：所属分区、楼层、顶点数、坐标范围、绑定/解绑、删除区域。
- 风险点：名称、类别、位置描述、所属分区、坐标、删除。
- 文字：内容、字号、颜色、旋转、删除。
- 未选中：画布设置、网格/吸附/辅助线开关、当前楼层图片状态、待绑定数量。

### 6.8 楼层管理

`EnterpriseFloorManager` 放在 `EnterpriseEditPage` 的“GIS 定位与平面图”区域：

- 支持新增、重命名、删除、排序、默认楼层设置。
- 每层单独上传平面图。
- 上传后从图片自然尺寸初始化 `canvas_width`、`canvas_height`。
- 无图片楼层使用默认画布尺寸 1200 x 900。
- 删除楼层前确认，存在分区或风险点不允许删除。

### 6.9 风险点交互

已有风险点：

- 加载 `is_risk_point=true` 对象。
- 有坐标直接渲染在画布。
- 无坐标在左栏显示，可拖到画布。
- 画布内使用 Konva `draggable`，拖拽结束写入百分比坐标。

新建风险点：

- 选择风险点工具后点击画布创建草稿。
- 默认楼层为当前楼层。
- 如果当前选中分区，默认写入 `zone_id`。
- 属性面板维护名称、类别、描述、位置描述、坐标、所属分区。
- 保存时必须绑定分区并填写名称。

### 6.10 待绑定清单

- 未选中分区时绘制完成的区域进入 `pendingRegions`。
- 支持绑定已有分区、新建分区、删除。
- 保存前必须为空。
- 切换楼层后按楼层过滤，其他楼层草稿不丢失。

### 6.11 总览联动

- 替换 `RiskOverviewPage` 的 `FloorPlanHeatmap` 占位。
- 顶部使用 `FloorSwitcher`。
- 使用只读 `RiskDistributionStage` 渲染当前楼层。
- 点击分区/风险点联动右侧层级树。
- 工作台保存成功后失效 `risk-workbench`、`risk-hierarchy`、`enterprise-floors` 等查询键。

### 6.12 前端类型与服务

核心类型：

```ts
export type RiskLevel = "重大" | "较大" | "一般" | "低" | "未评估";
export type ColorSource = "auto" | "manual";

export interface RiskPolygonPoint {
  x: number;
  y: number;
}

export interface RiskPolygon {
  id: string;
  label?: string;
  points: RiskPolygonPoint[];
}

export interface RiskZoneFloorPlanPolygon {
  version: 2;
  color_source: ColorSource;
  color: string | null;
  polygons: RiskPolygon[];
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

export interface RiskZone {
  id: string;
  enterprise_id: string;
  floor_id: string | null;
  floor_name: string | null;
  name: string;
  description: string | null;
  sort_order: number;
  floor_plan_polygon: RiskZoneFloorPlanPolygon | null;
  max_risk_level: RiskLevel | null;
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
}

export interface WorkbenchZone extends RiskZone {
  objects?: RiskObject[];
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
  riskPoints: RiskObject[];
  texts: RiskCanvasText[];
  pendingRegions: PendingRegion[];
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
  zones: RiskZone[];
  risk_points: RiskObject[];
  texts: RiskCanvasText[];
  created_zone_map: Record<string, string>;
  created_risk_point_map: Record<string, string>;
}

export interface RiskMappingOverviewResponse {
  floor: EnterpriseFloor;
  zones: WorkbenchZone[];
  risk_points: RiskObject[];
}

export interface HierarchyObject extends Pick<RiskObject, "id" | "name" | "category" | "is_risk_point" | "floor_id" | "location_x" | "location_y"> {
  units: unknown[];
  events: unknown[];
}

export interface HierarchyZone extends Pick<RiskZone, "id" | "name" | "description" | "floor_id" | "floor_name" | "floor_plan_polygon" | "max_risk_level" | "effective_color"> {
  objects: HierarchyObject[];
}
```

说明：`BatchSaveZoneItem`、`BatchSaveRiskPointItem` 在实现时应使用 discriminated union 约束“新建必填 client_id/name”和“既有必填 id/updated_at”，避免可选字段导致前端构造非法请求。

新增服务：

- `getRiskMappingWorkbench`
- `saveRiskMappingWorkbench`
- `listEnterpriseFloors`
- `createEnterpriseFloor`
- `updateEnterpriseFloor`
- `deleteEnterpriseFloor`
- `uploadEnterpriseFloorPlan`

前端依赖新增：

- `konva`
- `react-konva`

---

## 7. 状态管理与画布适配

### 7.1 Zustand Store

新增 `riskMappingWorkbenchStore`，保存当前楼层可编辑快照：

- `floors`
- `currentFloorId`
- `zones`
- `riskPoints`
- `texts`
- `pendingRegions`
- `selected`
- `tool`
- `viewport`
- `gridEnabled`
- `snapEnabled`
- `guideEnabled`
- `past` / `future`
- `dirty`

规则：

- 撤销/重做记录几何、颜色、绑定、风险点、文字，不记录 viewport/tool/selected。
- 每次绘制完成、拖拽结束、绑定完成、颜色修改、文字修改后 commit。
- 页面离开前检查 dirty，有未保存修改时确认。
- 保存成功后重置 dirty 并清空历史栈。

### 7.2 Konva 使用规则

```tsx
<Stage width={viewportWidth} height={viewportHeight}>
  <Layer>
    <Group x={viewport.x} y={viewport.y} scaleX={viewport.scale} scaleY={viewport.scale}>
      {/* layers */}
    </Group>
  </Layer>
</Stage>
```

- 内容统一放在一个可缩放平移的 Group 内。
- 多边形使用闭合 Line，选中后显示顶点 Circle。
- 文字和矩形使用 Transformer。
- 变换结束把 scale 换算回持久化字段。

### 7.3 坐标转换

持久化坐标统一为 0-100 百分比：

```ts
export function percentToStage(point: RiskPolygonPoint, floor: EnterpriseFloor) {
  const w = floor.canvas_width ?? 1200;
  const h = floor.canvas_height ?? 900;
  return {
    x: (point.x / 100) * w,
    y: (point.y / 100) * h,
  };
}

export function stageToPercent(position: { x: number; y: number }, floor: EnterpriseFloor) {
  const w = floor.canvas_width ?? 1200;
  const h = floor.canvas_height ?? 900;
  return {
    x: clamp((position.x / w) * 100, 0, 100),
    y: clamp((position.y / h) * 100, 0, 100),
  };
}
```

- 指针坐标使用 Group `getRelativePointerPosition()`。
- 加载时百分比转世界坐标，保存前世界坐标转百分比。
- 楼层图片更换后保留百分比坐标。

### 7.4 缩放、网格与吸附

- 缩放范围 0.25 到 4，滚轮以鼠标为中心。
- 双击适配全部。
- 网格默认间隔 10 画布像素，只在编辑态显示。
- 吸附默认容差 6 画布像素。
- 吸附目标：网格、已有多边形顶点、边中点、风险点中心、文字包围盒中心。
- 辅助线动态显示对齐线，不持久化。

### 7.5 自由画笔转多边形

- 按 4 像素最小距离采样。
- 去重和轻量简化。
- 点数大于等于 3 时闭合。
- 预览用 Line tension，保存时转为普通多边形顶点。

---

## 8. 保存与校验

### 8.1 前端校验

保存按钮触发统一校验：

- 待绑定清单为空。
- 当前楼层所有分区至少有一个区域。
- 每个多边形至少 3 个顶点。
- 多边形面积大于 0。
- 坐标 0-100。
- `floor_updated_at` 来自最近一次工作台/楼层加载，不能为空。
- 同一分区所有多边形属于同一楼层。
- 风险点必须有名称、分区、楼层、坐标。
- 新建风险点 `is_risk_point=true`。
- 文字内容非空。

### 8.2 后端校验

- 请求体 JSON 结构合法。
- 楼层属于当前企业。
- 分区属于当前企业且属于当前楼层。
- 风险点属于当前企业且属于当前楼层。
- 未绑定区域和缺失分区拒绝保存。
- 手动颜色合法。
- 多边形结构和坐标合法。

### 8.3 并发与事务

- 批量保存单事务。
- 使用 `SELECT ... FOR UPDATE` 锁定当前楼层、分区、风险点。
- 当前楼层必须比较 `floor_updated_at`，覆盖平面图替换、楼层文字、画布尺寸等画布相关变更；不一致返回 `SAVE_CONFLICT`。
- 既有分区和既有风险点必须比较各自 `updated_at`，不一致返回 `SAVE_CONFLICT`。
- 首版不承诺实时协同，冲突时提示用户刷新或重新合并。

---

## 9. 权限与安全

- 所有接口沿用现有登录鉴权和企业归属校验。
- 只读角色只能查看工作台和总览，不能进入编辑或调用批量保存。
- 文件上传限制图片类型、大小和像素尺寸。
- 上传失败时清理临时文件。
- 删除分区或企业时必须校验写权限，并返回影响数量供前端二次确认。
- 输入校验不允许任意 SQL、路径穿越、恶意多边形坐标。

---

## 10. 性能与容量

首版性能目标：

- 单楼层 200 个区域、500 个风险点、5000 个顶点时，首屏加载不超过 3 秒。
- 普通桌面浏览器拖拽无明显卡顿。
- 批量保存不超过 3 秒。

优化手段：

- 按楼层加载，避免一次加载全部楼层。
- 使用 Konva Layer 分层渲染。
- 拖拽过程不频繁触发保存。
- 自由画笔点集简化。
- 大数据量时提示拆分或简化。

---

## 11. 兼容与迁移

### 11.1 兼容规则

- `floor_plan_polygon` 新旧格式同时可读。
- 旧 `enterprises.floor_plan_url` 保留。
- 旧 `risk_zones` 无 `floor_id` 时通过迁移回填默认楼层。
- 旧 `risk_objects` 无 `floor_id` 时优先沿用所属分区楼层。
- 迁移期间旧功能继续可用。

### 11.2 迁移步骤

1. 生成全量数据快照和预检报告。
2. 创建默认楼层并绑定旧平面图。
3. 回填 `risk_zones.floor_id`。
4. 回填 `risk_objects.floor_id`。
5. 转换旧 `points` 为 v2 `polygons`。
6. 迁移后校验无缺失 `floor_id`、无跨楼层分区、记录数一致。
7. 迁移可幂等重跑，失败企业整体回滚。

说明：`4.6` 的 SQL 是全库迁移基线，可在单个迁移事务中执行；若需要单企业部分回滚，应由应用层迁移服务按企业循环调用同一套校验和回填逻辑。

---

## 12. 测试与验收标准

### 12.1 测试策略

| 测试层级 | 覆盖范围 |
|---|---|
| 后端单元 | v2 归一化、旧 points 兼容、颜色计算、楼层约束、未绑定校验、迁移幂等 |
| 后端 API | floors CRUD、workbench 加载、batch-save、错误码、权限、事务回滚、并发冲突 |
| 前端组件 | 工具栏、画布绘制、顶点编辑、风险点拖拽/新建、绑定、属性面板、总览联动 |
| 前端 Store | 楼层切换、脏状态、撤销/重做、保存载荷、失败恢复 |
| E2E | 登录、绘制、绑定、保存、刷新、总览联动、多层切换、旧数据迁移回归 |

### 12.2 验收标准

| 编号 | 验收项 | 通过条件 |
|---|---|---|
| AC-01 | 默认楼层 | 无楼层企业进入工作台自动存在默认楼层，旧总图可作默认底图 |
| AC-02 | 楼层切换 | 工作台/总览切换楼层后底图、分区、风险点只显示当前楼层 |
| AC-03 | 楼层维护 | 可新增、编辑、删除楼层；有数据的楼层和唯一默认楼层不可删除 |
| AC-04 | 跨楼层约束 | 分区不可跨楼层，保存跨楼层数据被拒绝 |
| AC-05 | 多边形绘制 | 保存后 v2 格式正确，刷新后形状一致 |
| AC-06 | 多区域分区 | 一个分区可包含多个不相邻区域，且同一楼层 |
| AC-07 | 未绑定限制 | 存在待绑定区域时禁止保存并给出提示 |
| AC-08 | 自动颜色 | 自动色随分区最高风险等级正确计算 |
| AC-09 | 手动颜色 | 手动覆盖持久化，清除覆盖后恢复自动色 |
| AC-10 | 风险点拖拽 | 已有风险点拖拽保存后坐标更新 |
| AC-11 | 新建风险点 | 新建风险点生成 risk_object 且 is_risk_point=true |
| AC-12 | 批量保存 | 单事务保存分区、颜色、风险点、楼层文字；失败整体回滚；楼层元数据由 Floors CRUD 独立保存 |
| AC-13 | 总览联动 | 保存后总览数据与工作台一致，点击分区联动层级树 |
| AC-14 | 文字标注 | 文字标注保存后刷新仍存在，位置和样式一致 |
| AC-15 | 撤销/重做 | 几何、颜色、绑定、风险点、文字可撤销/重做 |
| AC-16 | 旧坐标迁移 | 旧 points 转 polygons 后坐标、顺序、闭合关系不变 |
| AC-17 | 旧总图迁移 | 旧 floor_plan_url 迁移到默认楼层，原地址仍可用 |
| AC-18 | 迁移安全 | 迁移支持预检、单企业事务、失败回滚、幂等重跑 |
| AC-19 | 同批新建分区与风险点 | 工作台同批新建分区和风险点时，通过 client_id 映射保存，刷新后绑定关系正确 |
| AC-20 | 并发冲突 | 另一用户已修改楼层画布数据、分区或风险点后保存返回 SAVE_CONFLICT，不静默覆盖 |
| AC-21 | 级联删除确认 | 删除有风险对象或风险事件的分区必须显式确认，否则返回 CASCADE_CONFIRM_REQUIRED，并返回各层级影响数量 |
| AC-22 | 平面图上传 | 支持 PNG/JPEG/WebP，超限或非法文件被拒绝；上传成功返回新 URL、画布尺寸和 updated_at，默认楼层同步写回旧字段 |

---

## 13. 实施顺序

| 阶段 | 任务 | 依赖 | 估算 |
|---|---|---|---|
| 阶段 1 | 数据兼容与迁移基线（含外键 RESTRICT、企业清理服务） | 无 | 2.5 人日 |
| 阶段 2 | 后端工作台 API（含平面图上传、批量保存并发检测、级联删除确认） | 阶段 1 | 3 人日 |
| 阶段 3 | 前端状态与工作台框架 | 阶段 2 | 2.5 人日 |
| 阶段 4 | Konva 绘制与编辑 | 阶段 3 | 4 人日 |
| 阶段 5 | 绑定、颜色与保存校验 | 阶段 4 | 2 人日 |
| 阶段 6 | 总览联动与体验收尾 | 阶段 5 | 1.5 人日 |
| 阶段 7 | E2E、性能与发布验证 | 阶段 6 | 2.5 人日 |

合计约 18 人日。阶段 7 通过前不开放生产入口。

---

## 14. 受影响文件清单

### 后端

- `backend/app/models/enterprise.py`：新增 `EnterpriseFloor`。
- `backend/app/models/risk_management.py`：扩展 `RiskZone.floor_id`、`RiskObject.floor_id`。
- `backend/app/schemas/risk_management.py`：扩展楼层、分区、对象、层级、总览、批量保存 Schema。
- `backend/app/routers/risk_management.py`：新增 Floors、Workbench、Overview、Batch Save。
- `backend/app/routers/enterprises.py`：企业删除改为调用应用层清理服务。
- `backend/app/services/enterprise_cleanup_service.py`：新增企业级风险分级数据清理服务。
- `backend/app/services/floor_plan_storage_service.py`：新增平面图校验、存储、替换与旧文件清理。
- `backend/app/services/risk_mapping_service.py`：新增绘图业务服务。
- `backend/db_migration_risk_mapping_workbench.sql`：新增迁移。
- `backend/tests/test_risk_mapping_workbench.py`：新增后端工作台/批量保存测试。
- `backend/tests/test_risk_mapping_migration.py`：新增迁移兼容与幂等测试。
- `backend/tests/test_risk_mapping_cascade.py`：新增分区/企业删除确认与级联测试。
- `backend/tests/test_floor_plan_upload.py`：新增平面图上传校验与默认楼层同步测试。

### 前端

修改：

- `frontend/src/routes/index.tsx`
- `frontend/src/pages/Enterprise/RiskManagementTab.tsx`
- `frontend/src/pages/Enterprise/RiskOverviewPage.tsx`
- `frontend/src/pages/Enterprise/EnterpriseEditPage.tsx`
- `frontend/src/components/enterprise/RiskZoneForm.tsx`
- `frontend/src/components/enterprise/FloorPlanPicker.tsx`
- `frontend/src/components/enterprise/RiskObjectForm.tsx`
- `frontend/src/types/riskManagement.ts`
- `frontend/src/types/enterprise.ts`
- `frontend/src/services/riskManagementService.ts`
- `frontend/src/services/enterpriseService.ts`
- `frontend/package.json`

新增：

- `frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx`
- `frontend/src/types/riskMappingWorkbench.ts`
- `frontend/src/store/riskMappingWorkbenchStore.ts`
- `frontend/src/utils/riskMappingGeometry.ts`
- `frontend/src/components/enterprise/EnterpriseFloorManager.tsx`
- `frontend/src/components/enterprise/riskMapping/` 下工作台组件
- `frontend/src/store/riskMappingWorkbenchStore.test.ts`：新增 Store 测试。
- `frontend/e2e/risk-mapping-workbench.spec.ts`：新增 E2E 流程。

---

## 15. 风险与假设

### 假设

- 默认楼层可通过迁移确定；无楼层企业创建“默认总图”。
- 手动颜色覆盖按分区整体，不与区域级颜色冲突。
- 新建风险点必须绑定分区，避免画布出现无法归属的风险点。
- 每层使用一张底图，不处理图片旋转和比例尺校准。
- 工作台保存为整体提交，首版不支持多人实时协同。
- 旧 `enterprises.floor_plan_url` 保留为兼容字段，后续版本再清理。

### 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| 大数据量画布卡顿 | 高 | 按楼层加载、分层渲染、点集简化 |
| 批量保存部分成功 | 高 | 单事务 + 行锁 + 全量校验 |
| 图片上传和底图处理 | 中高 | 限制类型/大小/像素，失败自动清理 |
| 企业/分区级联误删 | 高 | 影响数量预览、二次确认、应用层单事务清理、级联测试 |
| 平面图文件残留 | 中 | 新文件提交成功后清理旧文件，失败记录日志 |
| 多人并发覆盖 | 中高 | 行锁 + 版本检测 + SAVE_CONFLICT |
| 旧数据兼容问题 | 中 | 迁移预检、幂等、抽样核对 |
| 坐标体系不一致 | 中 | 百分比坐标统一，测试图固定 |
| 权限和数据隔离 | 中 | 沿用现有鉴权和企业归属校验 |

---

## 16. 已解决的关键疑问

| 疑问 | 结论 |
|---|---|
| 多层厂房如何处理 | 首版完整支持 enterprise_floors，每层独立平面图 |
| 风险分区能否跨楼层 | 不能，risk_zones.floor_id NOT NULL |
| 一个分区能否多块 | 能，floor_plan_polygon.polygons 支持多区域 |
| 手动颜色按分区还是区域 | 按分区整体 |
| 新建风险点是否必须绑定分区 | 必须 |
| 无平面图能否使用 | 能，空白画布 + 网格/辅助线 |
| 旧单张平面图如何处理 | 迁移为默认楼层/总图 |
| 保存是否原子 | 是，批量保存单事务 |
| 楼层画布并发 | 批量保存校验 floor_updated_at，平面图/文字/画布尺寸变更触发 SAVE_CONFLICT |
| 删除分区 | 有风险对象或风险事件时必须显式确认，应用层按依赖顺序级联删除 |
| 删除企业 | 调用 enterprise_cleanup_service 显式清理新增楼层与风险分级数据，不依赖静默数据库级联 |
| 旧 CRUD 兼容 | 旧表单可不传 floor_id，服务端解析默认楼层；风险点仍强制绑定分区和坐标 |
