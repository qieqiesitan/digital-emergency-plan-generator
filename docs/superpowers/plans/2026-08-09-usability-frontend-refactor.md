# 易用性整体优化 · 计划 C2（信息架构与创建流程重构）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 完成信息架构重构与创建流程改造——企业页面卡片化与 tab 分组、企业列表完成度列、专业模式开关、预案双列表合并、创建流程两步化、样章确认、编辑器增强。

**架构：** 复用计划 C1 的 `EnterpriseInfoCards`；`MainLayout` 增加专业模式开关（localStorage 记忆 + 权限可见）；`PlanCardsPage` 页内 Segmented 切换卡片/列表；`PlanCreatePage` 精简为两步；`PlanEditorPage` 支持 `auto_generate=sample` 样章确认。

**技术栈：** React + Ant Design + TypeScript。

**规格依据：** `docs/superpowers/specs/2026-08-08-usability-enhancement-design.md` 第 5、8、8.1 节。

**依赖：** 先执行计划 A、C1。

---

## 文件结构

| 文件 | 职责 | 动作 |
|------|------|------|
| `frontend/src/pages/Enterprise/EnterpriseCreatePage.tsx` | 卡片化创建 | 修改 |
| `frontend/src/pages/Enterprise/EnterpriseEditPage.tsx` | 卡片化编辑 | 修改 |
| `frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx` | tab 分组 + 基本信息卡片 | 修改 |
| `frontend/src/pages/Enterprise/EnterpriseListPage.tsx` | 完成度列 | 修改 |
| `frontend/src/layouts/MainLayout.tsx` | 专业模式开关 | 修改 |
| `frontend/src/pages/Plan/PlanCardsPage.tsx` | 卡片/列表视图切换 | 修改 |
| `frontend/src/pages/Plan/PlanCreatePage.tsx` | 两步创建 | 修改 |
| `frontend/src/pages/Plan/PlanEditorPage.tsx` | 样章确认 + 质量提示条 | 修改 |
| `frontend/src/components/plan/SectionTree.tsx` | 章节树图例 | 修改 |
| `frontend/src/routes/index.tsx` | 移除 `/plans/all` | 修改 |

---

### 任务 C2-1：企业页面卡片化（创建/编辑/详情/列表）

**文件：**
- 修改：`frontend/src/pages/Enterprise/EnterpriseCreatePage.tsx`
- 修改：`frontend/src/pages/Enterprise/EnterpriseEditPage.tsx`
- 修改：`frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx`
- 修改：`frontend/src/pages/Enterprise/EnterpriseListPage.tsx`

- [ ] **步骤 1：创建页卡片化**

`EnterpriseCreatePage.tsx` 重写主体：保留 `createEnterprise` mutation 与企查查自动填充能力（迁移到 `EnterpriseInfoCards` 内部），页面骨架：

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
    onError: (err: any) => message.error(err?.response?.data?.detail || "创建失败"),
  });
  return (
    <div style={{ maxWidth: 720 }}>
      <PageHeader title="新建企业" onBack={() => navigate("/enterprises")} />
      <EnterpriseInfoCards onCreate={async (values) => mutation.mutate(values as any)} />
    </div>
  );
}
```

- [ ] **步骤 2：编辑页卡片化**

`EnterpriseEditPage.tsx` 重写主体：查询企业后传 `enterprise` 给 `EnterpriseInfoCards`，`onSaved` 调 `updateEnterprise` 后返回详情页。

```tsx
export default function EnterpriseEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: enterprise } = useQuery({ queryKey: ["enterprise", id], queryFn: () => getEnterprise(id!), enabled: !!id });
  const mutation = useMutation({
    mutationFn: (values: Record<string, unknown>) => updateEnterprise(id!, values as any),
    onSuccess: () => { message.success("保存成功"); queryClient.invalidateQueries({ queryKey: ["enterprise", id] }); navigate(`/enterprises/${id}`); },
    onError: (err: any) => message.error(err?.response?.data?.detail || "保存失败"),
  });
  return (
    <div style={{ maxWidth: 720 }}>
      <PageHeader title="编辑企业" onBack={() => navigate(`/enterprises/${id}`)} />
      <EnterpriseInfoCards enterprise={enterprise} onSaved={async (values) => mutation.mutate(values)} />
    </div>
  );
}
```

- [ ] **步骤 3：企业详情 tab 分组（虚线分隔 + 徽标）+ 基本信息卡片**

`EnterpriseDetailPage.tsx`：

1. 基本信息 tab 的 children 替换为只读卡片：

```tsx
children: (
  <EnterpriseInfoCards enterprise={enterprise} readOnly />
)
```

（导入 `EnterpriseInfoCards`；原 Descriptions 区块移除，GIS/平面图区块保留在卡片下方。）

2. tab 分组：把 tabItems 拆成两组渲染。`Tabs items` 支持分组标题（`type: "group"`）：

```tsx
const groupLabel = (label: React.ReactNode) => ({ type: "group" as const, label });

const tabItems = [
  groupLabel("数据录入"),
  { key: "info", label: "基本信息", children: ... },
  { key: "org", label: <span>组织架构 <Badge count={orgGroups.length} /></span>, children: ... },
  { key: "resources", label: <span>应急资源 <Badge count={enterprise.resources_count} /></span>, children: ... },
  { key: "surrounding", label: "周边环境", children: ... },
  { key: "chemicals", label: "危险化学品", children: ... },
  { key: "risk-management", label: "风险分级管控", children: ... },
  groupLabel("报告生成"),
  {
    key: "risk-assessment",
    label: (
      <span>
        风险评估
        <span style={{ marginLeft: 6, fontSize: 11, padding: "0 6px", borderRadius: 8, background: "#fff7e6", color: "#fa8c16" }}>
          未生成
        </span>
      </span>
    ),
    children: <RiskAssessmentTab enterpriseId={id!} />,
  },
  {
    key: "resource-investigation",
    label: (
      <span>
        应急资源调查
        <span style={{ marginLeft: 6, fontSize: 11, padding: "0 6px", borderRadius: 8, background: "#f6ffed", color: "#52c41a" }}>
          已完成
        </span>
      </span>
    ),
    children: <ResourceInvestigationTab enterpriseId={id!} />,
  },
];
```

报告徽标状态从报告查询结果动态生成（`useQuery` 获取 `getRiskAssessment` / `getResourceInvestigation` 的 `status`，映射 未生成/生成中/已完成 三种徽标颜色：橙/蓝/绿）。

3. Ant Design `Tabs` 对 `items` 中 `type: "group"` 的项渲染为分组标题；如需完全虚线分隔效果，给分组项设置自定义样式（`style: { borderTop: "1px dashed #e5e5e5" }`）。

- [ ] **步骤 4：企业列表完成度列**

`EnterpriseListPage.tsx` columns 增加：

```tsx
{
  title: "数据完成度",
  key: "completion",
  width: 140,
  render: (_: unknown, record: any) => {
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

（`Enterprise` 类型增加可选 `completion?: { percent: number; modules: unknown[] }`。）

- [ ] **步骤 5：tsc 验证并 Commit**

运行：`cd frontend && npx tsc --noEmit`

预期：无类型错误。

```bash
git add frontend/src/pages/Enterprise/EnterpriseCreatePage.tsx frontend/src/pages/Enterprise/EnterpriseEditPage.tsx frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx frontend/src/pages/Enterprise/EnterpriseListPage.tsx frontend/src/types/enterprise.ts
git commit -m "feat(enterprise): card-based forms, tab grouping with report badges, completion column"
```

---

### 任务 C2-2：专业模式开关

**文件：**
- 修改：`frontend/src/layouts/MainLayout.tsx`

- [ ] **步骤 1：实现专业模式开关**

`MainLayout.tsx`：

1. state + 持久化：

```tsx
const [proMode, setProMode] = useState(() => localStorage.getItem("pro_mode") === "1");
const togglePro = () => {
  setProMode(v => {
    localStorage.setItem("pro_mode", v ? "0" : "1");
    return !v;
  });
};
```

2. 普通菜单与专业菜单拆分：`menuItems` 中「系统管理 / AI 管理 / 法规库管理 / 风险方法」等管理项只在 `proMode && hasMenu(...)` 时渲染（风险方法入口属于企业详情内部，此处指侧边栏管理项）。

3. 顶部（企业切换旁）开关，仅对有权限用户显示：

```tsx
{(showSystemGroup || showAIGroup) && (
  <Button size="small" onClick={togglePro}>
    {proMode ? "专业模式 开" : "专业模式 关"}
  </Button>
)}
```

（普通用户无管理权限时不显示开关；`proMode` 为 false 时隐藏管理分组。）

- [ ] **步骤 2：tsc 验证并 Commit**

运行：`cd frontend && npx tsc --noEmit`

预期：无类型错误。

```bash
git add frontend/src/layouts/MainLayout.tsx
git commit -m "feat(layout): professional mode toggle to expand management menus"
```

---

### 任务 C2-3：预案双列表合并 + 创建流程两步化

**文件：**
- 修改：`frontend/src/pages/Plan/PlanCardsPage.tsx`
- 修改：`frontend/src/pages/Plan/PlanCreatePage.tsx`
- 修改：`frontend/src/routes/index.tsx`

- [ ] **步骤 1：PlanCardsPage 卡片/列表视图切换**

`PlanCardsPage.tsx`：

1. 顶部增加 Segmented：

```tsx
const [view, setView] = useState<"cards" | "list">("cards");
...
<Space style={{ marginBottom: 16 }}>
  <Segmented
    options={[{ label: "卡片视图", value: "cards" }, { label: "列表视图", value: "list" }]}
    value={view}
    onChange={(v) => setView(v as "cards" | "list")}
  />
  <Input prefix={<SearchOutlined />} placeholder="搜索企业名称" allowClear style={{ width: 240 }} value={search} onChange={(e) => setSearch(e.target.value)} />
  <Select placeholder="行业筛选" allowClear style={{ width: 160 }} value={industry} onChange={setIndustry} options={[...PRESET_INDUSTRIES].map(i => ({ value: i, label: i }))} />
</Space>
```

2. 移除「全部预案列表」按钮；`view === "list"` 时渲染列表表格（复用 `listPlans` 数据，列：预案标题/所属企业/类型/完成度/更新时间/操作）：

```tsx
{view === "list" ? (
  <PlanListEmbedded enterpriseId={undefined} />
) : (
  <Row gutter={[16, 16]}>...原卡片...</Row>
)}
```

`PlanListEmbedded` 复用 `PlanListPage` 的表格逻辑（抽成可复用组件或在 PlanCardsPage 内联简单表格）。

- [ ] **步骤 2：路由移除 `/plans/all`**

`frontend/src/routes/index.tsx` 删除 `{ path: "/plans/all", element: <PlanListPage /> }`（`/enterprises/:enterprise_id/plans` 保留）。

- [ ] **步骤 3：PlanCreatePage 两步化**

`PlanCreatePage.tsx` 精简为两步（选类型 → 确认信息），删除「事故类型单独步（并入确认信息）/创作风格/编号版本号」：

```tsx
const steps = [
  { title: "选择类型" },
  { title: "确认信息" },
];
```

- 第 1 步：三种类型卡片（保留现有类型选择 UI）。
- 第 2 步：显示企业/类型/标题（默认生成、可改）+ 专项事故类型下拉 + 创建按钮。
- 创建成功后跳转改为：

```tsx
navigate(`/plans/${data.id}/edit?auto_generate=sample`);
```

- [ ] **步骤 4：tsc 验证并 Commit**

运行：`cd frontend && npx tsc --noEmit`

预期：无类型错误。

```bash
git add frontend/src/pages/Plan/PlanCardsPage.tsx frontend/src/pages/Plan/PlanCreatePage.tsx frontend/src/routes/index.tsx
git commit -m "refactor(plan): merge plan list views, slim create flow to two steps"
```

---

### 任务 C2-4：样章确认 + 编辑器增强

**文件：**
- 修改：`frontend/src/pages/Plan/PlanEditorPage.tsx`
- 修改：`frontend/src/components/plan/SectionTree.tsx`

- [ ] **步骤 1：样章确认（auto_generate=sample）**

`PlanEditorPage.tsx`：

1. 读取 `auto_generate` 参数区分模式：

```tsx
const autoGenerate = searchParams.get("auto_generate"); // "1" 全量（旧） | "sample" 样章
```

2. `sample` 模式：只生成第一章（`sections[0].section_key`），生成完成后进入「样章确认」状态：

```tsx
const [sampleMode, setSampleMode] = useState(autoGenerate === "sample");
const [sampleDone, setSampleDone] = useState(false);

// 在 autoGenerate === "sample" 时，startRealtimeGeneration([sections[0].section_key]) 并 setSampleDone(true)
```

3. 样章确认横幅（`sampleDone && sampleMode`）：

```tsx
{sampleDone && sampleMode && (
  <div style={{ border: "1px solid #1677ff", borderRadius: 8, padding: 12, marginBottom: 12, background: "#f0f7ff" }}>
    <div style={{ fontWeight: 600, marginBottom: 4 }}>样章已生成（第一章）——先看风格和内容</div>
    <div style={{ fontSize: 13, color: "#555", marginBottom: 8 }}>满意后生成全部章节；不满意可换风格重新生成样章</div>
    <Space>
      <Button onClick={() => { setSampleMode(false); startRealtimeGeneration(); }} type="primary">满意，生成全部章节</Button>
      <Button onClick={() => startRealtimeGeneration([sections[0].section_key])}>换风格重新生成样章</Button>
    </Space>
  </div>
)}
```

4. `auto_generate=1`（旧全量模式）逻辑保留兼容；`sample` 不自动全量。

- [ ] **步骤 2：质量提示条（编辑页顶部）**

`PlanEditorPage.tsx` 增加查询与提示（复用 `validateExport`）：

```tsx
const { data: validation } = useQuery({
  queryKey: ["exportValidate", id],
  queryFn: () => validateExport(id!),
  enabled: !!id && !isGenerating,
});

{validation && !validation.valid && (
  <Alert
    type="warning" showIcon style={{ marginBottom: 12 }}
    message="⚠ 部分章节可能未覆盖完整要点"
    description={validation.issues.slice(0, 3).map((i: any) => `「${i.section_title}」${i.issue}`).join("；")}
    action={<Button size="small" onClick={() => message.info("可在导出预览页查看全部校验结果")}>查看要点清单</Button>}
  />
)}
```

- [ ] **步骤 3：章节树图例**

`SectionTree.tsx` 返回的 `<Tree>` 后追加图例：

```tsx
<div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px dashed #eee", fontSize: 12, color: "#666", lineHeight: 1.8 }}>
  <b>图例</b><br />
  ✓ 已完成 · ! 必填未完成 · ⏳ 生成中 · 🤖 可 AI 生成
  <div style={{ color: "#999", fontSize: 11 }}>必填章节为空时导出会被拦截</div>
</div>
```

- [ ] **步骤 4：tsc 验证并 Commit**

运行：`cd frontend && npx tsc --noEmit`

预期：无类型错误。

```bash
git add frontend/src/pages/Plan/PlanEditorPage.tsx frontend/src/components/plan/SectionTree.tsx
git commit -m "feat(plan): sample confirmation flow, quality hint bar and section tree legend"
```

---

## 计划 C2 自检

**规格覆盖度：** 第 5 节企业页面卡片化/tab 分组/完成度列/AI 助手入口（计划 A 已完成菜单移除）→ C2-1；第 4 节专业模式 → C2-2；第 5 节预案双列表合并 → C2-3；第 8 节创建流程两步化与样章确认 → C2-3/C2-4；第 8.1 节质量提示条与图例 → C2-4。无遗漏。

**占位符扫描：** 无 TODO/待定；`PlanListEmbedded` 抽组件说明明确。

**类型一致性：** `auto_generate` 参数在 PlanCreatePage（跳转）与 PlanEditorPage（读取）一致；`validation` 复用 `validateExport` 返回结构；`completion.percent` 在列表与类型中一致。
