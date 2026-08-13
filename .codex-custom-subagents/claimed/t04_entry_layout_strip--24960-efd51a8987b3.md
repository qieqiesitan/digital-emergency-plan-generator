# Codex Custom Subagents task handoff v1

Task: t04_entry_layout_strip

## 任务：部署可交付性计划任务 4 —— 入口与布局剥前缀

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。不要读计划文件——本任务文件已包含完整任务文本。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness` 的隔离 worktree。启动时 `cd` 到该目录，`git status` 确认工作区干净（TASKS.md 若有未提交改动属正常，不要动它）。前端命令在 `frontend/` 子目录执行。

### 背景

任务 1 已新增 `stripAppBase`（`frontend/src/utils/platform.ts`）。子路径部署时浏览器 `pathname` 带前缀（如 `/emergency-plan-migration/m/login`），本任务让移动端入口判断、桌面菜单选中、移动端 Tab 显示/高亮统一剥前缀。开发环境 `APP_BASE` 为空 → `stripAppBase` 原样返回，行为与现状完全一致。

### 步骤 1：entry.tsx

文件：`frontend/src/entry.tsx`。

在第 1 行 `import { isMobile } from "@/mobile/utils/platform";` 之后追加：

```tsx
import { stripAppBase } from "@/utils/platform";
```

将 `isMobilePath` 函数（当前第 5-8 行附近）改为：

```tsx
function isMobilePath(): boolean {
  const p = stripAppBase(window.location.pathname);
  return p === "/m" || p.startsWith("/m/");
}
```

### 步骤 2：main.tsx

文件：`frontend/src/main.tsx`。同样在第 1 行后追加 `import { stripAppBase } from "@/utils/platform";`，并将 `isMobilePath` 改为与步骤 1 相同实现。

### 步骤 3：MainLayout.tsx

文件：`frontend/src/layouts/MainLayout.tsx`。

在文件顶部 import 区追加：

```tsx
import { stripAppBase } from "@/utils/platform";
```

将第 155 行附近 `selectedKeys={[location.pathname]}` 改为：

```tsx
          selectedKeys={[stripAppBase(location.pathname)]}
```

### 步骤 4：MainTabsLayout.tsx

文件：`frontend/src/mobile/layouts/MainTabsLayout.tsx`。

在文件顶部 import 区追加：

```tsx
import { stripAppBase } from "@/utils/platform";
```

将第 60 行附近 `const hideTabBar = shouldHideTabBar(location.pathname);` 改为：

```tsx
  const pathname = stripAppBase(location.pathname);
  const hideTabBar = shouldHideTabBar(pathname);
```

将第 65 行附近 `if (pattern.test(location.pathname)) {` 改为 `if (pattern.test(pathname)) {`；第 72 行附近依赖数组 `[location.pathname, setActiveTab, activeTab]` 改为 `[pathname, setActiveTab, activeTab]`；第 90 行附近 `key={location.pathname}` 改为 `key={pathname}`。

### 步骤 5：类型检查 + lint

```bash
cd frontend
npx tsc -b
npx eslint src/entry.tsx src/main.tsx src/layouts/MainLayout.tsx src/mobile/layouts/MainTabsLayout.tsx
```

预期：tsc 退出码 0；eslint 无新增 error（允许既有 warning）。

### 步骤 6：Commit

```bash
git add frontend/src/entry.tsx frontend/src/main.tsx frontend/src/layouts/MainLayout.tsx frontend/src/mobile/layouts/MainTabsLayout.tsx
git commit -m "feat(deploy): strip app base in entry, menu and mobile tab paths"
```

### 门禁

1. `npx tsc -b` 退出码 0；
2. 上述 4 文件 eslint 无新增 error；
3. `git diff --check` 干净；新增行不超 100 字符；
4. `npx vitest run` 全量通过（52）；
5. 提交只含上述 4 个文件，提交消息精确匹配步骤 6。

### 集成验证（必做）

任务 3 质量审查发现：在任务 4 之前，子路径部署下桌面端访问 `/emergency-plan-migration/m/login` 会命中
`MobileRedirect`（`window.location.replace` 同一 URL）形成自循环。本任务把 `isMobilePath` 改为
`stripAppBase` 判断后，该路径应直接加载移动端 App，不再进入桌面路由。

验证：在 `frontend/src` 中确认 `isMobilePath`（entry.tsx 与 main.tsx）均使用
`stripAppBase(window.location.pathname)`，并通读 `routes/index.tsx` 的 `MobileRedirect` 确认其仅在
桌面路由被匹配时兜底（预期：isMobilePath 修正后该分支不会被 `/m/*` 触发）。若发现循环路径仍存在，
以 DONE_WITH_CONCERNS 汇报并说明原因，不要擅自扩大改动范围。

### 汇报格式

完成后汇报：**状态：** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT；你实现了什么；验证结果；修改的文件；自审发现；任何疑虑。遇到疑问先以 NEEDS_CONTEXT 或 BLOCKED 汇报，不要猜测。
