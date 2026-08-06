<!--
  文档元信息
  创建日期: 2026-08-06
  作者: Codex
  版本: 1.0
  状态: 待审查
  依赖: 风险分级管控层级树（RiskHierarchyTree）、四色分布图工作台楼层体系（enterprise_floors）
-->

# 风险分级管控分区树状图楼层分组 — 设计方案

## 1. 概述

### 1.1 背景

风险分级管控模块的层级树（分区 -> 对象 -> 单元 -> 事件 -> 措施）没有体现企业楼层关系，而四色分布图工作台已按楼层组织数据。排查发现两个问题：

- 数据层早已具备楼层关系（`risk_zones.floor_id/floor_name`、`risk_objects.floor_id`、`enterprise_floors`），但层级树完全没用上。
- 更严重：后端 `GET /risk-management/hierarchy` 在未传 `floor_id` 时只返回默认楼层的分区；风险管控页调用时未传 `floor_id`，导致多楼层企业**其他楼层的分区在树中完全不可见**，不仅是"没体现关系"。

本方案在保持现有层级结构不变的前提下，为树顶层增加楼层分组，并让分区创建/编辑真正感知楼层。

### 1.2 目标

- 树顶层新增楼层分组：企业 -> 楼层 -> 分区 -> 对象 -> 单元 -> 事件 -> 措施。
- 多楼层企业全部楼层分区在树中可见，不再只显示默认楼层。
- 新建分区可归属指定楼层；编辑分区可迁移楼层。
- 「在平面图上标注」的底图跟随选中楼层。
- 保持单楼层过滤能力（总览页继续使用）。

### 1.3 非目标

- 不改四色分布图工作台与可视化总览页。
- 不做三维厂房、楼层展开动画、跨楼层合并视图。
- 不迁移旧数据：`floor_id` 为 null 的历史分区归入「未分配楼层」兜底分组即可。
- 移动端不涉及（已确认不调用 `getFullHierarchy`）。

### 1.4 已确认决策

| 决策项 | 结论 |
|---|---|
| 优化方向 | 方案 A：树顶层楼层分组 + 添加分区楼层联动 |
| 后端接口 | `/hierarchy` 不传 `floor_id` 时返回企业全部楼层分区；响应结构不变 |
| 楼层数据源 | 前端并行 `GET /floors`（现有 `listFloors` 封装）提供排序、默认标记、分区数/风险点数 |
| 未分配兜底 | `floor_id` 为 null 的分区归入「未分配楼层」分组，置于楼层列表之后 |
| 展开策略 | 默认展开默认楼层，其余楼层折叠；单楼层企业保持全展开 |
| 楼层节点信息 | 楼层名称 + 默认徽标 + 分区数 + 风险点数 |
| 新建分区 | 从楼层节点「添加分区」进入时锁定该楼层；顶部「添加分区」默认选默认楼层、可修改 |
| 编辑分区 | 楼层可迁移；后端 `update_zone` 已有 `floor_id` 变更逻辑，直接复用 |
| 标注底图 | 跟随选中楼层 `floor_plan_url` |

### 1.5 用户故事

**场景 A：多层厂房安全员**

企业维护 1F/2F 两个楼层并分别上传平面图。安全员进入风险分级管控页，树顶层看到两个楼层节点，默认展开 1F；展开 2F 后能看到此前在 2F 工作台绘制的分区和对象。从 2F 楼层节点「添加分区」，新分区保存后归属 2F，「在平面图上标注」打开的是 2F 平面图。

**场景 B：迁移分区**

安全员把误建到 1F 的「危废暂存间」编辑迁移到 2F，保存后树中该分区自动归入 2F 楼层节点，其下风险对象楼层同步变更（后端既有逻辑）。

**场景 C：历史单楼层企业**

企业没有维护楼层或分区无楼层归属，树只显示一个「未分配楼层」分组，交互与现状一致。

## 2. 现状与断点

### 2.1 现有基础

- 后端 `GET /risk-management/hierarchy`（backend/app/routers/risk_management.py:691）：`floor_id` 为空取默认楼层，传了按楼层过滤；`HierarchyZoneResponse` 已含 `floor_id/floor_name`。
- 数据模型：`risk_zones.floor_id`、`risk_objects.floor_id`、`enterprise_floors（sort_order/is_default/floor_plan_url）`。
- 工作台：`load_workbench` 返回全部 floors；前端 `riskMappingWorkbenchService.listFloors` 已封装 `GET /floors`。
- 总览页：`RiskOverviewPage` 按 `effectiveFloorId` 传 `floor_id`，走单楼层过滤。

### 2.2 需要修复的断点

1. 层级树只显示默认楼层的分区（数据可见性 bug）。
2. 树顶层无楼层分组层（`RiskHierarchyTree.tsx` 的 `buildTreeData` 直接 zone 起步）。
3. 旧表单新建分区一律落默认楼层（`buildZonePayload` 不透传 `floor_id`，`RiskZoneForm` 无楼层字段）。
4. 「在平面图上标注」底图固定为父级传入的默认楼层 URL。

## 3. 后端设计

### 3.1 `/hierarchy` 行为调整

- `floor_id` 为空：返回企业**全部楼层**的分区，按（楼层 `sort_order`，分区 `sort_order`）排序。
- `floor_id` 非空：维持现有单楼层过滤，总览页不受影响。
- 响应模型不变：`ApiResponse[list[HierarchyZoneResponse]]`，每个 zone 已含 `floor_id/floor_name`，无需新增字段。
- 实现要点：先查企业全部 `EnterpriseFloor` 建排序映射；再查企业全部 `RiskZone`（沿用现有 `selectinload` 加载对象/单元/事件/措施）；内存分组排序后返回。企业无楼层时退化为"全部归入未分配"，行为与现状一致。

### 3.2 复用与不涉及

- 无表结构变更、无迁移脚本。
- 分区迁移楼层的对象同步逻辑已存在于 `update_zone`（risk_management.py:484-489），直接复用。

## 4. 前端设计

### 4.1 数据加载（RiskManagementTab）

- 并行 `useQuery`：`getFullHierarchy(eid)`（全部楼层）+ `listFloors(eid)`。
- `listFloors` 提供楼层顺序、默认标记、`zone_count/risk_point_count`、每层 `floor_plan_url`。
- 向 `RiskHierarchyTree` 传入 `data + floors`；向 `RiskZoneForm` 传入当前选中楼层的 `floor_plan_url`（替代父级默认楼层 URL，父级传参保留为兜底）。

### 4.2 树结构（RiskHierarchyTree）

- 新增 `floor` 节点类型：key = `floor-{id}`，标题显示楼层 emoji、名称、默认徽标（默认楼层）、分区数/风险点数；childCount = 分区数。
- `buildTreeData` 改造：按 `floor_id` 分组（顺序取 `floors.sort_order`），`floor_id` 为 null 或楼层不存在时归入「未分配楼层」兜底组（置于最后）；原 zone 及以下层级逻辑不变。
- 操作：楼层节点提供「添加分区」，`onAction("add-zone", meta)` 携带 `floorId/floorName`。
- 展开策略：多楼层默认展开默认楼层、其余折叠；单楼层（或仅未分配组）保持现有 `defaultExpandAll` 行为。
- 点击楼层节点：右侧详情面板展示楼层信息（名称、默认标记、分区数、风险点数）。

### 4.3 表单楼层联动（RiskZoneForm / zoneSubmit）

- `buildZonePayload` 增加可选 `floor_id` 透传：创建时必传（来自表单状态）；编辑时若楼层未改动则不传，避免误清已有归属（沿用现有"多边形仅在有值时提交"的防御风格）。
- `RiskZoneForm` 增加楼层 Select：
  - 数据来自 `listFloors`；
  - 从楼层节点「添加分区」进入：默认锁定该楼层，仍允许切换；
  - 顶部「添加分区」进入：默认选默认楼层；
  - 编辑分区：显示当前楼层，可切换迁移；
  - 企业无楼层时隐藏 Select。
- `floorPlanUrl` 状态跟随所选楼层：楼层切换时更新「在平面图上标注」底图。

### 4.4 类型与消费方

- `TreeNodeMeta` 增加 `floorId?/floorName?`；`RiskManagementTab` 的 `handleTreeAction` 增加 `add-zone` 分支（楼层节点进入时预设楼层）。
- 现有 `getFullHierarchy` 类型与调用不变；总览页继续传 `floor_id`。

## 5. 边界与错误处理

- 企业无楼层：floors 为空，全部分区归「未分配楼层」，与现状一致。
- 楼层被删除：工作台现有删除逻辑已处理分区/对象约束（默认楼层提升或禁止删除），树随刷新数据重新分组，无需额外处理。
- 分区移动楼层：后端同步该分区下对象 `floor_id`，前端无需补偿逻辑。
- 并发/保存冲突：沿用现有乐观更新与错误提示，不做额外处理。

## 6. 测试

- 后端（pytest）：
  - `/hierarchy` 不传 `floor_id` 返回多楼层分区且楼层/分区排序正确；
  - 传 `floor_id` 仍单楼层过滤（回归）；
  - 企业无楼层、分区 `floor_id` 为 null 的场景。
- 前端（vitest）：
  - 树分组单测：楼层顺序、未分配兜底、默认楼层优先展开；
  - `zoneSubmit` 增加 `floor_id` 透传断言。
- E2E（Playwright，风险管控页 mock）：
  - 多楼层 mock 下断言树顶层出现楼层节点；
  - 跨楼层分区均可见；
  - 从楼层节点「添加分区」提交的 payload 含目标 `floor_id`。

## 7. 涉及文件

- backend/app/routers/risk_management.py（`/hierarchy` 多楼层返回）
- frontend/src/components/enterprise/RiskHierarchyTree.tsx（楼层分组节点）
- frontend/src/components/enterprise/RiskZoneForm.tsx（楼层 Select + 底图联动）
- frontend/src/pages/Enterprise/RiskManagementTab.tsx（并行加载 floors、add-zone 分支、详情面板）
- frontend/src/utils/zoneSubmit.ts 及测试（`floor_id` 透传）
- 新增：树分组单测、E2E 用例
