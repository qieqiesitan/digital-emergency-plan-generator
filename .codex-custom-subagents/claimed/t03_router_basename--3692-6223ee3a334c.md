# Codex Custom Subagents task handoff v1

Task: t03_router_basename

## 任务：部署可交付性计划任务 3 —— 路由 basename（桌面端 + 移动端）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。不要读计划文件——本任务文件已包含完整任务文本。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness` 的隔离 worktree。启动时 `cd` 到该目录，`git status` 确认工作区干净（TASKS.md 若有未提交改动属正常，不要动它）。前端命令在 `frontend/` 子目录执行。

### 背景

任务 1 已新增 `APP_BASE`（`frontend/src/utils/platform.ts`，从 `import.meta.env.BASE_URL` 派生，开发环境为空串）。本任务给桌面端与移动端 react-router 传 `basename`，使子路径部署时路由自动剥离前缀；开发环境 `APP_BASE` 为空 → `basename: undefined`，行为与现状完全一致。

### 步骤 1：桌面端 routes/index.tsx

文件：`frontend/src/routes/index.tsx`（第 1 行 import 区，第 70-74 行附近 createBrowserRouter 收尾）。

在第 1 行 `import { createBrowserRouter, Navigate } from "react-router-dom";` 之后追加：

```tsx
import { APP_BASE } from "@/utils/platform";
```

将文件末尾 `return createBrowserRouter([ ... ]);` 的收尾（当前为 `],` 后接 `);`）改为：

```tsx
    { path: "/m/*", element: <MobileRedirect /> },
    { path: "*", element: <Navigate to="/dashboard" replace /> },
  ], { basename: APP_BASE || undefined });
}
```

注意：`MobileRedirect`（第 35 行附近 `window.location.replace(window.location.pathname + window.location.search)`）保持不动——其行为不依赖前缀，basename 接管后语义不变。

### 步骤 2：移动端 mobile/routes.tsx

文件：`frontend/src/mobile/routes.tsx`（第 1 行 import 区，第 30 行 `export const mobileRouter = createBrowserRouter([`，文件末尾 `]);`）。

在第 1 行 `import { createBrowserRouter, Navigate } from "react-router-dom";` 之后追加：

```tsx
import { APP_BASE } from "@/utils/platform";
```

将文件末尾的 `]);` 改为：

```tsx
], { basename: APP_BASE || undefined });
```

### 步骤 3：类型检查

```bash
cd frontend
npx tsc -b
```

预期：退出码 0。

### 步骤 4：Commit

```bash
git add frontend/src/routes/index.tsx frontend/src/mobile/routes.tsx
git commit -m "feat(deploy): add router basename for desktop and mobile"
```

### 门禁

1. `npx tsc -b` 退出码 0；
2. `npx eslint frontend/src/routes/index.tsx frontend/src/mobile/routes.tsx` 无新增 error；
3. `git diff --check` 干净；新增行不超 100 字符；
4. `npx vitest run` 全量通过（52）；
5. 提交只含上述 2 个文件，提交消息精确匹配步骤 4。

### 汇报格式

完成后汇报：**状态：** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT；你实现了什么；验证结果；修改的文件；自审发现；任何疑虑。遇到疑问先以 NEEDS_CONTEXT 或 BLOCKED 汇报，不要猜测。
