# Codex Custom Subagents task handoff v1

Task: task_c11_types_service_route

## 任务：引导页类型 + 服务封装 + 路由（易用性优化计划 C1 任务 C1-1）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含后端全部提交（382ce76）。启动时 `cd` 到该目录，git status 确认干净。

### 步骤 1：新增类型与服务

新建 `frontend/src/types/onboarding.ts`：

```ts
export interface CompletionModule {
  key: string;
  label: string;
  weight: number;
  done: boolean;
}

export interface CompletionResult {
  percent: number;
  modules: CompletionModule[];
}

export interface CandidateItem {
  _key: string;
  source?: string;
  [key: string]: unknown;
}
```

新建 `frontend/src/services/onboardingService.ts`：

```ts
import api from "./api";
import type { CompletionResult } from "@/types/onboarding";

export function getEnterpriseCompletion(enterpriseId: string): Promise<CompletionResult> {
  return api.get(`/enterprises/${enterpriseId}/completion`).then(r => r.data.data);
}

export function importOnboardingFile(enterpriseId: string, module: string, file: File): Promise<{ module: string; candidates: unknown[]; source: string }> {
  const form = new FormData();
  form.append("module", module);
  form.append("file", file);
  return api.post(`/onboarding/import`, form).then(r => r.data.data);
}

export function importOnboardingBatch(enterpriseId: string, files: File[]): Promise<{ module: string; candidates: unknown[]; source: string }[]> {
  const form = new FormData();
  files.forEach(f => form.append("files", f));
  return api.post(`/onboarding/import/batch`, form).then(r => r.data.data);
}
```

（enterpriseId 参数保留供后续使用；若 api.ts 已处理 /api/v1 前缀则路径按现有约定。）

### 步骤 2：创建 OnboardingPage 最小占位 + 挂载路由

新建 `frontend/src/pages/Onboarding/OnboardingPage.tsx`：

```tsx
export default function OnboardingPage() {
  return <div>引导页开发中</div>;
}
```

在 `frontend/src/routes/index.tsx` 的 `contentRoutes` 增加：

```tsx
import OnboardingPage from "@/pages/Onboarding/OnboardingPage";
...
{ path: "/onboarding", element: <OnboardingPage /> },
```

### 步骤 3：tsc 验证

运行：`cd frontend && npx tsc -p tsconfig.app.json --noEmit`

预期：无类型错误。

### 步骤 4：Commit

```bash
git add frontend/src/types/onboarding.ts frontend/src/services/onboardingService.ts frontend/src/pages/Onboarding/OnboardingPage.tsx frontend/src/routes/index.tsx
git commit -m "feat(onboarding): types, service and route scaffolding"
```

## 上下文

- 后端接口已就绪：GET /enterprises/{id}/completion、POST /onboarding/import、POST /onboarding/import/batch、POST /onboarding/candidates。
- 项目前端：React + TS + TanStack Query；services 目录按模块封装；routes/index.tsx 集中管理桌面路由。
- 不要改动其它文件；若 tsc 报既有无关错误，记录并说明。

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 严格按任务描述实现
2. tsc 验证
3. 提交
4. 自审：类型/服务/路由可用？api 路径与后端一致？
5. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、tsc 结果、提交 SHA、自审发现
