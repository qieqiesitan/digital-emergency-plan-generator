# 企业详情页重构为「企业驾驶舱」设计规格

> 版本：1.0 | 创建日期：2026-08-16 | 状态：待用户审查
> 关联：PRD-02-企业管理模块.md、frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx、frontend/src/routes/index.tsx

## 1. 背景与目标

当前企业详情页（`/enterprises/:id`）使用 Ant Design Tabs 承载全部功能，9 个选项卡分为「数据录入」「报告生成」两组，另有 14 个子页面散落在各处，入口深、层级不清晰。

本次重构目标：

1. 将详情页改造为**企业驾驶舱**——深空蓝科技感、指挥大屏式构图的信息总览页；
2. 所有企业功能按业务域**重新归类为 10 个独立模块**，驾驶舱底部以图标宫格平铺；
3. **仅驾驶舱采用深色科技感**，模块页保持现有浅色系统风格，避免全局风格漂移；
4. 复杂模块使用**左侧竖向分组导航**（方案 B）收纳子功能，简单模块不加导航。

## 2. 范围界定

### 2.1 本次范围

- 新建企业驾驶舱页面，替换 `/enterprises/:id` 的 Tabs 结构；
- 新增模块页包装（复用现有 Tab 组件/子页面，浅色风格，带「返回驾驶舱」）；
- 复杂模块（风险分级管控、隐患排查治理）增加浅色左竖分组导航；
- 新增驾驶舱汇总数据端点（一个后端接口）；
- 路由调整与旧 `?tab=` 链接兼容。

### 2.2 不在本次范围

- 移动端 `m` 应用（EnterpriseDetailScreen 保持 4 Tab 现状）；
- 除驾驶舱与模块页外的其他页面（工作台、预案、设置、公开页等）；
- 企业列表页视觉改造；
- 主题切换/驾驶舱自定义能力；
- 驾驶舱内各图表的交互下钻（如点击环形图区块筛选风险），仅做入口跳转。

## 3. 信息架构：模块重新归类

10 个一级模块，归为 4 组。图标名与二级功能映射如下（驾驶舱底部导航按此顺序渲染）：

| 组 | 模块 | 二级功能（二级导航/现有子页） |
|----|------|-------------------------------|
| 组1 基础档案 | 基本信息 | 企业档案、GIS 定位、厂区平面图、编辑 |
| 组1 基础档案 | 组织架构 | 应急指挥部、应急小组、成员维护 |
| 组1 基础档案 | 周边环境 | 周边单位、敏感目标、交通状况 |
| 组2 风险与隐患 | 危险化学品 | 化学品台账、AI 生成、与风险对象关联 |
| 组2 风险与隐患 | 风险分级管控 | 数据编辑：风险树编辑 / 楼层平面图 / 评估方法 / 风险与隐患配置；成果输出：可视化总览 / 四色图工作台 / 管控清单 / 风险告知卡 / 风险公示 |
| 组2 风险与隐患 | 隐患排查治理 | 排查管理：隐患台账 / 排查计划 / 排查任务 / 排查模板；分析公示：隐患看板 / 隐患公示 |
| 组3 应急准备 | 应急资源 | 内部物资、外部救援力量 |
| 组4 报告与预案 | 风险评估报告 | AI 生成章节、预览、下载、合并 |
| 组4 报告与预案 | 应急资源调查报告 | AI 生成章节、预览、下载、合并 |
| 组4 报告与预案 | 预案管理 | 企业预案列表、新建、版本、导出 |

## 4. 企业驾驶舱页面设计

### 4.1 整体构图（指挥大屏三段式）

```
┌──────────────────────────────────────────────────────────────┐
│ 顶栏：返回企业列表 · 企业名 · 系统状态/行业/重大风险Tag · 编辑  │
├──────────────────────────────────────────────────────────────┤
│ 数据跑马灯（风险/隐患/资源/完成度滚动）                        │
├──────────────┬───────────────────────────────┬───────────────┤
│ 左翼 240px   │ 中翼（自适应）                 │ 右翼 276px    │
│ 风险等级分布  │ 风险雷达（264px 核心视觉）     │ 待办提醒      │
│ 环形图+图例  │ · 扫描光锥/轨道点/等级光点     │ 数据完成度环  │
│ 重大风险 TOP │ · 中心综合风险指数             │ 最近动态      │
│              │ 分区风险分布堆叠条              │               │
├──────────────┴───────────────────────────────┴───────────────┤
│ 底部：10 模块图标导航（SVG 线性图标 + 悬停辉光）               │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 区块明细

**顶栏**：返回企业列表（`←`）；企业名称 + 副标 `Enterprise Cockpit · 企业驾驶舱`；右侧「系统运行正常」呼吸灯、行业 Tag、重大风险计数 Tag（红色）、「编辑企业」主按钮（蓝青渐变）。

**数据跑马灯**：风险事件/重大/较大/一般/低、待整改/整改中/已闭环隐患、应急资源、预案、数据完成度，共 11 项，双份内容无缝滚动（22s 一轮）。

**左翼**

- 风险等级分布：conic-gradient 环形图（重大 #ff4d4f / 较大 #ff9f43 / 一般 #ffd666 / 低 #40a9ff），中心为事件总数，下方四色图例 + 计数；
- 重大风险 TOP：最多 3 条，色条（等级色）+ 名称 + 综合得分 + 责任部门，按得分降序。

**中翼**

- 风险雷达（核心视觉）：264px 圆，4 层同心环（含虚线环）+ 十字线 + 旋转扫描光锥（4.2s）+ 2 个轨道点（8s/11s 反向）+ 5 个按风险等级着色的光点（呼吸脉冲）+ 中心「综合风险指数」；
- 分区风险分布：按管控区域的水平堆叠条（四色分段 + 总数），区域名 + 计数。

**右翼**

- 待办提醒：最多 3 条，优先级色条（红/橙/蓝），标题 + 说明；
- 数据完成度：环形进度（78% 示例） + 6 模块勾选清单（基本信息/组织架构/危险化学品/应急资源/周边环境/报告，✓/…/✕ 三态）；
- 最近动态：3 条，操作人 + 动作 + 时间。

**底部导航**：10 模块图标（自绘线性 SVG：建筑/组织网络/地球/烧瓶/盾牌/搜索/卡车/图表/清单/文件），中文标签 + 英文角标（ARCHIVE/ORG/GEO/CHEM/RISK/HAZARD/RESCUE/REPORT/SURVEY/PLAN）；悬停浮起 + 辉光；「风险管控」「隐患治理」带红点 badge（有高等级数据时）。

### 4.3 背景层与动效规范

背景自底向上：深空渐变 → 网格（26px）→ 双光晕（右上蓝、左下青，blur 28-30px）→ 底部透视网格地台（rotateX 58°）→ 两侧数据流竖线 → 漂浮粒子（≤8 个，7-10s 上升）→ 全页扫描线（6-7s）。

动效清单（全部 CSS，禁用 JS 动画）：

| 动效 | 参数 | 用途 |
|------|------|------|
| 雷达扫描 | 4.2s linear infinite | 雷达光锥旋转 |
| 轨道点 | 8s / 11s（反向） | 雷达外圈卫星点 |
| 风险光点脉冲 | 2s ease-in-out（错峰延迟） | 等级光点 |
| 粒子上升 | 7-10s linear（错峰延迟） | 背景粒子 |
| 数据流 | 1.5s linear infinite | 两侧竖线 |
| 扫描线 | 6-7s linear infinite | 全页光束 |
| 跑马灯 | 22s linear infinite | 数据带 |
| 数字/呼吸辉光 | 2.4s ease-in-out | 关键数字 |
| 导航悬停 | 0.22s ease | 图标浮起 + 辉光 |
| 系统状态灯 | 1.8s ease-in-out | 在线呼吸 |

**无障碍与降级**：`@media (prefers-reduced-motion: reduce)` 下禁用上述全部动效（保留静态辉光或直接关闭）；文本对比度：主文本 #eaf2ff on #0a1d3f ≥ 12:1，辅助文本 #8aa3c8 ≥ 7:1，满足 WCAG AA。

### 4.4 视觉令牌（设计系统）

| Token | 值 |
|-------|-----|
| 背景 bg0/bg1/bg2 | #030814 / #06112a / #0a1d3f |
| 面板 | linear-gradient(160deg, rgba(19,38,74,.78), rgba(8,18,42,.9)) |
| 面板边框 | rgba(0,212,255,.20)；顶边光带 rgba(0,212,255,.55) |
| 强调色 | cyan #00d4ff / blue #2f81f7 |
| 主文本 / 辅助文本 | #eaf2ff / #8aa3c8 |
| 风险色 | 重大 #ff4d4f / 较大 #ff9f43 / 一般 #ffd666 / 低 #40a9ff |
| 数字排版 | font-variant-numeric: tabular-nums；渐变文字 + drop-shadow 辉光 |
| 圆角/描边 | 面板 10px；角标 1.5px cyan；按钮 6px 蓝青渐变 |

## 5. 模块页设计（方案 B：左竖分组导航）

### 5.1 通用规则

- 模块页**保持现有浅色系统风格**（Ant Design 组件、白底卡片），仅新增统一外壳；
- 统一外壳：顶部「← 返回企业驾驶舱」+ 模块名（可含统计 Tag 与主操作按钮，沿用现有页面自带操作）；
- 复杂模块（风险分级管控、隐患排查治理）在内容区左侧增加浅色竖向分组导航；其余 8 个模块无导航，直接渲染内容。

### 5.2 左竖分组导航

浅色样式：白底侧栏 + 组标题（小号大写灰字）+ 菜单项；选中项浅蓝底 #e6f0ff、文字 #1677ff、右侧 2px 蓝色竖条。

| 模块 | 组 1 | 组 2 |
|------|------|------|
| 风险分级管控 | 数据编辑：风险树编辑 / 楼层平面图 / 评估方法 / 风险与隐患配置 | 成果输出：可视化总览 / 四色图工作台 / 管控清单 / 风险告知卡 / 风险公示 |
| 隐患排查治理 | 排查管理：隐患台账 / 排查计划 / 排查任务 / 排查模板 | 分析公示：隐患看板 / 隐患公示 |

导航点击后切到对应子页；URL 变化（NavLink 高亮），支持浏览器前进/后退与刷新保持。

### 5.3 实现方式

- 新增 `ModulePageShell` 布局组件：顶栏（返回驾驶舱）+ 可选 `ModuleSideNav` + `<Outlet/>`；
- 风险管控/隐患治理使用嵌套路由，现有子页面（RiskOverviewPage、RiskMappingWorkbenchPage、RiskControlListPage、RiskNoticeCardPage、RiskPublicityPage、RiskMethodListPage/Editor、EnterpriseDictConfigPage、HazardPlanPage/TaskPage/RecordDetail/TemplatePage/DashboardPage/PublicityPage 等）作为子路由渲染在壳内，**页面自身内容与逻辑不动**，仅包裹布局；
- 风险树编辑为现有 `RiskManagementTab` 内的核心内容：拆出为独立 `RiskTreePanel` 组件供模块页默认路由使用（行为不变）；
- 隐患台账为现有 `HazardInspectionTab` 核心内容，同理拆为 `HazardLedgerPanel`。

## 6. 路由设计

新路由清单（相对 `/enterprises/:id`）：

| 路径 | 页面 | 说明 |
|------|------|------|
| `/enterprises/:id` | 企业驾驶舱 | 替换现有 Tabs 详情页 |
| `/enterprises/:id/modules/info` | 基本信息 | 复用 EnterpriseInfoCards |
| `/enterprises/:id/modules/surrounding` | 周边环境 | 复用 SurroundingInfoPanel |
| `/enterprises/:id/modules/chemicals` | 危险化学品 | 复用 HazardousChemicalsTab |
| `/enterprises/:id/risk-management` | 风险分级管控（壳） | 默认=风险树 |
| `/enterprises/:id/risk-management/overview` | 可视化总览 | 壳内子路由（迁移自 /risk-overview，保留旧路径重定向） |
| `/enterprises/:id/risk-management/workbench` | 四色图工作台 | 同上 |
| `/enterprises/:id/risk-management/control-list` | 管控清单 | 同上 |
| `/enterprises/:id/risk-management/notice-cards` | 风险告知卡 | 同上 |
| `/enterprises/:id/risk-management/publicity` | 风险公示 | 同上 |
| `/enterprises/:id/risk-management/methods` | 评估方法 | 同上 |
| `/enterprises/:id/risk-management/data-dicts` | 风险与隐患配置 | 同上 |
| `/enterprises/:id/risk-management`（?floor=1） | 楼层平面图 | 不单独建路由：导航项「楼层平面图」点击后进入风险树页并自动打开现有 FloorManagementDrawer 抽屉 |
| `/enterprises/:id/hazard` | 隐患排查治理（壳） | 默认=隐患台账 |
| `/enterprises/:id/hazard/plans` `/tasks` `/templates` `/dashboard` `/publicity` `/records/:rid` | 隐患子页 | 壳内子路由（沿用现有路径） |
| `/enterprises/:id/modules/resources` | 应急资源 | 复用 EmergencyResourceForm |
| `/enterprises/:id/modules/assessment` | 风险评估报告 | 复用 RiskAssessmentTab |
| `/enterprises/:id/modules/investigation` | 应急资源调查报告 | 复用 ResourceInvestigationTab |
| `/enterprises/:enterprise_id/plans` | 预案管理 | 现有页面 |
| `/enterprises/:id/org` | 组织架构 | 现有页面，加返回驾驶舱 |
| `/enterprises/:id/edit` | 编辑企业 | 不变 |

兼容规则：

- 旧详情页 `?tab=xxx` 参数不再生效：驾驶舱忽略该参数（不重定向，避免死链）；从旧链接进入的页面路径均为完整路由，不受影响；
- 现有 `/risk-overview` 等旧路径保留 302 重定向到新壳内路径，避免外部引用失效；
- 驾驶舱模块图标点击目标见第 3 节映射。

## 7. 数据需求

### 7.1 新增后端端点

`GET /api/v1/enterprises/{id}/cockpit-summary`（企业归属校验：非本人企业 404，与现有 `_get_ent` 一致）返回：

```json
{
  "risk_counts": { "major": 2, "larger": 4, "general": 18, "low": 10, "total": 34 },
  "top_risks": [{ "name": "液氨储罐区", "level": "重大", "score": 82, "responsible_unit": "生产部" }],
  "zone_risks": [{ "zone_name": "生产车间", "counts": { "major": 1, "larger": 2, "general": 8, "low": 2 }, "total": 13 }],
  "risk_index": 62,
  "todos": [{ "priority": "high", "title": "风险评估报告未生成", "note": "建议本周完成" }],
  "completion": { "percent": 78, "modules": [{ "key": "enterprise_info", "label": "基本信息", "done": true }] },
  "recent_activities": [{ "actor": "张伟", "action": "更新了组织架构", "time": "2026-08-16T10:32:00+08:00" }]
}
```

### 7.2 计算规则

- **风险等级分布 / 分区分布 / TOP**：从风险层级树（zone→object→unit→event）聚合，事件级 `risk_level` 与 `risk_score` 取值；TOP 按 `risk_score` 降序取 3；
- **综合风险指数 risk_index**（0-100）：`min(100, round(major*100 + larger*70 + general*40 + low*10))` 按企业规模系数归一（规格默认直接取该式，超过 100 截断；后续可配置权重）；
- **待办提醒**：由三类信号派生——①风险评估/应急资源调查报告 status 非 completed；②隐患整改到期（deadline 3 天内且状态未闭环）；③数据完成度缺失模块（周边环境/报告未完成时提示）；
- **完成度**：复用 onboarding `completion` 逻辑与 `MODULE_KEY_MAP`（enterprise_info/org_structure/risk_chemical/resources/surrounding/reports 6 模块），不重复实现；
- **最近动态**：MVP 从企业 `updated_at` 与各子模块最近更新时间聚合，操作人字段可为空（显示「系统」），不做操作审计表（后续如需再建）。

### 7.3 现有接口复用

`completion`（onboarding）、`getFullHierarchy`（风险树，驾驶舱可复用前端已有数据或由汇总端点聚合）、隐患 dashboard、报告状态（现有 `getRiskAssessment/getResourceInvestigation` 的 status/isError 模式）、enterprise 基础字段。**推荐前端驾驶舱只调 cockpit-summary 一个端点**（+ 企业基础字段随列表接口已有），避免并发多接口。

### 7.4 空数据与错误态

- 无风险数据：环形图显示空环 + 「暂无风险数据」，雷达中心指数显示 `--`，分区列表显示空态；
- 无待办：显示「暂无待办事项」；
- 完成度无数据：环显示 `--`，模块勾选全 `…`；
- 端点失败：整页骨架转错误提示 + 重试按钮，不阻塞模块导航使用。

## 8. 前端组件结构

```
pages/Enterprise/
  EnterpriseCockpitPage.tsx          # 驾驶舱主页面（数据编排 + 布局）
components/enterprise/cockpit/
  CockpitBackground.tsx              # 背景层（网格/光晕/粒子/数据流/扫描线/地台）
  CockpitHeader.tsx                  # 顶栏
  CockpitTicker.tsx                  # 数据跑马灯
  RiskRadarPanel.tsx                 # 雷达 + 分区分布
  RiskDonutPanel.tsx                 # 环形图 + 图例 + TOP
  CockpitTodoPanel.tsx               # 待办提醒
  CockpitCompletionPanel.tsx         # 完成度环 + 模块清单
  CockpitActivityPanel.tsx           # 最近动态
  ModuleNav.tsx                      # 10 模块图标导航（SVG 组件内置）
  ModulePageShell.tsx                # 模块页外壳（返回驾驶舱 + ModuleSideNav + Outlet）
  ModuleSideNav.tsx                  # 左竖分组导航
services/
  cockpitService.ts                  # cockpit-summary 前端服务（箭头函数 + 解包，遵循项目惯例）
styles/
  cockpit.css                        # 驾驶舱专属样式（不污染全局）
```

复用不改动：EnterpriseInfoCards、OrgStructureEditor、EmergencyResourceForm、SurroundingInfoPanel、HazardousChemicalsTab、RiskManagementTab（拆出 RiskTreePanel）、HazardInspectionTab（拆出 HazardLedgerPanel）、RiskAssessmentTab、ResourceInvestigationTab、全部风险/隐患子页面。

## 9. 测试策略

### 9.1 后端

- `cockpit-summary` 端点：鉴权 404（他人企业）、聚合正确性（构造已知风险树断言各计数/TOP/分区）、空企业、待办派生（报告未完成/隐患到期/完成度缺失）、risk_index 截断；
- 既有全量 pytest 无回归。

### 9.2 前端

- `cockpitService` 契约测试（URL/解包）；
- 驾驶舱组件渲染测试（vitest）：各面板空态/有数据态、模块导航 10 项渲染、`prefers-reduced-motion` 降级类生效；
- `ModuleSideNav` 分组与高亮测试；
- `tsc -b`、`eslint` 通过；
- Playwright 冒烟：进入驾驶舱 → 点模块图标 → 到达模块页 → 左竖导航切换 → 返回驾驶舱；旧 `?tab=` 链接不 404。

## 10. 验收标准

| 编号 | 验收项 |
|------|--------|
| AC1 | `/enterprises/:id` 显示深色驾驶舱，10 模块图标平铺且点击进入对应模块页 |
| AC2 | 模块页保持浅色系统风格；风险管控/隐患治理有左竖分组导航且高亮正确 |
| AC3 | 驾驶舱各区块展示真实数据（汇总端点），空数据有占位 |
| AC4 | 非本人企业访问驾驶舱/汇总端点返回 404 |
| AC5 | 旧 `/enterprises/:id?tab=xxx` 链接不 404；旧 `/risk-overview` 等路径重定向到壳内路径 |
| AC6 | `prefers-reduced-motion` 下动效降级，页面可正常使用 |
| AC7 | 驾驶舱加载失败有错误态与重试，不阻塞模块导航 |
| AC8 | 后端全量测试、前端 tsc/eslint/vitest 全部通过 |

## 11. 风险与取舍

- **RiskManagementTab 拆分**：树编辑拆为 RiskTreePanel 时需保持行为不变，拆分为纯布局抽取，不做逻辑重构（项目「页面自包含」惯例的例外以模块壳为边界）；
- **壳内子路由迁移**：现有子页从独立路由迁到壳内会改变其页面宽度/上下文，需逐页冒烟；保留旧路径重定向兜底；
- **最近动态数据来源**：无审计表，MVP 用更新时间聚合，数据可能不够丰富，标注为已知取舍；
- **risk_index 公式**：先按固定权重实现，权重可配留到后续。
