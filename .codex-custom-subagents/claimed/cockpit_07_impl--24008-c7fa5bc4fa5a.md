# Codex Custom Subagents task handoff v1

Task: cockpit_07_impl

你正在实现「企业驾驶舱重构」实现计划的 任务 7：模块页外壳 + 左竖分组导航 + 现有 Tab 组件嵌入改造。任务 1-6 已完成并通过双审。

## 工作目录（重要）
C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit
（git worktree，分支 codex/enterprise-cockpit。前端命令用 workdir 进入 frontend 子目录。）

## 任务描述（完整文本）

**文件：**
- 创建：`frontend/src/components/enterprise/cockpit/ModulePageShell.tsx`
- 创建：`frontend/src/components/enterprise/cockpit/ModuleSideNav.tsx`
- 创建：`frontend/src/pages/Enterprise/enterpriseNavConfig.ts`
- 创建：`frontend/src/pages/Enterprise/EnterpriseModulePage.tsx`
- 修改：`frontend/src/pages/Enterprise/RiskManagementTab.tsx`
- 修改：`frontend/src/pages/Hazard/HazardInspectionTab.tsx`

步骤 1：实现外壳与左竖导航

创建 `frontend/src/components/enterprise/cockpit/ModuleSideNav.tsx`：

```tsx
import { useLocation, useNavigate } from "react-router-dom";

export interface SideNavItem {
  key: string;
  label: string;
  to: string;
  matchSearch?: string;
}

export interface SideNavGroup {
  label: string;
  items: SideNavItem[];
}

export default function ModuleSideNav({ groups }: { groups: SideNavGroup[] }) {
  const navigate = useNavigate();
  const location = useLocation();
  return (
    <div
      style={{
        width: 170, flexShrink: 0, background: "#fff", border: "1px solid #e5e9f0",
        borderRadius: 8, padding: "8px 0", alignSelf: "flex-start",
      }}
    >
      {groups.map((g) => (
        <div key={g.label}>
          <div style={{ fontSize: 10, color: "#9aa4b4", padding: "8px 12px 3px", letterSpacing: 1 }}>{g.label}</div>
          {g.items.map((it) => {
            const active = it.matchSearch
              ? location.search.includes(it.matchSearch)
              : location.pathname === it.to;
            return (
              <div
                key={it.key}
                role="button"
                tabIndex={0}
                onClick={() => navigate(it.to)}
                onKeyDown={(e) => e.key === "Enter" && navigate(it.to)}
                style={{
                  fontSize: 12, padding: "7px 12px", cursor: "pointer",
                  color: active ? "#1677ff" : "#5a6a80",
                  background: active ? "#e6f0ff" : "transparent",
                  borderRight: active ? "2px solid #1677ff" : "2px solid transparent",
                  fontWeight: active ? 600 : 400,
                }}
              >
                {it.label}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
```

创建 `frontend/src/components/enterprise/cockpit/ModulePageShell.tsx`：

```tsx
import { useNavigate, useParams, Outlet } from "react-router-dom";
import { Button } from "antd";
import ModuleSideNav, { type SideNavGroup } from "./ModuleSideNav";

interface Props {
  title: string;
  en?: string;
  groups?: (id: string) => SideNavGroup[];
}

export default function ModulePageShell({ title, en, groups }: Props) {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const navGroups = groups?.(id ?? "");
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Button type="link" onClick={() => navigate(`/enterprises/${id}`)}>← 返回企业驾驶舱</Button>
          <span style={{ fontSize: 16, fontWeight: 700 }}>{title}</span>
          {en && <span style={{ fontSize: 9, color: "#8a94a6", letterSpacing: 2 }}>{en}</span>}
        </div>
      </div>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        {navGroups && <ModuleSideNav groups={navGroups} />}
        <div style={{ flex: 1, minWidth: 0 }}>
          <Outlet />
        </div>
      </div>
    </div>
  );
}
```

步骤 2：实现导航分组配置

创建 `frontend/src/pages/Enterprise/enterpriseNavConfig.ts`：

```ts
import type { SideNavGroup } from "@/components/enterprise/cockpit/ModuleSideNav";

export function riskNavGroups(id: string): SideNavGroup[] {
  return [
    {
      label: "数据编辑",
      items: [
        { key: "tree", label: "风险树编辑", to: `/enterprises/${id}/risk-management` },
        { key: "floors", label: "楼层平面图", to: `/enterprises/${id}/risk-management?floor=1`, matchSearch: "floor=1" },
        { key: "methods", label: "评估方法", to: `/enterprises/${id}/risk-management/methods` },
        { key: "dicts", label: "风险与隐患配置", to: `/enterprises/${id}/risk-management/data-dicts` },
      ],
    },
    {
      label: "成果输出",
      items: [
        { key: "overview", label: "可视化总览", to: `/enterprises/${id}/risk-management/overview` },
        { key: "workbench", label: "四色图工作台", to: `/enterprises/${id}/risk-management/workbench` },
        { key: "list", label: "管控清单", to: `/enterprises/${id}/risk-management/control-list` },
        { key: "cards", label: "风险告知卡", to: `/enterprises/${id}/risk-management/notice-cards` },
        { key: "publicity", label: "风险公示", to: `/enterprises/${id}/risk-management/publicity` },
      ],
    },
  ];
}

export function hazardNavGroups(id: string): SideNavGroup[] {
  return [
    {
      label: "排查管理",
      items: [
        { key: "ledger", label: "隐患台账", to: `/enterprises/${id}/hazard` },
        { key: "plans", label: "排查计划", to: `/enterprises/${id}/hazard/plans` },
        { key: "tasks", label: "排查任务", to: `/enterprises/${id}/hazard/tasks` },
        { key: "templates", label: "排查模板", to: `/enterprises/${id}/hazard/templates` },
      ],
    },
    {
      label: "分析公示",
      items: [
        { key: "dashboard", label: "隐患看板", to: `/enterprises/${id}/hazard/dashboard` },
        { key: "publicity", label: "隐患公示", to: `/enterprises/${id}/hazard/publicity` },
      ],
    },
  ];
}
```

步骤 3：改造 RiskManagementTab（embedded + floor 参数）

`frontend/src/pages/Enterprise/RiskManagementTab.tsx` 三处修改：

1. Props 增加可选字段并读取楼层参数。顶部 import 追加 `useSearchParams`（来自 react-router-dom）与 `useEffect`（来自 react），Props 改为：

```tsx
interface Props {
  enterpriseId: string;
  floorPlanUrl?: string | null;
  embedded?: boolean;
}
```

组件内（`const [form, setForm] = useState...` 附近）追加：

```tsx
const [searchParams] = useSearchParams();
useEffect(() => {
  if (searchParams.get("floor") === "1") setFloorDrawerOpen(true);
}, [searchParams]);
```

2. 顶部按钮区（约 349-361 行）：把「可视化总览 / 四色分布图工作台 / 管控清单 / 重大风险公示 / 风险告知卡 / 评估方法 / 风险与隐患配置 / 组织与人员」8 个按钮包进 `{!embedded && (<>...</>)}`，保留「添加分区 / 智能导引 / 楼层管理」：

```tsx
<Button icon={<PlusOutlined />} onClick={() => setForm({ type: "zone", open: true })}>添加分区</Button>
<Button icon={<ThunderboltOutlined />} onClick={() => setSmartGuideOpen(true)}>🚀 智能导引</Button>
<Button icon={<ApartmentOutlined />} onClick={() => setFloorDrawerOpen(true)}>楼层管理</Button>
{!embedded && (
  <>
    <Button icon={<BarChartOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-overview`)}>📊 可视化总览</Button>
    <Button icon={<EditOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-mapping-workbench`)}>四色分布图工作台</Button>
    <Button icon={<UnorderedListOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-control-list`)}>管控清单</Button>
    <Button icon={<NotificationOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-publicity`)}>重大风险公示</Button>
    <Button icon={<ApartmentOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-notice-cards`)}>风险告知卡</Button>
    <Button icon={<SettingOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-methods`)}>⚙ 评估方法</Button>
    <Button icon={<SettingOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/data-dicts`)}>风险与隐患配置</Button>
    <Button icon={<ApartmentOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/org`)}>组织与人员</Button>
  </>
)}
```

3. 其余（FloorManagementDrawer/RiskMigrationWizard/表单弹窗/树渲染）保持不变。

步骤 4：改造 HazardInspectionTab（embedded）

`frontend/src/pages/Hazard/HazardInspectionTab.tsx` 两处修改：

1. Props 增加可选字段：

```tsx
interface Props {
  enterpriseId: string;
  embedded?: boolean;
}
```

2. 按钮区（约 281-299 行）：保留「新增记录 / 导出台账」，把 5 个导航按钮包进 `{!embedded && (<>...</>)}`：

```tsx
<Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>新增记录</Button>
<Button icon={<DownloadOutlined />} loading={exporting} onClick={handleExport}>导出台账</Button>
{!embedded && (
  <>
    <Button icon={<ScheduleOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/hazard/plans`)}>排查计划</Button>
    <Button icon={<CheckSquareOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/hazard/tasks`)}>排查任务</Button>
    <Button icon={<FileTextOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/hazard/templates`)}>排查模板</Button>
    <Button icon={<DashboardOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/hazard/dashboard`)}>隐患看板</Button>
    <Button icon={<EyeOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/hazard/publicity`)}>隐患公示</Button>
  </>
)}
```

注意：若原「导出」按钮文案不是「导出台账」，按文件实际文案保留（只包条件渲染，不改文案）。

步骤 5：实现简单模块通用包装页

创建 `frontend/src/pages/Enterprise/EnterpriseModulePage.tsx`：

```tsx
import { useParams } from "react-router-dom";
import { useNavigate } from "react-router-dom";
import { Spin, Button } from "antd";
import { EditOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/PageHeader";
import { getEnterprise } from "@/services/enterpriseService";
import type { Enterprise } from "@/types/enterprise";
import EnterpriseInfoCards from "@/components/enterprise/EnterpriseInfoCards";
import SurroundingInfoPanel from "@/components/enterprise/SurroundingInfoPanel";
import HazardousChemicalsTab from "@/pages/Enterprise/HazardousChemicalsTab";
import EmergencyResourceForm from "@/components/enterprise/EmergencyResourceForm";
import RiskAssessmentTab from "@/pages/Enterprise/RiskAssessmentTab";
import ResourceInvestigationTab from "@/pages/Enterprise/ResourceInvestigationTab";

type Ctx = { enterpriseId: string; enterprise: Enterprise };

const MODULE_MAP: Record<string, { title: string; en: string; render: (ctx: Ctx) => React.ReactNode }> = {
  info: {
    title: "基本信息", en: "ENTERPRISE ARCHIVE",
    render: ({ enterprise }) => (
      <>
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
          <EditButton />
        </div>
        <EnterpriseInfoCards enterprise={enterprise} readOnly />
      </>
    ),
  },
  surrounding: {
    title: "周边环境", en: "SURROUNDING",
    render: ({ enterpriseId, enterprise }) => (
      <SurroundingInfoPanel
        enterpriseId={enterpriseId}
        surroundingInfo={enterprise.surrounding_info || { nearby_units: [], sensitive_targets: [], traffic_info: "" }}
        onRefresh={() => undefined}
      />
    ),
  },
  chemicals: { title: "危险化学品", en: "CHEMICALS", render: ({ enterpriseId }) => <HazardousChemicalsTab enterpriseId={enterpriseId} /> },
  resources: { title: "应急资源", en: "EMERGENCY RESOURCES", render: ({ enterpriseId }) => <EmergencyResourceForm enterpriseId={enterpriseId} /> },
  assessment: { title: "风险评估报告", en: "RISK ASSESSMENT", render: ({ enterpriseId }) => <RiskAssessmentTab enterpriseId={enterpriseId} /> },
  investigation: { title: "应急资源调查报告", en: "RESOURCE INVESTIGATION", render: ({ enterpriseId }) => <ResourceInvestigationTab enterpriseId={enterpriseId} /> },
};

function EditButton() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  return <Button icon={<EditOutlined />} onClick={() => navigate(`/enterprises/${id}/edit`)}>编辑</Button>;
}

export default function EnterpriseModulePage() {
  const { id, moduleKey = "" } = useParams<{ id: string; moduleKey: string }>();
  const navigate = useNavigate();
  const mod = MODULE_MAP[moduleKey];
  const { data: enterprise, isLoading } = useQuery({
    queryKey: ["enterprise", id],
    queryFn: () => getEnterprise(id!),
    enabled: !!id,
  });

  if (!mod) return <div>模块不存在</div>;
  if (isLoading || !enterprise) return <Spin size="large" />;

  return (
    <div>
      <PageHeader
        title={mod.title}
        subtitle={mod.en}
        onBack={() => navigate(`/enterprises/${id}`)}
      />
      {mod.render({ enterpriseId: id!, enterprise })}
    </div>
  );
}
```

> 注意：`EnterpriseInfoCards`、`SurroundingInfoPanel`、`EmergencyResourceForm`、`HazardousChemicalsTab`、`RiskAssessmentTab`、`ResourceInvestigationTab` 的 props 以现有组件签名为准；若与本任务假设不一致，按现有调用处补齐（例如 EnterpriseInfoCards 可能需要额外字段）。如发现 props 不匹配且无法确定，以 BLOCKED/NEEDS_CONTEXT 上报并说明所见签名。

步骤 6：验证
运行：`cd frontend && npx tsc -b && npx eslint src/components/enterprise/cockpit/ModulePageShell.tsx src/components/enterprise/cockpit/ModuleSideNav.tsx src/pages/Enterprise/enterpriseNavConfig.ts src/pages/Enterprise/EnterpriseModulePage.tsx src/pages/Enterprise/RiskManagementTab.tsx src/pages/Hazard/HazardInspectionTab.tsx`
预期：exit 0

步骤 7：Commit
```bash
git add frontend/src/components/enterprise/cockpit/ModulePageShell.tsx frontend/src/components/enterprise/cockpit/ModuleSideNav.tsx frontend/src/pages/Enterprise/enterpriseNavConfig.ts frontend/src/pages/Enterprise/EnterpriseModulePage.tsx frontend/src/pages/Enterprise/RiskManagementTab.tsx frontend/src/pages/Hazard/HazardInspectionTab.tsx
git commit -m "feat(cockpit): module page shell, side nav and embedded tab components"
```

## 上下文（场景铺设）
- 任务 8 将注册路由：/enterprises/:id/risk-management 与 /enterprises/:id/hazard 作为嵌套路由外壳（ModulePageShell + groups），/enterprises/:id/modules/:moduleKey 渲染 EnterpriseModulePage。本任务只交付组件与改造，不挂路由。
- RiskManagementTab 当前 431 行、HazardInspectionTab 413 行；改造仅加 prop + 条件渲染 + floor 参数，不动内部逻辑。
- 这些组件是浅色现有风格，不引用 cockpit.css。

## 项目规则
- 提交消息遵循 conventional commits；TASKS.md 永不提交；不要修改任务范围外文件；提交前 `git diff --check`。
- 你不是孤立的：同一 worktree 可能有其他会话/代理改动，不要 revert 他人修改；冲突先停下提问。
- 按 AGENTS.md 铁律一，在 TASKS.md 顶部追加「当前状态快照」（不提交）。

## 开始之前
有疑问现在就问，不要猜测。

## 汇报格式
- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 实现内容、验证结果、修改文件清单、commit SHA、自审发现
