# Codex Custom Subagents task handoff v1

Task: task_c23_plan_list_create

## 任务：预案双列表合并 + 创建流程两步化（易用性优化计划 C2 任务 C2-3）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 C2-2 提交（710a156）。启动时 `cd` 到该目录，git status 确认干净。

### 背景

- `PlanCardsPage`（预案总览，按企业卡片）+ `PlanListPage`（表格列表）双入口并存。
- `PlanCreatePage` 5 步向导（选类型/事故类型/填写信息/创作风格/确认创建 + 编号版本号）。
- 本任务：PlanCardsPage 加 Segmented「卡片/列表」视图切换（移除「全部预案列表」按钮）、路由移除 `/plans/all`、PlanCreatePage 精简为两步（选类型 → 确认信息），创建后跳 `auto_generate=sample`。

### 步骤 1：PlanCardsPage 视图切换

`frontend/src/pages/Plan/PlanCardsPage.tsx`：

1. 顶部 Segmented：

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
  <PlanListTable />
) : (
  <Row gutter={[16, 16]}>...原卡片...</Row>
)}
```

`PlanListTable`：页面内简单表格组件（可用 `useQuery` + `listPlans`，列含标题/企业/类型标签/完成度/更新时间/编辑跳转）；或复用 `PlanListPage` 的表格逻辑（若可抽取）。

### 步骤 2：路由移除 /plans/all

`frontend/src/routes/index.tsx` 删除 `{ path: "/plans/all", element: <PlanListPage /> }`（`/enterprises/:enterprise_id/plans` 保留）。

### 步骤 3：PlanCreatePage 两步化

`frontend/src/pages/Plan/PlanCreatePage.tsx` 精简为两步（选类型 → 确认信息），删除「事故类型单独步（并入确认信息）/创作风格/编号版本号」：

```tsx
const steps = [
  { title: "选择类型" },
  { title: "确认信息" },
];
```

- 第 1 步：三种类型卡片（保留现有类型选择 UI）。
- 第 2 步：显示企业/类型/标题（默认生成、可改）+ 专项事故类型下拉 + 创建按钮（无编号/版本号输入、无风格面板）。
- 创建成功跳转改为：

```tsx
navigate(`/plans/${data.id}/edit?auto_generate=sample`);
```

### 步骤 4：tsc + eslint 验证

运行：`cd frontend && npx tsc -p tsconfig.app.json --noEmit`

再运行：`cd frontend && npx eslint src/pages/Plan/ src/routes/index.tsx`

预期：无类型/ESLint 错误（无 no-explicit-any；新增代码行 ≤100）。

### 步骤 5：Commit

```bash
git add frontend/src/pages/Plan/ frontend/src/routes/index.tsx
git commit -m "refactor(plan): merge plan list views, slim create flow to two steps"
```

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 先读 PlanCardsPage / PlanListPage / PlanCreatePage / routes 现状
2. 按步骤实现
3. tsc + eslint 验证
4. 提交
5. 自审：Segmented 切换可用？/plans/all 移除无残留？两步创建 + auto_generate=sample？无 any？
6. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、tsc/eslint 结果、提交 SHA、自审发现
