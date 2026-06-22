# PRD-M04：移动端企业管理模块

> **版本**：1.0 | **创建日期**：2026-06-09 | **依赖**：PRD-M00, PRD-M01, PRD-02（桌面端企业管理）, PRD-11, PRD-12 | **关联文档**：移动端设计方案 §5.5~5.7

---

## 1. 模块概述

提供移动端完整的企业数据管理闭环：企业 CRUD、风险源管理、应急资源管理、周边环境、风险评估报告、应急资源调查报告。

**与本模块相关的文件**：

| 文件 | 职责 |
|------|------|
| `mobile/screens/EnterpriseListScreen.tsx` | 企业列表 |
| `mobile/screens/EnterpriseCreateScreen.tsx` | 新建企业 |
| `mobile/screens/EnterpriseDetailScreen.tsx` | 企业详情（含 Tab 切换） |
| `mobile/screens/EnterpriseEditScreen.tsx` | 编辑企业 |
| `mobile/screens/RiskSourceListScreen.tsx` | 风险源列表 |
| `mobile/screens/ResourceListScreen.tsx` | 应急资源列表 |
| `mobile/screens/RiskAssessmentScreen.tsx` | 风险评估报告 |
| `mobile/screens/ResourceInvestigationScreen.tsx` | 应急资源调查报告 |
| `mobile/components/enterprise/EnterpriseCard.tsx` | 企业卡片 |
| `mobile/components/enterprise/EnterpriseForm.tsx` | 企业表单（创建+编辑复用） |
| `mobile/components/enterprise/RiskSourceItem.tsx` | 风险源列表项 |
| `mobile/components/enterprise/ResourceItem.tsx` | 资源列表项 |
| `services/enterpriseService.ts` | 共享 API 服务 |
| `services/riskAssessmentService.ts` | 共享 API 服务 |

**复用的后端 API**（不做任何修改）：

| 端点 | 用途 |
|------|------|
| `GET/POST /api/v1/enterprises` | 企业列表 / 创建 |
| `GET/PUT/DELETE /api/v1/enterprises/{id}` | 企业详情 / 更新 / 删除 |
| `GET/POST /api/v1/enterprises/{id}/risk-sources` | 风险源列表 / 新增 |
| `PUT/DELETE /api/v1/enterprises/{id}/risk-sources/{rid}` | 风险源编辑 / 删除 |
| `GET/POST /api/v1/enterprises/{id}/resources` | 资源列表 / 新增 |
| `PUT/DELETE /api/v1/enterprises/{id}/resources/{rid}` | 资源编辑 / 删除 |
| `POST /api/v1/enterprises/{id}/risk-sources/generate` | AI 生成风险源（如有） |
| `POST /api/v1/enterprises/{id}/resources/generate` | AI 生成资源（如有） |
| `GET/POST /api/v1/enterprises/{id}/risk-assessment` | 风险评估报告 |
| `GET/POST /api/v1/enterprises/{id}/resource-investigation` | 资源调查报告 |

---

## 2. 页面详案

### 2.1 EnterpriseListScreen（企业列表）

**文件**：`mobile/screens/EnterpriseListScreen.tsx`

**路由**：`/m/enterprises`

**布局**：

```
┌──────────────────────────────────────┐
│ ← 企业列表               + 新建      │  ← NavBar: 标题 + 右侧 Plus 图标按钮
├──────────────────────────────────────┤
│ ┌─ 🔍 搜索企业名称... ──────────────┐│  ← 搜索栏：52px Input type="search"
│ └──────────────────────────────────────┘│     prefixIcon: Search
│                                      │
│ ┌─ 西安宝岳空间科技有限公司 ────────→ ┐│  ← EnterpriseCard
│ │ [头像] 工贸  ·  陕西省西安市       ││     pressable → 跳转详情
│ │        3个预案                     ││     左滑 → 删除（红色）
│ └──────────────────────────────────────┘│
│                                      │
│ ┌─ 陕西华安化工有限公司 ────────────→ ┐│
│ │ [头像] 危化  ·  陕西省渭南市       ││
│ │        2个预案                     ││
│ └──────────────────────────────────────┘│
│                                      │
│              ...无限滚动...           │
│                                      │
└──────────────────────────────────────┘
```

**组件**：EnterpriseCard

```typescript
interface EnterpriseCardProps {
  enterprise: Enterprise;
  onPress: () => void;
  onDelete: () => void;       // 左滑删除回调
}
```

- 布局：`h-[72px]`，flex 水平，`px-md`
- 左侧 Avatar md（44px）：首字母
- 主体：名称（`text-h3`）+ 行业 + 地区（`text-caption` Neutral 400）
- 右侧：预案数量 Badge（`count` 模式）+ `ChevronRight`
- 左滑：红色「删除」按钮（实现方式：Framer Motion `drag="x"` 或 CSS `translateX` + 手势）

**搜索栏**：
- 实时前端过滤（企业名称模糊匹配），300ms 防抖
- 不请求后端（企业列表数据已在内存）

**空状态**：EmptyState icon=`Building2` title="暂无企业档案" description="添加企业后即可开始创建应急预案" action="创建企业"

**数据加载**：`useQuery(["enterprises"])`，React Query 自动缓存。

---

### 2.2 EnterpriseCreateScreen（新建企业）

**文件**：`mobile/screens/EnterpriseCreateScreen.tsx`

**路由**：`/m/enterprises/new`

**布局**（分段表单 + 底部固定保存按钮）：

```
┌──────────────────────────────────────┐
│ ← 新建企业                           │
├──────────────────────────────────────┤
│                                      │
│  基本信息                             │  ← 分组标题 text-h2
│  ┌──────────────────────────────┐    │
│  │ 企业名称 *                   │    │  ← Input label + required
│  │ [                     ]      │    │
│  │                              │    │
│  │ 行业分类 *                   │    │  ← SelectSheet: 预置 + 自定义
│  │ 工贸                    ▼    │    │     触发弹出 BottomSheet 选择器
│  │                              │    │
│  │ 经营范围                     │    │
│  │ [                     ]      │    │  ← multiline Input
│  │                              │    │
│  │ 员工人数                     │    │
│  │ [ 0              ] 人       │    │  ← type="number"
│  └──────────────────────────────┘    │
│                                      │
│  地址信息                             │
│  ┌──────────────────────────────┐    │
│  │ 省 / 市 / 区          ▼      │    │  ← 级联 SelectSheet
│  │                              │    │
│  │ 详细地址                     │    │
│  │ [                     ]      │    │
│  └──────────────────────────────┘    │
│                                      │
│         [SafeArea Bottom]            │
│  ┌──────────────────────────────┐    │
│  │           保存                │    │  ← Button primary lg fullWidth
│  └──────────────────────────────┘    │     sticky bottom
└──────────────────────────────────────┘
```

**表单校验**：
- 企业名称：必填，1-100 字符
- 行业分类：必填
- 员工人数：≥0

**保存逻辑**：
1. `POST /api/v1/enterprises` → 成功
2. Toast「企业创建成功」
3. `navigate("/m/enterprises/:newId")`（跳转新企业详情）

**EnterpriseForm 组件**（创建 + 编辑复用）：

```typescript
// mobile/components/enterprise/EnterpriseForm.tsx
interface EnterpriseFormProps {
  initialValues?: Enterprise;      // 编辑模式传入
  onSubmit: (data: EnterpriseInput) => Promise<void>;
  submitLabel: string;             // "保存" / "创建企业"
}
```

- 表单状态由组件内部 `useState` 管理
- 校验在 `onSubmit` 前执行，未通过则 Input error 态显示

---

### 2.3 EnterpriseDetailScreen（企业详情）

**文件**：`mobile/screens/EnterpriseDetailScreen.tsx`

**路由**：`/m/enterprises/:id`

**布局**（顶部固定区 + 吸顶 Tab + 内容滚动）：

```
┌──────────────────────────────────────┐
│ ← 企业详情                   编辑    │  ← NavBar
├──────────────────────────────────────┤
│  西安宝岳空间科技有限公司             │  ← text-h1
│  工贸                                │  ← Badge
├──────────────────────────────────────┤
│ [基本信息] [风险源] [应急资源] [调查报告] │  ← SegmentedControl (吸顶 sticky)
├──────────────────────────────────────┤
│                                      │
│  ┌─ 企业名称 ───────────────────────┐│  ← 基本信息 Tab 内容
│  │ 西安宝岳空间科技有限公司          ││     label-value 对：
│  ├──────────────────────────────────┤│     label: text-caption Neutral 400
│  │ 行业分类                          ││     value: text-body Neutral 900
│  │ 工贸                              ││
│  ├──────────────────────────────────┤│
│  │ 经营范围                          ││
│  │ ...                               ││
│  ├──────────────────────────────────┤│
│  │ 员工人数                          ││
│  │ 150 人                            ││
│  ├──────────────────────────────────┤│
│  │ 地址                              ││
│  │ 陕西省西安市高新区科技路xxx号     ││
│  └──────────────────────────────────┘│
│                                      │
│  ┌─ 应急组织机构 ───────────────────┐│
│  │ 总指挥：张三                      ││
│  │ ...                               ││
│  └──────────────────────────────────┘│
│                                      │
└──────────────────────────────────────┘
```

- Tab 切换：使用 `SegmentedControl` 水平 4 段
- 每个 Tab 内容区为对应 Screen 嵌入（或将详情页拆为 4 个子路由）
- 推荐方案：页面内用 `useState` 追踪 `activeTab`，条件渲染 4 个内容组件，避免 4 个子路由的重定向开销

**风险源 Tab 内容**（→ 嵌入 RiskSourceListScreen）：

### 2.4 RiskSourceListScreen（风险源列表）

**文件**：`mobile/screens/RiskSourceListScreen.tsx`

**路由**：`/m/enterprises/:id/risk-sources`（独立路由，也可嵌入详情页）

**布局**：

```
┌──────────────────────────────────────┐
│ ← 风险源管理            ✨ AI生成    │  ← NavBar: 右侧 sparkles 按钮
├──────────────────────────────────────┤
│  高风险 3 | 中风险 5 | 低风险 2       │  ← 统计条：Chip 行
├──────────────────────────────────────┤
│                                      │
│ ┌─ 🔴 火灾 ────────────────────────┐│  ← RiskSourceItem
│ │ 生产车间A区                       ││     红色圆点 = 高风险
│ │ 管控措施：配备灭火器、烟感报警...  ││     橙色 = 中，黄色 = 低
│ └──────────────────────────────────┘│
│                                      │
│ ┌─ 🟠 触电 ────────────────────────┐│
│ │ 配电室                            ││
│ │ ...                               ││
│ └──────────────────────────────────┘│
│                                      │
│  ┌──────────────────────────────┐    │
│  │ AI 智能分析生成风险源          │    │  ← 引导卡片（无数据时显示）
│  │ 上传或填写企业信息，            │    │
│  │ AI 自动识别潜在风险源          │    │
│  │              [开始生成]        │    │
│  └──────────────────────────────┘    │
│                                      │
│                     [◎]              │  ← FAB: Plus → 新增风险源
└──────────────────────────────────────┘
```

**RiskSourceItem**：

```typescript
interface RiskSourceItemProps {
  riskSource: {
    id: string;
    name: string;
    category: string;
    level: "high" | "medium" | "low";
    location: string;
    mitigation?: string;
  };
  onPress: () => void;
}
```

- 排序：高风险 → 中风险 → 低风险
- 每项：Card 包裹
  - 左侧：8px 圆点（红/橙/黄）
  - 主体：名称（`text-h3`）+ 位置（`text-body-sm` Neutral 600）+ 管控措施（`text-caption` Neutral 400，1 行省略）
  - 右侧：`ChevronRight`

**右滑删除**：左滑 → 红色删除按钮 → 确认 Dialog → `DELETE /api/v1/enterprises/{id}/risk-sources/{rid}`

**FAB**：跳转新增风险源表单（BottomSheet 或新 Screen）

**AI 生成引导**（无数据时）：Card 内有 `Sparkles` 图标 + 引导文案 +「开始生成」按钮 → 弹出 AIGenerationSheet（见 PRD-M06）

---

### 2.5 ResourceListScreen（应急资源列表）

**文件**：`mobile/screens/ResourceListScreen.tsx`

**结构**：与 RiskSourceListScreen 几乎一致：

- 顶部：分类筛选横向滚动 Chip 行：全部 | 消防 | 急救 | 防护 | 通讯 | 照明 | 破拆
- 列表项：ResourceItem（名称 + 数量 + 位置 + 责任人）
- FAB：新增资源
- AI 生成引导（无数据时）

---

### 2.6 RiskAssessmentScreen（风险评估报告）

**文件**：`mobile/screens/RiskAssessmentScreen.tsx`

**路由**：`/m/enterprises/:id/risk-assessment`

**布局**：Markdown 渲染 + 底部操作

- 顶部 NavBar：「风险评估报告」
- 主体：`<div className="prose">` 渲染 Markdown（从 API 获取）
- 底部固定栏：`<Button variant="primary" fullWidth>重新生成</Button>` 或「导出 PDF」（P2）

---

### 2.7 ResourceInvestigationScreen（应急资源调查报告）

**文件**：`mobile/screens/ResourceInvestigationScreen.tsx`

**路由**：`/m/enterprises/:id/resource-investigation`

**布局**：同 RiskAssessmentScreen，标题改为「应急资源调查报告」。

---

### 2.8 EnterpriseEditScreen（编辑企业）

**文件**：`mobile/screens/EnterpriseEditScreen.tsx`

**路由**：`/m/enterprises/:id/edit`

**布局**：复用 `EnterpriseForm`，初始值从 `GET /api/v1/enterprises/{id}` 填充

- 底部固定：「保存」按钮 + 底部「删除企业」红色文字按钮（居中，点击弹出确认 Dialog）
- 删除确认：「确定删除"[企业名]"及其全部关联数据？此操作不可撤销。」→ 「取消」「删除」
- 删除成功 → `navigate("/m/enterprises")` + Toast

---

## 3. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| M04-01 | 企业列表正常渲染 + 搜索过滤 | 自动化 |
| M04-02 | 新建企业 → 表单校验 → 提交成功 → 跳转详情 | 自动化 |
| M04-03 | 企业详情 4 个 Tab 切换 + 内容正确显示 | 自动化 |
| M04-04 | 编辑企业 → 保存 → 数据更新 | 自动化 |
| M04-05 | 删除企业 → 确认 → 删除成功 → 返回列表 | 自动化 |
| M04-06 | 左滑删除企业（列表项） | 手动 |
| M04-07 | 风险源列表按等级排序（高→中→低）+ 色标正确 | 自动化 |
| M04-08 | 风险源新增 → 提交成功 | 自动化 |
| M04-09 | 应急资源分类筛选 Chip 行工作正常 | 手动 |
| M04-10 | 风险评估报告渲染正确 | 自动化 |
| M04-11 | 视觉铁律通过 | 代码审查 |

---

> **下一文档**：PRD-M05 移动端预案编辑器
