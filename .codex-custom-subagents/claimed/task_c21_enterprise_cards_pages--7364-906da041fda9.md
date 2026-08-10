# Codex Custom Subagents task handoff v1

Task: task_c21_enterprise_cards_pages

## 任务：企业页面卡片化（创建/编辑/详情 tab 分组/列表完成度列）——易用性优化计划 C2 任务 C2-1

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 C1-6 提交（174d400）。启动时 `cd` 到该目录，git status 确认干净。

### 背景

- `EnterpriseInfoCards` 组件已就绪（C1-2，含 onSaved/onCreate/readOnly）。
- 本任务：企业创建页/编辑页改为卡片化、企业详情 tab 分组（数据录入/报告生成）+ 基本信息卡片、企业列表加「数据完成度」列。

### 步骤 1：创建页卡片化

`frontend/src/pages/Enterprise/EnterpriseCreatePage.tsx` 重写为：

```tsx
import { useNavigate } from "react-router-dom";
import { Button, message } from "antd";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createEnterprise } from "@/services/enterpriseService";
import { PageHeader } from "@/components/common/PageHeader";
import EnterpriseInfoCards from "@/components/enterprise/EnterpriseInfoCards";

export default function EnterpriseCreatePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: createEnterprise,
    onSuccess: (data) => {
      message.success("企业创建成功");
      queryClient.invalidateQueries({ queryKey: ["enterprises"] });
      navigate(`/enterprises/${data.id}`);
    },
    onError: (err: unknown) => message.error(extractDetail(err) || "创建失败"),
  });
  return (
    <div style={{ maxWidth: 720 }}>
      <PageHeader title="新建企业" onBack={() => navigate("/enterprises")} />
      <EnterpriseInfoCards onCreate={async (values) => mutation.mutate(values as never)} />
    </div>
  );
}
```

（`extractDetail` 用 axios.isAxiosError 取 response.data.detail；`values as never` 避免 any——或按 EnterpriseCreate 类型转换。）

### 步骤 2：编辑页卡片化

`frontend/src/pages/Enterprise/EnterpriseEditPage.tsx` 重写：查询企业 → `EnterpriseInfoCards enterprise={enterprise}` → `onSaved` 调 `updateEnterprise` 后返回详情页：

```tsx
export default function EnterpriseEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: enterprise } = useQuery({
    queryKey: ["enterprise", id],
    queryFn: () => getEnterprise(id!),
    enabled: !!id,
  });
  const mutation = useMutation({
    mutationFn: (values: Record<string, unknown>) => updateEnterprise(id!, values as never),
    onSuccess: () => {
      message.success("保存成功");
      queryClient.invalidateQueries({ queryKey: ["enterprise", id] });
      navigate(`/enterprises/${id}`);
    },
    onError: (err: unknown) => message.error(extractDetail(err) || "保存失败"),
  });
  return (
    <div style={{ maxWidth: 720 }}>
      <PageHeader title="编辑企业" onBack={() => navigate(`/enterprises/${id}`)} />
      <EnterpriseInfoCards enterprise={enterprise} onSaved={async (values) => mutation.mutate(values)} />
    </div>
  );
}
```

### 步骤 3：企业详情 tab 分组 + 基本信息卡片

`frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx`：

1. 基本信息 tab 的 children 替换为 `<EnterpriseInfoCards enterprise={enterprise} readOnly />`（保留 GIS/平面图区块在卡片下方）。
2. tab 分组：用 `items` 中 `type: "group"` 项（Ant Design Tabs 支持分组标题）：

```tsx
const groupLabel = (label: string) => ({ type: "group" as const, label });

const tabItems = [
  groupLabel("数据录入"),
  { key: "info", label: "基本信息", children: <EnterpriseInfoCards enterprise={enterprise} readOnly /> },
  { key: "org", label: <span>组织架构 <Badge count={orgGroups.length} /></span>, children: ... },
  { key: "resources", label: <span>应急资源 <Badge count={enterprise.resources_count} /></span>, children: ... },
  { key: "surrounding", label: "周边环境", children: ... },
  { key: "chemicals", label: "危险化学品", children: ... },
  { key: "risk-management", label: "风险分级管控", children: ... },
  groupLabel("报告生成"),
  { key: "risk-assessment", label: 报告徽标("风险评估", raStatus), children: <RiskAssessmentTab enterpriseId={id!} /> },
  { key: "resource-investigation", label: 报告徽标("应急资源调查", riStatus), children: <ResourceInvestigationTab enterpriseId={id!} /> },
];
```

3. 报告徽标：`useQuery` 获取 `getRiskAssessment` / `getResourceInvestigation` 的 status，映射 未生成（橙）/生成中（蓝）/已完成（绿）徽标；`type: "group"` 项加 `style: { borderTop: "1px dashed #e5e5e5" }` 呈现虚线分隔。

（先读 EnterpriseDetailPage 现状与 riskAssessmentService/resourceInvestigationService 的 get 方法确认 status 字段；Ant Design Tabs items 支持 type: "group"——若当前 antd 版本不支持 group 项，用「报告生成」分组标题的等价方案（如自定义 label + 分隔样式），保持分组视觉。）

### 步骤 4：企业列表完成度列

`frontend/src/pages/Enterprise/EnterpriseListPage.tsx` columns 增加：

```tsx
{
  title: "数据完成度",
  key: "completion",
  width: 140,
  render: (_: unknown, record: Enterprise) => {
    const pct = record.completion?.percent ?? 0;
    const color = pct >= 80 ? "#52c41a" : pct >= 40 ? "#1677ff" : "#fa8c16";
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <div style={{ flex: 1, height: 6, background: "#eee", borderRadius: 3, overflow: "hidden" }}>
          <div style={{ width: `${pct}%`, height: "100%", background: color }} />
        </div>
        <span style={{ color: "#666", whiteSpace: "nowrap" }}>{pct}%</span>
      </div>
    );
  },
},
```

（`Enterprise` 类型增加可选 `completion?: { percent: number; modules: unknown[] }`——先读 types/enterprise.ts 确认是否已有。）

### 步骤 5：tsc + eslint 验证

运行：`cd frontend && npx tsc -p tsconfig.app.json --noEmit`

再运行：`cd frontend && npx eslint src/pages/Enterprise/`

预期：无类型/ESLint 错误（无 no-explicit-any）。

### 步骤 6：Commit

```bash
git add frontend/src/pages/Enterprise/ frontend/src/types/enterprise.ts
git commit -m "feat(enterprise): card-based forms, tab grouping with report badges, completion column"
```

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 先读四个页面现状 + types/enterprise.ts + 报告 service
2. 按步骤实现
3. tsc + eslint 验证
4. 提交
5. 自审：创建/编辑卡片化可用？详情 tab 分组 + 徽标正确？列表完成度列显示？无 any？
6. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、tsc/eslint 结果、提交 SHA、自审发现
