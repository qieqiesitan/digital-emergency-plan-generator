# Codex Custom Subagents task handoff v1

Task: t02_vite_base_param

## 任务：部署可交付性计划任务 2 —— vite.config.ts 参数化 base 与 PWA manifest

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。不要读计划文件——本任务文件已包含完整任务文本。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness` 的隔离 worktree。启动时 `cd` 到该目录，`git status` 确认工作区干净（TASKS.md 若有未提交改动属正常，不要动它）。前端命令在 `frontend/` 子目录执行。

### 背景

前端要支持部署子路径（如 `/emergency-plan-migration/`），子路径由构建期环境变量 `VITE_BASE_PATH` 决定。默认（不设变量）必须与现状一致：base 为 `/`，PWA start_url 为 `/m/dashboard`。本任务只改 `frontend/vite.config.ts` 一个文件。

### 步骤 1：新增 BASE_PATH 常量

在 `frontend/vite.config.ts` 第 11 行附近 `const API_TARGET = process.env.VITE_API_TARGET || "http://localhost:8000";` 之后追加：

```ts
// 部署子路径（生产如 /emergency-plan-migration，开发为空 → 根路径）
const BASE_PATH = (process.env.VITE_BASE_PATH || "").replace(/\/+$/, "");
```

### 步骤 2：PWA manifest start_url / scope 参数化

在 manifest 中找到 `start_url: "/m/dashboard",` 并改为：

```ts
        start_url: BASE_PATH ? `${BASE_PATH}/m/dashboard` : "/m/dashboard",
        scope: BASE_PATH ? `${BASE_PATH}/` : "/",
```

（在 start_url 行后新增 scope 行；缩进与现有 manifest 字段保持一致。）

### 步骤 3：defineConfig 增加 base

在 `export default defineConfig(async () => ({` 之后的 `plugins: await getPlugins(),` 之前插入：

```ts
  base: BASE_PATH ? `${BASE_PATH}/` : "/",
```

### 步骤 4：类型检查

```bash
cd frontend
npx tsc -b
```

预期：退出码 0。

### 步骤 5：Commit

```bash
git add frontend/vite.config.ts
git commit -m "feat(deploy): parameterize vite base and PWA manifest via VITE_BASE_PATH"
```

### 门禁

1. `npx tsc -b` 退出码 0；
2. `npx eslint frontend/vite.config.ts` 无新增 error；
3. `git diff --check` 干净；新增行不超 100 字符；
4. 提交只含 `frontend/vite.config.ts`，提交消息精确匹配步骤 5；
5. 不设 `VITE_BASE_PATH` 时 `base` 必须仍为 `/`（可通过 `npx vite build` 后检查 `dist/index.html` 资源引用无前缀验证；也可用 `npx vitest run` 确认未破坏现有测试）。

### 汇报格式

完成后汇报：**状态：** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT；你实现了什么；验证结果；修改的文件；自审发现；任何疑虑。遇到疑问先以 NEEDS_CONTEXT 或 BLOCKED 汇报，不要猜测。
