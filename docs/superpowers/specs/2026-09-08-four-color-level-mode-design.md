# 四色分布图分区显式等级设计（2026-09-08）

## 背景与目标

用户反馈：绘制四色分布图时，分区颜色与区域颜色无法赋值和调整，操作很不方便。

现状诊断（代码证据）：

1. **颜色只挂在分区级，区域无颜色概念**：`floor_plan_polygon` 仅有 `color_source: auto/manual` 与 `color`，其下 `polygons[]` 区域只有顶点。画布渲染时一个分区的所有区域共用同一颜色（`WorkbenchCanvas.tsx` `fill={zoneColor(z)}`），用户无法对单个区域赋值颜色。
2. **颜色控件可达性差**：画布点中区域只设置 `selectedRegionId`，不联动选中所属分区；颜色控件只在左侧分区列表选中分区时出现于属性面板底部（`WorkbenchPropertiesPanel.tsx`）。画完一块想上色找不到入口，且面板上半截显示区域、下半截可能仍是上一个分区的属性，容易改错对象。
3. **手动模式是"任意颜色"而非"四色"**：manual 时是自由取色器（`<input type="color">`），默认 `#ff4d4f` 与当前等级无关；auto 颜色依赖分区下绑定的风险对象等级，未绑对象的分区永远是灰色，用户无法表达"这块是较大风险"。
4. **AI 导入链路语义不一致**：`commit_four_color_import` 把识别出的等级转存为 `color_source: manual + color: LEVEL_COLORS[level]`，等级本身未落库，导入分区 `max_risk_level` 仍为 None（代码注释自证），统计/公示/报告中该分区是"未评估 + 手动染色"。

目标：把"手动颜色"升级为"显式等级"，颜色一律由等级派生；统一手工链路与 AI 导入链路的等级语义；修复颜色控件的可达性与交互。

## 范围

### 做

- 数据结构：`floor_plan_polygon` 用 `level_mode: "auto" | "manual"` + `risk_level` 显式等级取代 `color_source` + 任意 `color`；颜色为派生值，不允许存任意色。
- 迁移：存量 `color_source=manual` 数据读取时按颜色反查四色等级（AI 导入色均落在 `LEVEL_COLORS` 四色内），运行时归一化，无需 SQL 迁移。
- 计算口径：`effective_color`、分区 `max_risk_level` 返回"显式等级优先，否则对象推导等级"；手动指定等级对现有/固有两种模式同时生效。
- AI 导入：落库写 `level_mode: manual + risk_level: 识别等级`，导入后分区等级立即正确显示。
- 交互：画布选中区域自动选中所属分区；绑定待绑定区域后自动选中目标分区；属性面板颜色设置上移并改为"跟随自动 / 指定等级"四色块选择；图例文案同步。
- 验证：后端 pytest、前端 vitest + tsc、浏览器冒烟（手绘指定等级→保存→公示/报告一致；AI 导入→等级正确）。

### 不做（本期）

- 区域（`polygons[]` 单个多边形）独立等级/颜色（方案三，结构性重构，后续单独评估）。
- 保留"手动任意色"入口（方案二决策：颜色只从四色派生）。
- 分区级自定义色与显式等级并存的混合模式。
- 移动端改造（本期桌面四色工作台范围内；移动端如有对应功能另行评估）。

## 数据模型

### 新结构（版本仍为 2）

```json
{
  "version": 2,
  "level_mode": "auto" | "manual",
  "risk_level": "重大" | "较大" | "一般" | "低" | null,
  "polygons": [ { "id": "...", "label": "...", "points": [...] } ]
}
```

- `level_mode=auto`：`risk_level` 必须为 `null`。颜色按当前查看模式（现有/固有）下分区内风险对象的最大等级推导；无对象时呈现"未评估"灰。
- `level_mode=manual`：`risk_level` 必须为四大等级之一（不允许"未评估"）。颜色 = `LEVEL_COLORS[risk_level]`，现有/固有两种模式显示一致，不随对象变化。
- `color` 字段不再写入；读取时对旧数据做兼容归一化，见下。

### 兼容与归一化（无 SQL 迁移）

扩展 `risk_mapping_service.normalize_polygon`（含 v2 分支）：

- 旧 `color_source=manual` + `color`：按 `LEVEL_COLORS` 逆映射（颜色小写规范化比较）回推等级 → `level_mode=manual + risk_level=<等级>`；无法识别的任意色退化为 `level_mode=auto`（该分区视觉回到对象推导/未评估，可人工重设）。
- 旧 `color_source=auto` 或无字段：归一化为 `level_mode=auto + risk_level=null`。
- 输出统一去掉 `color_source`/`color` 键。

后端读取分区多数路径（工作台/总览 `_to_workbench_zone`、层级 `hierarchy`）已走 `normalize_polygon` + `RiskZoneFloorPlanPolygon.model_validate(normalized)`；**例外：风险公示 `/risk-publicity` 的 `zones_data` 直接透传 `z.floor_plan_polygon`（risk_management.py 约 1208 行），实施时须一并改为先 normalize 再返回**，保证所有响应结构一致。`RiskZone` 表不加列。

## 后端设计

### 1. Schema（`backend/app/schemas/risk_management.py`）

- `RiskZoneFloorPlanPolygon`：`color_source`/`color` 替换为 `level_mode: Literal["auto", "manual"]` 与 `risk_level: RiskLevel | None`；校验规则改为：manual 必须提供 `risk_level` 且为四色等级之一，auto 时 `risk_level` 必须为空。
- `/risk-publicity` `zones_data` 的 `floor_plan_polygon` 接入 `normalize_polygon`（当前直接透传），保持各响应结构一致。
- 手写 validator 保留现有风格；非法值返回明确中文错误。

### 2. 计算口径（`backend/app/services/risk_mapping_service.py`）

- `LEVEL_COLORS` 保留为颜色唯一来源；新增 `LEVEL_COLORS_REVERSE`（小写键）用于迁移反查。
- `effective_color(polygon, computed_level)`：
  - manual → `LEVEL_COLORS[risk_level]`（`risk_level` 缺失视为 auto 兜底）；
  - auto → `LEVEL_COLORS[computed_level or "未评估"]`。
- `risk_management.py` 的 `_zone_dual_levels`：分区响应的 `max_risk_level`/`inherent_max_level` 在 manual 时均返回显式 `risk_level`（并同时使用于 `effective_color`/`inherent_effective_color`）；auto 时维持现有对象推导逻辑。
- `validate_polygon_v2` 同步新字段校验（manual 缺等级、auto 带等级均为错误）。

### 3. AI 导入落库（`backend/app/routers/risk_management.py` commit_four_color_import）

- 两处 `floor_plan_polygon` 构造（预校验与正式创建）改为：

```python
{
  "version": 2,
  "level_mode": "manual",
  "risk_level": zone.risk_level,
  "polygons": [...],
}
```

- 导入响应不再特判"暂无风险对象"：`effective_color`/`inherent_effective_color` 由 manual 等级直接给出，`max_risk_level` 返回识别等级。

## 前端设计

### 1. 类型（`frontend/src/types/riskManagement.ts`）

- `ColorSource` 替换为 `LevelMode = "auto" | "manual"`；
- `RiskZoneFloorPlanPolygon` 字段改为 `level_mode` + `risk_level`（`RiskLevel | null`），移除 `color`；
- `WorkbenchZone` 响应字段 `max_risk_level`/`effective_color` 等含义不变，直接反映后端归一化结果。

### 2. 选中联动（可达性修复）

- `WorkbenchCanvas.tsx`：点中 `zone:<zoneId>:<polygonId>` 区域时，`setState` 同时设置 `selectedZoneId: z.id`；
- `WorkbenchPropertiesPanel.tsx` `bindSelectedPending`：绑定成功后 `setState({ selectedZoneId: target.id, selectedRegionId: null })`，使属性面板立即切到目标分区的颜色设置；
- 点中待绑定区域（pending）仍清空 `selectedZoneId`（保持现状，属性面板只显示绑定/变换操作）。

### 3. 颜色设置区（`WorkbenchPropertiesPanel.tsx`）

- 位置：从分区属性块底部移到分区名称下方（"颜色"小节）。
- 控件：
  - 顶部显示当前实际色块与等级文案；
  - 单选：`跟随自动` / `手动指定`；
  - 手动指定时展示四个等级色块按钮（重大 #ff4d4f / 较大 #fa8c16 / 一般 #fadb14 / 低 #52c41a，含等级名），点击即设置 `level_mode=manual + risk_level=<等级>`；
  - 跟随自动时无额外控件，等级由后端对象推导；无对象时为"未评估"灰。
- 移除 `<input type="color">` 与默认 `#ff4d4f` 逻辑。
- 提示文案：手动指定后现有/固有模式均显示该颜色，不随对象变化；未绑定风险对象的分区也可直接指定等级。

### 4. 图例与展示

- `WorkbenchLegend.tsx` 文案由"区域颜色 = 该区域现有/固有最大风险等级"改为体现来源：手动指定等级或风险对象最大等级。
- 左侧分区卡片（`WorkbenchZonePanel.tsx`）无需改逻辑：后端返回的 `max_risk_level`/`effective_color` 已含显式等级，卡片等级与背景色自动正确。

## 错误处理与兼容

- 旧数据反查失败（非四色的自定义 manual 色）退化为 auto：不报错、不阻断加载，视觉回到推导色，提示性说明写入迁移注释与实现计划的回归用例。
- 非法 body（manual 无等级、auto 带等级、等级不在四色集合）由 schema/`validate_polygon_v2` 拒绝，沿用现有 422 中文错误风格。
- 读取归一化必须幂等：重复 normalize 同一对象结果不变；前端拿到的一律是新结构。
- 已存在的后端消费方（风险概览、报告四色插图、法规/上下文构建等）读取响应字段 `max_risk_level`/`effective_color`，颜色口径随 `_zone_dual_levels` 自动统一，无需逐点改动；唯一例外是 `/risk-publicity` 的 `floor_plan_polygon` 透传点（见后端设计），前端公示页只消费 `polygons` 与 `effective_color`，接入 normalize 后视觉行为不变。

## 测试策略

### 后端单测（新增/更新）

- `validate_polygon_v2`：manual 缺等级、auto 带等级、四色外等级均报错；合法新旧结构通过。
- `normalize_polygon`：旧 manual+四色 → manual+等级；旧 manual+任意色 → auto；旧 auto → auto；幂等性。
- `effective_color`：manual 取 `LEVEL_COLORS[risk_level]`；auto 取推导等级色；`risk_level` 缺失兜底 auto。
- 分区响应：manual 时 `max_risk_level`/`inherent_max_level`/两个 effective 色均为显式等级与其色。
- AI 导入 commit：落库含 `level_mode=manual + risk_level=识别等级`；响应 `max_risk_level` 返回识别等级（原"导入分区未评估"行为用例更新）。
- batch save：前端提交新结构可保存；旧结构保存前归一化。

### 前端验证

- vitest：类型与既有 workbench service 测试回归；如组件测试可低成本覆盖，补属性面板等级选择的状态更新用例。
- tsc -b 0 error；eslint 改动文件 0 error。

### 浏览器冒烟

- 手绘：画区域 → 绑定分区 → 自动带出颜色设置 → 手动指定"较大"→ 保存 → 刷新后分区卡片/画布为橙色且等级为"较大"；现有/固有模式切换颜色不变。
- AI 导入：导入四色图 → 分区等级正确显示、画布颜色与识别图一致 → 保存后刷新不变。
- 公示/概览/报告插图：分区等级与颜色口径一致。

## 涉及文件（供实现计划细化，非最终清单）

- 后端：`backend/app/schemas/risk_management.py`、`backend/app/services/risk_mapping_service.py`、`backend/app/routers/risk_management.py`、对应测试文件。
- 前端：`frontend/src/types/riskManagement.ts`、`frontend/src/components/enterprise/riskMapping/WorkbenchCanvas.tsx`、`WorkbenchPropertiesPanel.tsx`、`WorkbenchLegend.tsx`、类型/服务测试。

## 决策记录

- 2026-09-08：用户选定方案二（显式等级取代手动任意色），方案一（交互修复）与方案二合并实施；方案三（区域级独立上色）明确不做。
- 手动指定等级对现有/固有两种模式同时生效（显式覆盖优先于模式推导）。
- 等级覆盖存储于 `floor_plan_polygon` JSON 内（与现状字段同层），不新增数据库列。
- 允许手动指定的等级为四色四大等级，不含"未评估"。
