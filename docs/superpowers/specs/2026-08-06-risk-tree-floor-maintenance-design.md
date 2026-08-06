<!--
  文档元信息
  创建日期: 2026-08-06
  作者: Codex
  版本: 1.0
  状态: 待审查
  依赖: 2026-08-06-risk-tree-floor-grouping-design.md（分区树楼层分组，已合并）
-->

# 风险分级管控树楼层维护与空楼层显示 设计方案

## 1. 概述

### 1.1 背景

分区树楼层分组功能已上线（设计文档 `2026-08-06-risk-tree-floor-grouping-design.md`），但存在两个体验缺口：

- 树只显示**有分区**的楼层（`groupZonesByFloor` 过滤掉空楼层），导致在四色分布图工作台新增楼层后，风险分级管控的树状图看不到变化。
- 风险分级管控页的树区域没有任何楼层维护入口（添加/重命名/设为默认/删除只存在于工作台的 `EnterpriseFloorManager`）。

### 1.2 目标

- 树顶层显示**全部楼层**（含空楼层）：空楼层标注"0 分区 · 0 风险点"，保留「添加分区」操作。
- 风险分级管控页工具栏新增「楼层管理」抽屉：添加楼层、重命名、设为默认、删除。
- 工作台与风险页的楼层数据**双向联动**刷新，不依赖页面重挂载。

### 1.3 非目标

- 不在楼层管理抽屉提供平面图上传（保留工作台入口，抽屉内给一句提示）。
- 不改动工作台楼层管理的既有 UI 与逻辑（仅给其刷新逻辑补一行跨键失效）。
- 不做移动端适配（移动端不消费该树）。

### 1.4 已确认决策

| 决策项 | 结论 |
|---|---|
| 空楼层显示 | 全部楼层均显示，空楼层标注"0 分区 · 0 风险点" |
| 未分配兜底 | 仍仅在有未分配分区时出现，置于楼层列表之后 |
| 维护入口 | 工具栏「楼层管理」按钮 + 独立组件 `FloorManagementDrawer`（新建） |
| 维护能力 | 添加 / 重命名 / 设为默认 / 删除（全部复用后端既有规则） |
| 平面图上传 | 不包含，保留工作台入口 |
| 数据联动 | 抽屉操作后 invalidate 本页楼层键 + 重新拉取分区树；工作台 `EnterpriseFloorManager.refresh` 补 invalidate 风险页楼层键（双向） |
| 空态规则 | 有楼层即渲染树；无楼层且无分区才显示"暂无数据"空态 |

## 2. 现状

- `frontend/src/utils/riskTreeGrouping.ts`：`groups.filter((g) => g.zones.length > 0)` 隐藏空楼层。
- `frontend/src/components/enterprise/RiskHierarchyTree.tsx`：空态条件为 `data.length === 0`，企业有楼层但无分区时直接显示空态。
- `frontend/src/pages/Enterprise/RiskManagementTab.tsx`：工具栏只有 添加分区/智能导引/可视化总览/工作台/评估方法，无楼层维护入口；floors 查询键 `["enterprise-floors", enterpriseId]`。
- `frontend/src/components/enterprise/EnterpriseFloorManager.tsx`（工作台）：查询键 `["risk-floors", enterpriseId]`，`refresh()` 只 invalidate `risk-floors` 与 `risk-workbench`。
- 后端 `GET/POST/PUT/DELETE /floors` 与规则已完备：名称重复 409、有分区/风险对象不可删、默认楼层唯一、至少保留一个默认楼层（backend/app/routers/risk_management.py:66-145）。

## 3. 设计

### 3.1 `groupZonesByFloor` 调整（显示全部楼层）

- 返回全部楼层分组（含空楼层）：空楼层 `zoneCount=0`，`riskPointCount` 取 `floor.risk_point_count ?? 0`。
- 「未分配楼层」兜底逻辑不变（仅在有未分配分区时追加到末尾）。
- 调用方 `RiskHierarchyTree` 的 `totalNodes`/`multiFloor`/`defaultExpandedKeys` 逻辑天然适配，无需改动。

### 3.2 空态调整（`RiskHierarchyTree`）

- 空态条件由 `data.length === 0` 改为 `(floors?.length ?? 0) === 0 && data.length === 0`。
- 企业有楼层但无分区时，树渲染全部空楼层节点，可展开并「添加分区」。

### 3.3 `FloorManagementDrawer`（新建 `frontend/src/components/enterprise/FloorManagementDrawer.tsx`）

- Props：`enterpriseId: string; open: boolean; onClose: () => void; onChanged?: () => void`。
- 数据：`useQuery(["enterprise-floors", enterpriseId], listEnterpriseFloors)`，打开时自动重取。
- 列表项：楼层名称 + 默认徽标（Tag）+ "X 分区 · Y 风险点" + 操作按钮（设为默认 / 重命名 / 删除）。
- 添加/重命名：Modal + Input（名称必填；后端 409"楼层名称已存在"直接展示）。
- 设为默认：`updateEnterpriseFloor(eid, id, { is_default: true })`（后端处理唯一默认与保底）。
- 删除：Popconfirm；后端 409（有分区/风险对象、必须保留默认）文案直接展示。
- 成功回调：`invalidateQueries(["enterprise-floors", eid])` + `invalidateQueries(["risk-floors", eid])` + `onChanged()`（由 RiskManagementTab 传入 `refetch` 分区树）。
- 不做平面图上传；抽屉底部提示"平面图上传与分区绘制请在四色分布图工作台进行"。

### 3.4 `RiskManagementTab` 集成

- 工具栏新增「楼层管理」按钮（`ApartmentOutlined`），控制抽屉开关。
- 渲染 `FloorManagementDrawer`，`onChanged={refetch}`（分区树刷新）。

### 3.5 工作台联动（`EnterpriseFloorManager` 一行）

- `refresh()` 增加 `queryClient.invalidateQueries({ queryKey: ["enterprise-floors", enterpriseId] })`，与风险页楼层键对称联动。

## 4. 边界与错误处理

- 后端既有规则逐条映射到 UI：409 名称重复、409 有分区/风险对象不可删、409 必须保留默认楼层，均展示后端 `detail` 文案。
- 删除默认楼层：后端自动提升替代楼层或返回 409，UI 展示结果/文案。
- 空楼层删除：允许（无分区/风险点）。
- 抽屉操作后数据一致性：invalidate 两个查询键，`useQuery` 自动重取。

## 5. 测试

- 单测（vitest）：`riskTreeGrouping.test.ts` 将"隐藏空楼层"用例反转为"包含空楼层且计数为 0"；「未分配楼层」兜底用例保持不变。
- E2E（Playwright，`risk-hierarchy-tree.spec.ts`）新增 2 用例：
  1. 树显示空楼层：mock 2 个楼层、分区仅属于 floor-1 → 断言"二层"节点与"0 分区"文案可见。
  2. 抽屉添加楼层：mock `POST /floors`（新楼层）与后续 `GET /floors` 返回 3 层 → 断言树中出现新楼层节点。
- 回归：现有 risk-hierarchy-tree 3 用例 + risk-mapping-workbench 12 用例全部保持通过；tsc/vitest/后端 pytest 全量通过。

## 6. 涉及文件

- `frontend/src/utils/riskTreeGrouping.ts` 及 `riskTreeGrouping.test.ts`（空楼层显示）
- `frontend/src/components/enterprise/RiskHierarchyTree.tsx`（空态条件）
- `frontend/src/components/enterprise/FloorManagementDrawer.tsx`（新建）
- `frontend/src/pages/Enterprise/RiskManagementTab.tsx`（工具栏 + 抽屉）
- `frontend/src/components/enterprise/EnterpriseFloorManager.tsx`（refresh 补一行 invalidate）
- `frontend/e2e/risk-hierarchy-tree.spec.ts`（新增 2 用例）
