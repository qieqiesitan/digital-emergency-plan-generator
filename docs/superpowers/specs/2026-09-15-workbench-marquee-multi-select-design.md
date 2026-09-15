# 四色分布图工作台：同分区框选多区域批量操作设计（2026-09-15）

## 背景与目标

四色分布图工作台目前只能**单选**一个区域（多边形）并做自由变换：属性面板的"自由变换"（缩放/旋转/翻转）只作用于当前选中的单个区域（`WorkbenchPropertiesPanel` 的 `selectedPending` / `selectedZonePolygon`），画布上的 Konva `Transformer` 也只挂一个节点（`WorkbenchCanvas.tsx` 约 1010 行 `nodes={[regionNodeRefs.current.get(selectedRegionId)]}`）。

用户在绘制/导入四色分布图后，经常需要把**同一个分区内**的多块区域一起微调（整体挪动、整体旋转对齐底图、批量删除误识别的块），逐个操作效率很低。

目标：在 `select` 工具下支持**空白拖拽框选同一分区内的多个区域**，选中后可整体旋转、缩放、移动、删除；全程不改变后端接口与 `floor_plan_polygon` 数据结构。

## 范围

### 做

- 框选：`select` 工具下空白处按下拖动出选框，松开后选中**当前分区**内命中的区域。
- 多选集合：选择状态由单值升级为集合，支持替换选择、Shift 追加、单击空白清空。
- 整体变换：多选后整体旋转、整体缩放（绕整体中心）、整体平移（拖动任一选中区域带动全部）。
- 批量删除：键盘 Delete/Backspace 与属性面板按钮，一次删除所有选中区域。
- 多选态属性面板："已选中 N 个区域" + 批量旋转/缩放/翻转/删除。
- 撤销/重做：一次批量操作只占一步撤销栈。

### 不做（本期）

- 跨分区框选（多选限定在当前分区内；未选分区时框选不生效并给出提示）。
- 风险点与文字标注的框选（本期只针对区域多边形）。
- 多选后"移动到其它分区"（跨分区语义另行评估）。
- 移动端、跨楼层框选。

## 现状与约束（代码事实）

- 选择状态：`frontend/src/store/riskMappingWorkbenchStore.ts` 第 23 行 `selectedRegionId: string | null`，单选；删除相关 action 只有单条 `deleteZonePolygon` / `deletePendingRegion`，`deleteSelected` 也只处理一个区域（约 187-201 行）。
- 区域节点 id 约定：待绑定区域 `pending:<id>`，已绑定区域 `zone:<zoneId>:<polygonId>`；节点引用存于 `regionNodeRefs`（`WorkbenchCanvas.tsx` 134 行）。
- 变换回写：`handleRegionTransformEnd`（约 407 行）已按前缀把变换结果写回 store；`transformPolygonPoints(points, { scale, rotationDeg, flipX, flipY, center })`（`utils/riskMappingGeometry.ts` 41 行）**已支持 `center` 参数**，可直接实现"绕整体中心"的批量变换。
- 顶点范围：所有顶点经 `clampPoint` 收敛到 0–100，与后端 `validate_polygon_v2` 的坐标校验一致。
- 平移通道：空格 + 左键拖 / 右键拖（`handleMouseDown` 约 440-447 行），与框选不冲突。
- 撤销/重做：store 的 `commit()` 压栈、`markSaved()` 清栈，保存后 `dirty=false`。
- 引用点清单（升级为多选需同步适配）：`riskMappingWorkbenchStore.ts`、`WorkbenchCanvas.tsx`、`WorkbenchPropertiesPanel.tsx`、`WorkbenchZonePanel.tsx`、`WorkbenchToolbar.tsx`、`WorkbenchRiskPointLayer.tsx`，以及 `riskMappingWorkbenchStore.test.ts`。

## 状态设计

### 字段

- 新增 `selectedRegionIds: string[]` 作为**唯一权威**选择集合（元素为 `pending:` / `zone:` 前缀 id）。
- 移除 `selectedRegionId` 字段；调用处统一用 `selectedRegionIds[0] ?? null` 表达"主选中"（属性面板单选分支、`data-transform-active` 等展示逻辑）。
- 撤销/重做适配：`snapshotOf` 只含业务数据（floors/zones/riskPoints/texts/pendingRegions/deleted*），不含选择字段，无需改动；`undo`/`redo` 的 `restored` 对象保留当前选择态，需把其中 `selectedRegionId: state.selectedRegionId` 替换为 `selectedRegionIds: state.selectedRegionIds`。
- 选择互斥规则不变：选中区域时清空 `selectedRiskPointId` / `selectedTextId`，反之亦然。

### 新增 store action

```ts
setSelectedRegions(ids: string[], options?: { append?: boolean }): void
toggleRegionSelection(id: string): void
deleteSelectedRegions(): void
```

- `setSelectedRegions`：`append` 时并入去重，否则整体替换；同步清理风险点/文字选择。
- `deleteSelectedRegions`：对集合按前缀分组（`pending:` 与 `zone:`），从 `pendingRegions` 与各分区 `floor_plan_polygon.polygons` 批量移除；**先 `commit()` 一次**、再一次性 `setSnapshot()` 写回，保证撤销栈只有一步。
- 既有 `deleteZonePolygon` / `deletePendingRegion` / `deleteSelected` 保留，但 `deleteSelected` 优先走多选分支（见"删除与撤销"）。

## 交互设计（框选）

- 触发条件：`tool === "select"`、未按空格、左键、且按下位置不命中任何区域节点/风险点/文字。
- 拖动阈值：位移 ≥ 3px 视为框选；< 3px 视为"单击空白"，清空选择。
- 选框渲染：Konva `Rect`，蓝色细虚线边框 + 半透明蓝色填充，`listening={false}`。
- 命中规则：只对**当前分区**（`selectedZoneId`）下的 `floor_plan_polygon.polygons` 判定"多边形与选框矩形相交"（完全包含或部分相交均算命中）。
- 追加/替换：按住 Shift 时并入当前选择，否则替换。
- 未选分区：不进入框选态，`message.info("请先选择分区后再框选")`，避免误选到其它分区。
- 其它工具（rect/circle/polygon/pen/freehand/risk-point/text）与平移操作不触发框选。
- 框选过程中按下空格或右键：终止框选并转为平移。
- Esc：清空选择（保持现有行为）。

## 变换设计

- Transformer 多节点：

```tsx
const nodes = selectedRegionIds.map(id => regionNodeRefs.current.get(id)).filter(Boolean);
{tool === "select" && nodes.length > 0 && (
  <Transformer ref={transformerRef} nodes={nodes} rotateEnabled flipEnabled={false} ... />
)}
```

- 旋转/缩放：由 Konva 多节点 Transformer 提供，默认绕整体中心；每个多边形保持相对位置。
- 整体平移：`dragstart` 记录全部选中节点的起始点位与拖动起点；`dragmove` 把位移同步到其它选中节点（仅视觉）；`dragend` 用位移量一次性写回。
- 拖动未选中区域：先把它设为唯一选择，再按现有逻辑拖动。
- 一次性写回：变换/平移结束后遍历所有选中节点，用节点变换矩阵得到新顶点，`commit()` 一次 + `setSnapshot()` 一次，只更新所属分区的 `polygons`（本期多选同分区，因此只涉及一个 zone）。
- 顶点统一经 `clampPoint` 收敛在 0–100。

## 属性面板（多选态）

- `selectedRegionIds.length > 1` 时切换为多选态：
  - 标题："已选中 N 个区域"；
  - 批量旋转角度输入（度）→ 绕整体中心旋转；
  - 批量缩放输入（%）→ 绕整体中心缩放；
  - 水平/垂直翻转；
  - "删除选中区域"按钮。
  - 隐藏单区域专属内容（所属分区、移动到其它分区、顶点数）。
- 单选态完全保持现状。
- 批量变换实现复用 `transformPolygonPoints(points, { scale, rotationDeg, flipX, flipY, center: 整体质心 })`。

## 删除与撤销

- Delete/Backspace：`deleteSelected` 扩展为——若 `selectedRegionIds.length > 0` 走 `deleteSelectedRegions()`；否则维持原有风险点/文字删除逻辑。
- 批量删除与批量变换各自只调用一次 `commit()`，撤销一次即整体回退。
- 删除不需要二次确认（可用撤销恢复）。

## 错误处理与边界

- `regionNodeRefs` 缺少某个选中 id（节点未渲染）时过滤掉，不抛错。
- 框选命中 0 个区域：清空选择（非追加时），不报错。
- 追加选择时重复命中：集合去重。
- 平移/框选互斥：平移状态下 `handleMouseMove/handleMouseUp` 提前返回，不启动框选。
- 顶点越界：沿用 `clampPoint`（0–100），与后端校验一致，不会产生保存失败。
- 性能：单分区区域数量级（常见 < 50，极限 < 200）下逐多边形做矩形相交判定可接受，无需引入空间索引。

## 测试策略

### 纯函数单测（新增 `frontend/src/utils/riskMappingMarquee.ts` + `.test.ts`）

- `rectFromPoints(a, b)`：两点构造归一化矩形；位移小于阈值时返回 `null`。
- `polygonIntersectsRect(points, rect)`：完全包含 / 部分相交 / 完全不相交 / 仅边界接触 四类用例。
- `collectRegionsInRect(polygons, rect)`：返回命中 polygon id 列表。
- `transformRegionsAroundCenter(polygons, { scale, rotationDeg, flipX, flipY }, center)`：返回新顶点集合，验证相对位置保持、中心不变、顶点仍 clamp 在 0–100。

### store 单测（`riskMappingWorkbenchStore.test.ts`）

- `setSelectedRegions` 替换与追加（去重、清理风险点/文字选择）。
- `deleteSelectedRegions` 混合删除（`pending:` + `zone:`）、只压一次撤销栈、撤销可整体恢复。

### 浏览器冒烟（人工/Playwright）

1. 选中分区 → 空白拖拽框选 3 块区域 → 高亮与整体外框出现。
2. 拖外框旋转 15° → 保存 → 退出重进，旋转结果保持。
3. 拖动任一选中区域 → 全部一起平移 → 保存 → 重进保持。
4. 整体缩放 → 保存 → 重进保持。
5. 批量删除 → 保存；撤销一次回到删除前。
6. Shift 追加框选 / 单击空白清空 / 未选分区框选提示 / 绘制工具下不触发框选。

## 涉及文件

- `frontend/src/store/riskMappingWorkbenchStore.ts`（+ `riskMappingWorkbenchStore.test.ts`）
- `frontend/src/components/enterprise/riskMapping/WorkbenchCanvas.tsx`
- `frontend/src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx`
- `frontend/src/components/enterprise/riskMapping/WorkbenchZonePanel.tsx`（选择字段适配）
- `frontend/src/components/enterprise/riskMapping/WorkbenchToolbar.tsx`（禁用判断适配）
- `frontend/src/components/enterprise/riskMapping/WorkbenchRiskPointLayer.tsx`（清空选择适配）
- 新增 `frontend/src/utils/riskMappingMarquee.ts`（+ `.test.ts`）
- 后端与数据库：无改动（区域本就是同一分区 `floor_plan_polygon.polygons` 数组）

## 决策记录

- 2026-09-15：用户选定方案一（空白拖拽框选 + 多选变换框），范围为**同一分区内**。
- 保留整体缩放（拖外框角缩放），与现有单区域自由变换保持一致。
- 风险点、文字标注不参与框选；跨分区框选与"多选移动到其它分区"本期不做。
- 选择状态以 `selectedRegionIds` 为唯一权威，`selectedRegionId` 由 `selectedRegionIds[0] ?? null` 派生表达。
