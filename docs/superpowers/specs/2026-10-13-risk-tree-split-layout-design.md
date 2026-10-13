# 风险树编辑页左右分屏 + 四色图联动 — 设计规格

日期：2026-10-13
状态：已实现并通过验证（用户确认方案："可以，开干"）

## 1. 背景与目标

风险树编辑页（`/enterprises/:id/risk-management`，即「风险分级管控 › 风险树编辑」）原布局为
左侧风险树（flex:1）+ 右侧 300px 纯文字「节点详情」。用户要求：

- 左右分屏：左侧保持现有风险树编辑功能，可以稍微紧凑一些；
- 右侧展示「节点详情（小）」与「四色图展示」，四色图与左侧联动，更直观。

## 2. 布局

```
┌───────────────────────────────────┬──────────────────────┐
│ 工具栏（单行小按钮；导航收进「更多▾」） │ 📌 节点详情（紧凑小卡）  │
│ ┌───────────────────────────────┐ │ ┌──────────────────┐ │
│ │ 风险树（功能不变，行高/内边距略紧）  │ │ 四色图（底图+分区+风险点）│ │
│ │  · 楼层分组 · 行内增删改          │ │  · 选中节点高亮加粗    │ │
│ └───────────────────────────────┘ │ └──────────────────┘ │
└───────────────────────────────────┴──────────────────────┘
```

- 左栏：`minWidth 380`，flex:1；工具栏固定、树区域独立滚动；按钮 `size=small`，
  旧导航按钮（可视化总览/工作台/管控清单/…）收进「更多」Dropdown（仅非 embedded 渲染）。
- 右栏：固定宽 420px，竖排两卡——节点详情（`maxHeight 38%` 可滚动）+ 四色图（flex:1）。
- 四色图复用 `RiskDistributionStage`（底图 + 分区色块 effective_color + 风险点 + 文本，
  与「可视化总览」同款只读渲染），只读不做拖拽缩放。

## 3. 联动（双向）

- 树选节点 → 地图高亮该分区：分区节点=自身；对象/单元/事件/措施=其所属分区（`hierarchyMap`）；
  楼层节点=切换地图楼层、不高亮分区。
- 点地图分区 → 树反选：`RiskHierarchyTree` 新增受控 `selectedKey`，并自动展开选中节点的祖先；
  详情卡同步刷新。
- 多楼层（>1）时地图头部出现楼层下拉；地图楼层默认跟随所选节点，可手动切换。
- 空态：无楼层 → "暂无楼层，先上传四色图/底图"+「去楼层管理」；楼层无底图且无分区 → 同类空态。

## 4. 关键实现点

- `frontend/src/pages/Enterprise/RiskManagementTab.tsx`：
  新增 `mapFloorId`/`treeSelectedKey`/`highlightZoneId` 派生、楼层跟随 effect（带
  `react-hooks/set-state-in-effect` 定向豁免+说明，仓库既有约定）、`handleMapZoneClick`；
  详情卡新增「楼层」「分区等级」行。
- `frontend/src/components/enterprise/RiskHierarchyTree.tsx`：
  新增受控 `selectedKey`；展开态改为"派生默认值 + 用户接管"：
  `autoExpandedKeys`（多楼层=默认楼层；单楼层节点<100=全展开）由 `useMemo` 派生，
  `userExpandedKeys` 为空时始终使用派生值，并恒态并入选中节点的祖先链。
- `frontend/src/components/enterprise/RiskTreeFourColorMap.tsx`（新增）：
  地图卡片；`data-floor-id`/`data-highlight-zone` 供 e2e 断言联动状态。

### 关键坑（已修复）

1. floors 查询晚于 hierarchy 到达：树在 hierarchy 就绪即挂载，若用 `useState` 初始化
   展开键，`floors=[]` 时算出的键（`floor-unassigned`）会过期失效 → 楼层永远折叠。
   改为派生展开态后与数据到达顺序解耦。
2. e2e 规格历史陈旧（与本次改动无关但阻塞验证，已顺手修复）：
   `risk-hierarchy-tree.spec.ts` / `smart-guide-import.spec.ts` 仍走"企业驾驶舱 tab"入口
   （现已改模块导航）→ 改为直达 `/risk-management` 路由；补 `cockpit-summary` mock；
   智能导引提示文案与"重名分区并入现有"语义更新断言。

## 5. 验证

- `npx tsc -b` ✓；`npx vitest run` 370 例 ✓；`eslint-ratchet` 未新增债务 ✓；源码卫生 ✓。
- Playwright（本地，`ALLOW_PWA_SKIP=1`，Node24 需跳过 PWA）：
  `risk-hierarchy-tree.spec.ts` 6/6 ✓（含新增联动用例：树选分区→高亮；点楼层→切楼层；
  点地图→树反选并自动展开），`smart-guide-import.spec.ts` 1/1 ✓；
  `enterprise-cockpit`/`enterprise-switch`/`four-color-import` 等其余规格 22 例通过。
  预存在失败（非本次引入）：`mobile-routing`（写死 5173 端口）、`risk-mapping-workbench` 2 例（旧 URL 断言）。
- 真实环境（docker 后端 + 15173 前端，qa 账号 + 永昇四色图演示数据）：
  树选「办公室」→ 地图该分区加粗高亮、详情显示"楼层：默认总图 / 分区等级：低"；
  点地图中央大区 → 树自动选中「分区13」并滚动展开、详情同步。
  截图：`output/tmp/risktree-layout/s1_layout.png`、`s2_tree_to_map.png`、`s3_map_to_tree.png`。
