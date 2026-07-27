# 预案列表筛选查询功能 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在预案列表（桌面 + 移动端）增加企业名搜索、预案标题搜索、跨企业预案列表、服务端分页筛选，让用户在企业数量多时能快速定位目标。

**架构：** 后端 `GET /api/v1/plans` 已支持 `enterprise_id` 为空的全企业查询及 `search`/`plan_type`/`status` 过滤。方案核心是前端改造——将 `planService.ts` 的 `enterprise_id` 从必填改为可选，让 PlanListPage 支持"跨企业模式"并迁移到服务端搜索/分页；PlanCardsPage 增加客户端企业名筛选；移动端对齐桌面端能力。

**技术栈：** React 18 + TypeScript + Ant Design 5（桌面）+ 自研 mobile-ui（移动端）+ React Query + React Router v6

---

## 涉及文件总览

| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/src/services/planService.ts` | 修改 | `enterprise_id` 改为可选 |
| `frontend/src/pages/Plan/PlanCardsPage.tsx` | 修改 | 增加企业名搜索 + 行业筛选（客户端） |
| `frontend/src/pages/Plan/PlanListPage.tsx` | 重写 | 支持跨企业模式 + 服务端搜索/分页 |
| `frontend/src/routes/index.tsx` | 修改 | 新增 `/plans/all` 路由 |
| `frontend/src/types/plan.ts` | 修改 | `EnterprisePlanSummary` 增加 `industry` 字段 |
| `backend/app/schemas/plan.py` | 修改 | `EnterprisePlanSummary` 增加 `industry` 字段 |
| `backend/app/routers/plans.py` | 修改 | `enterprise_plan_summary` 查询 JOIN `industry` |
| `frontend/src/mobile/screens/EnterprisePlanListScreen.tsx` | 修改 | 增加搜索输入 + 状态筛选 |
| `frontend/src/mobile/screens/PlanCardsScreen.tsx` | 修改 | 增加企业名搜索（客户端） |

---

## 现状分析

### 后端现状（基本无需改动）

`backend/app/routers/plans.py` 的 `list_plans` 端点：
- `enterprise_id` 默认空字符串，为空时不限制企业 → **跨企业查询已可用**
- 支持 `search`（title ILIKE）、`plan_type`、`status` 过滤
- 支持 `page`/`page_size` 标准分页，返回 `total`
- 每条记录含 `enterprise_name` 字段

### 前端现状与问题

| 页面 | 问题 |
|------|------|
| PlanCardsPage（桌面 预案总览） | 无任何搜索/筛选，企业多时只能手动翻卡片 |
| PlanListPage（桌面 企业内预案列表） | `enterprise_id` 必填，无法跨企业；search 走客户端（page_size=100 全加载再过滤，数据量大时崩） |
| PlanCardsScreen（移动端 预案总览） | 同桌面 PlanCardsPage，无搜索 |
| EnterprisePlanListScreen（移动端 企业内预案列表） | 仅有类型筛选，缺搜索和状态筛选 |

### 设计决策：为什么不在 PlanCardsPage 上做"跨企业预案搜索"

PlanCardsPage 的定位是"企业卡片总览"，展示的是企业维度的汇总统计，不是预案列表。把预案级搜索塞进去会破坏信息架构。正确做法：

- **PlanCardsPage**：增强企业级筛选（按企业名、行业搜索） → 点卡片进入该企业的预案列表
- **PlanListPage**：增强为"可跨企业模式"，当 URL 无 `enterprise_id` 时展示全部企业的预案，支持跨企业搜索

---

## 任务分解

### 任务 1：planService 类型和接口调整

**文件：** `frontend/src/services/planService.ts`

将 `PlanQueryParams.enterprise_id` 从必填改为可选。

**变更：**

```typescript
export interface PlanQueryParams extends PaginationParams {
  enterprise_id?: string;  // 可选：不传 = 查询全部企业的预案
  plan_type?: string;
  status?: string;
  search?: string;
}
```

**验证：**

```bash
cd frontend && npx tsc --noEmit
```

---

### 任务 2：PlanListPage 重写 — 支持跨企业模式 + 服务端搜索/分页

**文件：** `frontend/src/pages/Plan/PlanListPage.tsx`

**改动要点：**

1. `enterprise_id` URL 参数改为可选，不存在时展示全部企业预案
2. search/类型/状态三个过滤器全部走服务端（作为 queryKey 触发 React Query 自动重新请求）
3. 用 Ant Design `Table` 的分页组件替代 `List` 组件，支持服务端分页（page_size=20）
4. 跨企业模式时表格多显示一列「所属企业」
5. 页面标题根据模式动态变化：「全部预案」vs「XX企业 - 预案列表」
6. 筛选条件变更时重置到第一页

**完整代码：** 见 [PlanListPage.tsx](/frontend/src/pages/Plan/PlanListPage.tsx)（在分支实现时直接替换现有文件）

**验证：**

```bash
cd frontend && npx tsc --noEmit
```

---

### 任务 3：PlanCardsPage 增加企业名搜索 + 行业筛选

**文件：** `frontend/src/pages/Plan/PlanCardsPage.tsx`

**改动要点：**

1. 页面顶部添加 `Input` 搜索框（企业名）+ `Select` 行业下拉
2. 使用 `useMemo` 对 `summaries` 做客户端双重过滤
3. 搜索无结果时显示「未找到匹配企业」空态
4. 标题栏增加「全部预案列表」按钮，跳转到 `/plans/all`

**注意：** 行业筛选依赖任务 5 的 `industry` 字段，在此之前行业筛选 UI 保留但暂不生效。

**验证：**

```bash
cd frontend && npx tsc --noEmit
```

---

### 任务 4：跨企业预案列表路由注册

**文件：** `frontend/src/routes/index.tsx`

在 contentRoutes 中添加新路由：

```typescript
{ path: "/plans/all", element: <PlanListPage /> },
```

放在 `/plans` 路由附近即可。

**验证：**

```bash
cd frontend && npx tsc --noEmit
```

---

### 任务 5：EnterprisePlanSummary 扩展 industry 字段

**文件：**
- `backend/app/schemas/plan.py`
- `backend/app/routers/plans.py`
- `frontend/src/types/plan.ts`
- `frontend/src/pages/Plan/PlanCardsPage.tsx`（补全行业过滤逻辑）

**后端改动：**

1. `EnterprisePlanSummary` schema 增加 `industry: str = ""`
2. `enterprise_plan_summary` 查询中 JOIN `Enterprise.industry`，构建响应时传入

**前端改动：**

1. `EnterprisePlanSummary` 接口增加 `industry: string`
2. PlanCardsPage 过滤逻辑加入 `item.industry === industry` 判断

**验证：**

```bash
cd backend && python -c "from app.schemas.plan import EnterprisePlanSummary; print('OK')"
cd frontend && npx tsc --noEmit
```

---

### 任务 6：移动端 EnterprisePlanListScreen 搜索 + 状态筛选补全

**文件：** `frontend/src/mobile/screens/EnterprisePlanListScreen.tsx`

**改动要点：**

1. 新增 `search` 和 `statusFilter` 状态
2. 在筛选 Chips 上方添加搜索输入框（`Input` + `Search` icon）
3. 在类型筛选 Chips 下方添加状态筛选 Chips 行（全部/草稿/已完成）
4. 搜索和状态作为 queryKey 传入 `listPlans`，走服务端筛选

**验证：**

```bash
cd frontend && npx tsc --noEmit
```

---

### 任务 7：移动端 PlanCardsScreen 增加企业名搜索

**文件：** `frontend/src/mobile/screens/PlanCardsScreen.tsx`

**改动要点：**

1. 新增 `search` 状态 + `useMemo` 客户端过滤 enterprises 列表
2. 在统计概览卡片和企业列表之间添加搜索输入框
3. 过滤后的 `filteredEnterprises` 替代原来的 `enterprises` 用于 `withPlans`/`withoutPlans` 分组

**验证：**

```bash
cd frontend && npx tsc --noEmit
```

---

## 自检

### 规格覆盖度

| 需求 | 对应任务 |
|------|---------|
| 企业多时快速找到企业 | 任务 3（桌面搜索）、任务 7（移动端搜索）、任务 2（跨企业预案列表） |
| 预案列表中筛选查询 | 任务 2（服务端搜索/分页/类型/状态）、任务 6（移动端搜索/状态） |
| 跨企业预案搜索 | 任务 2（跨企业模式）、任务 4（路由） |
| 行业筛选 | 任务 3（UI）、任务 5（后端字段） |

### 类型一致性

- `PlanQueryParams.enterprise_id` 在任务 1 改为可选后，任务 2 和 6 均使用 `enterprise_id || undefined`
- `EnterprisePlanSummary.industry` 在任务 5 前后端同步
- `PlanResponse.enterprise_name` 后端已有，前端 `PlanProject` 已有该字段
- 所有 import 路径均使用项目 `@/` alias，与 tsconfig 一致

### 未覆盖项（后续可扩展）

- URL 查询参数持久化（筛选条件同步到 URL search params，支持分享/书签）— 可后续追加
- 键盘快捷键（Ctrl+K 聚焦搜索框）— 可后续追加
- 移动端 PlanCardsScreen 的「全部预案列表」入口 — 当前移动端设计以卡片为主，可后续添加
