# PRD-M03：移动端工作台

> **版本**：1.0 | **创建日期**：2026-06-09 | **依赖**：PRD-M00, PRD-M01, PRD-M02, PRD-08（桌面端工作台） | **关联文档**：移动端设计方案 §5.4

---

## 1. 模块概述

工作台是用户登录后的首屏，提供全系统状态概览和快捷操作入口。移动端工作台完全不同于桌面端的卡片+表格布局，采用**信息流**设计：统计卡片横向滑动 → 快捷操作 → 最近编辑列表。

**核心体验**：5 秒内获取系统概况（几个预案、几个企业、最近在改什么），2 步内开始一次新建预案。

**与本模块相关的文件**：

| 文件 | 职责 |
|------|------|
| `mobile/screens/DashboardScreen.tsx` | 工作台主页 |
| `mobile/components/ui/FAB.tsx` | 浮动操作按钮（Speed Dial） |
| `mobile/store/appStore.ts` | 企业切换状态 |
| `services/planService.ts` | 共享 API — 预案统计、最近列表 |
| `services/enterpriseService.ts` | 共享 API — 企业列表 |

**复用的后端 API**（不做任何修改）：

| 端点 | 用途 |
|------|------|
| `GET /api/v1/enterprises` | 企业列表（用于企业切换器） |
| `GET /api/v1/plans/enterprise-summary` | 企业预案统计汇总（若已实现） |
| `GET /api/v1/plans?page=1&page_size=5&sort=updated_at` | 最近编辑的预案 |

> **注意**：如果 `GET /api/v1/plans/enterprise-summary` 未实现，Dashboard 的统计需要通过前端聚合企业列表 + 逐企业查询预案数量。建议先实现 summary 端点以避免 N+1 问题。

---

## 2. DashboardScreen 详细设计

**文件**：`mobile/screens/DashboardScreen.tsx`

**路由**：`/m/dashboard`

### 2.1 整体布局（自上而下，滚动）

```
┌──────────────────────────────────────┐
│            [SafeArea Top]            │
│                                      │
│  工作台                               │  ← NavBar largeTitle
│                                      │
│  当前企业：西安宝岳空间科技  ▼         │  ← 企业切换器（点击弹出 BottomSheet）
│  2026年6月9日 星期一                  │  ← text-caption Neutral 400
│                                      │
│  ┌──────────┬──────────┬──────────┐  │
│  │ 预案总数  │ 已完成   │ 管理企业  │  │  ← 水平滚动卡片组
│  │   12    │    8    │    3     │  │     snap 吸附，每张 116×96px
│  │ 较上月+2 │ 完成率67%│          │  │     bg-white, rounded-md, shadow-card
│  └──────────┴──────────┴──────────┘  │
│                                      │
│  快捷操作                             │  ← 区块标题：text-h2
│                                      │
│  ┌─ 📋 新建综合应急预案 ──────────→ ─┐│  ← 3 张操作卡片
│  │   从企业信息自动生成完整框架     ││     每张 h-14, 左图标+标题+描述+chevron
│  └──────────────────────────────────┘│     bg-white, rounded-md
│                                      │
│  ┌─ 🎯 新建专项应急预案 ──────────→ ─┐│
│  │   针对特定事故类型（火灾、触电等）││
│  └──────────────────────────────────┘│
│                                      │
│  ┌─ 🏭 新建现场处置方案 ──────────→ ─┐│
│  │   一线操作卡片式应急处置步骤     ││
│  └──────────────────────────────────┘│
│                                      │
│  最近编辑                    查看全部 →│  ← 区块标题
│                                      │
│  ┌─ 综合应急预案 ──────────────────┐│  ← PlanCard 列表（最多 5 条）
│  │ 西安宝岳空间科技  ·  2小时前     ││     每张 Card pressable
│  │ [综合] [已完成]                  ││     点击进入 PlanEditorScreen
│  └──────────────────────────────────┘│
│                                      │
│  ┌─ 火灾专项应急预案 ──────────────┐│
│  │ 西安宝岳空间科技  ·  昨天        ││
│  │ [专项] [草稿]                    ││
│  └──────────────────────────────────┘│
│                                      │
│  ┌─ 触电现场处置方案 ──────────────┐│
│  │ 西安宝岳空间科技  ·  3天前       ││
│  │ [现场] [已完成]                  ││
│  └──────────────────────────────────┘│
│                                      │
│         [SafeArea Bottom + TabBar]   │
└──────────────────────────────────────┘

                 ◎                  ← FAB (56×56px), position:fixed
                                    bottom: 16px + tabbar + safe
                                    right: 16px
```

### 2.2 组件级分解

#### (A) 企业切换器

- 位置：大标题下方第一行
- 显示当前企业名称（`text-h3` Semibold）+ 右侧 `ChevronDown` 14px
- 点击弹出 BottomSheet：
  - 标题：「选择工作企业」
  - 列表：用户所有企业（从 `GET /api/v1/enterprises` 或 Zustand cache）
  - 每项：Avatar + 企业名称，选中项右侧 `Check` 蓝色图标
  - 底部：「管理企业 →」链接跳转 `/m/enterprises`
- 切换后：更新 `appStore.currentEnterpriseId`，Dashboard 统计和最近编辑列表随之刷新
- 如果无企业：显示「暂未添加企业」+「去添加 →」链接

#### (B) 统计卡片组

- 3 张卡片，水平 `<div className="flex gap-md overflow-x-auto snap-x snap-mandatory hide-scrollbar px-md">`
- 每张卡片：`min-w-[116px] h-24 bg-white rounded-md shadow-card flex flex-col justify-center p-md`
- 大数字：`text-display`（34px Bold），颜色：预案总数=Primary 600，已完成=Success，企业数=Neutral 900
- 标签：`text-caption` Neutral 400，大数字下方 4px
- 趋势文字（可选，如有上月数据）：`text-caption`，「较上月+2」Success / 「持平」Neutral 400

**数据来源**：
- 预案总数 / 已完成数：`GET /api/v1/plans/enterprise-summary`（按当前企业过滤）
- 企业数：Zustand `enterprises.length`

**加载态**：3 张 Skeleton（card variant）

**空态**（0 预案）：数字显示 0，颜色保持 Neutral 900

#### (C) 快捷操作卡片

- 3 张卡片，垂直排列，间距 12px
- 每张：`h-14 bg-white rounded-md shadow-card flex items-center px-md cursor-pointer active:scale-[0.99]`
- 布局（从左到右）：
  - 图标圆形容器：40×40px，`rounded-full`，Primary 50 背景
  - 图标：20px，Primary 600（Lucide：`FileText` / `Target` / `Factory`）
  - 文字区：`ml-md flex-1`
    - 标题：`text-body` Semibold Neutral 900
    - 描述：`text-caption` Neutral 400（1 行省略）
  - 右侧：`ChevronRight` 16px，Neutral 400
- 点击行为：
  - 综合 → `navigate("/m/plans/new?type=comprehensive")`
  - 专项 → `navigate("/m/plans/new?type=special")`
  - 现场 → `navigate("/m/plans/new?type=onsite")`

#### (D) 最近编辑列表

- 标题「最近编辑」+ 右侧「查看全部 →」链接（跳转 `/m/plans`）
- 每条：`<Card pressable>` 包装的 `<PlanCard>`
- PlanCard 内容（详见 PRD-M04 的 PlanCard 组件规范）：
  - 标题：`text-h3`
  - 副标题：企业名 + 时间
  - 标签：Badge（类型 + 状态）
- 最多 5 条，无数据时显示 EmptyState：「暂无编辑记录」+「新建预案」按钮
- 点击 → `navigate("/m/plans/:id/edit")`

#### (E) FAB（浮动操作按钮）

- 右下角 `position: fixed`
- 56×56px 圆形，Primary 600，shadow-fab
- 图标：`Plus` 24px 白色
- 点击：展开 Speed Dial（3 个操作项，从下往上 stagger 动画）：
  1. 综合应急预案 → `navigate("/m/plans/new?type=comprehensive")`
  2. 专项应急预案 → `navigate("/m/plans/new?type=special")`
  3. 现场处置方案 → `navigate("/m/plans/new?type=onsite")`
- Speed Dial 展开时：FAB 图标变为 `X`（旋转 45°），背景遮罩覆盖全屏
- 点击遮罩或再次点击 FAB → 关闭 Speed Dial
- 滚动页面时 FAB 自动缩小为 mini (40×40px)，停止滚动 1s 后恢复

---

## 3. 数据流

```
DashboardScreen mount
  │
  ├─ 1. 读取 appStore.currentEnterpriseId
  │   ├─ 有 → 进入步骤 2
  │   └─ 无 → 默认选第一个企业（GET /enterprises → items[0]）
  │
  ├─ 2. 并行请求（React Query）：
  │   ├─ useQuery(["enterprise-summary", currentEnterpriseId], fetchSummary)
  │   ├─ useQuery(["recent-plans", currentEnterpriseId], fetchRecentPlans)
  │   └─ useQuery(["enterprises"], fetchEnterprises)  // 企业切换器
  │
  └─ 3. 渲染：统计卡片 + 快捷操作 + 最近列表
```

**React Query 配置**（Dashboard 页面级）：

```typescript
// staleTime 设为 60s —— 工作台数据不需要实时刷新
// refetchOnMount 为 true —— 每次进入 Dashboard 刷新
```

---

## 4. 状态覆盖

| 状态 | 统计卡片 | 快捷操作 | 最近列表 |
|------|----------|----------|----------|
| **加载中** | 3 张 Skeleton (card) | 3 张 Skeleton (h-14) | 3 条 Skeleton (list-item) |
| **正常** | 真实数据 | 正常显示 | 真实列表 |
| **0 数据** | 数字显示 0 | 正常显示（可点击创建） | EmptyState「暂无编辑记录」 |
| **网络错误** | 保留上次缓存数据 + 顶部 Toast「数据可能不是最新」 | 正常显示（离线可用） | 保留缓存 + Toast |
| **无企业** | 「0」「0」「0」 | 正常显示 → 点击时弹出「请先添加企业」 | EmptyState「暂无编辑记录」 |

---

## 5. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| M03-01 | 登录后 Dashboard 正常渲染（统计 + 快捷操作 + 最近列表） | 自动化 |
| M03-02 | 统计卡片数据正确（预案总数/已完成数/企业数） | 自动化（与 API 对比） |
| M03-03 | 统计卡片水平滑动 + snap 吸附 | 手动 |
| M03-04 | 快捷操作卡片点击跳转正确（3 种类型各带 query param） | 自动化 |
| M03-05 | 最近编辑点击 → 预案编辑器 | 自动化 |
| M03-06 | FAB 点击展开 Speed Dial（3 个选项） | 手动 |
| M03-07 | Speed Dial 选项点击跳转新建预案（带类型） | 自动化 |
| M03-08 | 企业切换器弹出 BottomSheet → 选择企业 → Dashboard 数据刷新 | 自动化 |
| M03-09 | 无企业时切换器显示「暂未添加企业」+ 跳转链接 | 手动 |
| M03-10 | 0 数据时统计显示 0，最近列表显示 EmptyState | 自动化 |
| M03-11 | 网络错误时使用缓存数据 + Toast 提示 | 手动（断网） |
| M03-12 | 视觉铁律检查通过 | 代码审查 |

---

> **下一文档**：PRD-M04 移动端企业管理模块
