# Codex Custom Subagents task handoff v1

Task: task_d1_mobile_completion

## 任务：移动端完成度卡片（易用性优化计划 D 任务 D-1）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 C2-4 提交（e154e37）。启动时 `cd` 到该目录，git status 确认干净。

### 背景

- 移动端 `frontend/src/mobile/screens/DashboardScreen.tsx`（@ts-nocheck，工作台首页）。
- 移动端不做完整引导页；首页加完成度卡片 + 各模块「去补 XX」直达入口。
- 后端 `GET /enterprises/{id}/completion` 已就绪；前端 `onboardingService.getEnterpriseCompletion` 已就绪。

### 步骤 1：DashboardScreen 完成度卡片

`frontend/src/mobile/screens/DashboardScreen.tsx`：

1. 引入查询：

```tsx
import { getEnterpriseCompletion } from "@/services/onboardingService";

const completionQuery = useQuery({
  queryKey: ["completion", activeEnterpriseId],
  queryFn: () => getEnterpriseCompletion(activeEnterpriseId!),
  enabled: !!activeEnterpriseId,
});
```

2. 在统计卡之前渲染完成度卡片（移动端样式，参考桌面 CompletionCard 但用移动端 UI 组件/内联样式）：

```tsx
{completionQuery.data && (
  <div className="mx-md mt-md" style={{ border: "1px solid #1677ff", borderRadius: 10, padding: 12, background: "#f0f7ff" }}>
    <p className="text-body font-semibold">企业数据完成度 {completionQuery.data.percent}%</p>
    <div style={{ height: 6, background: "#d9d9d9", borderRadius: 3, overflow: "hidden", marginBottom: 8 }}>
      <div style={{ width: `${completionQuery.data.percent}%`, height: "100%", background: "#1677ff" }} />
    </div>
    <div className="flex flex-wrap gap-xs mb-sm">
      {completionQuery.data.modules
        .filter((m) => !m.done)
        .map((m) => (
          <span key={m.key} style={{ fontSize: 11, background: "#fff7e6", border: "1px solid #ffe7ba", borderRadius: 4, padding: "1px 6px" }}>
            {m.label}
          </span>
        ))}
    </div>
    <button className="bg-primary-500 text-white rounded-md px-sm py-xs text-body-sm" onClick={...}>
      去补数据 / 直达入口
    </button>
  </div>
)}
```

3. 「去补数据」按钮跳转：未完成模块存在时跳企业详情页（`/m/enterprises/${activeEnterpriseId}`）或各模块路由；全部完成时跳 `/m/plans/new?enterprise_id=...`（若移动端有该路由）。按移动端实际路由选择（可先跳企业详情，各模块直达由后续迭代细化）。

（先读 DashboardScreen.tsx 现状确认 activeEnterpriseId 来源与渲染结构；`useQuery` 需从 @tanstack/react-query 导入——检查现有导入。）

### 步骤 2：tsc + eslint 验证

运行：`cd frontend && npx tsc -p tsconfig.app.json --noEmit`

再运行：`cd frontend && npx eslint src/mobile/screens/DashboardScreen.tsx`

预期：无类型/ESLint 错误（无 no-explicit-any；DashboardScreen 是 @ts-nocheck，但避免新增显式 any）。

### 步骤 3：Commit

```bash
git add frontend/src/mobile/screens/DashboardScreen.tsx
git commit -m "feat(mobile): completion card on dashboard with module shortcuts"
```

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 先读 DashboardScreen.tsx 现状（activeEnterpriseId 来源、useQuery 导入、统计卡位置）
2. 按步骤实现
3. tsc + eslint 验证
4. 提交
5. 自审：完成度卡片显示/进度条/未完成模块？去补数据跳转？无 any？
6. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、tsc/eslint 结果、提交 SHA、自审发现
