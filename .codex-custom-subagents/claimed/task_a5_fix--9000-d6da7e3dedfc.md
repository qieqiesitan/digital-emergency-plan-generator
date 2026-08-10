# Codex Custom Subagents task handoff v1

Task: task_a5_fix

## 任务：修复 A5 质量审查关键问题（login/register 路径统一降级逻辑）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 50a3abc。启动时 `cd` 到该目录，git status 确认干净。

### 背景

质量审查发现：login/register 成功后直接 `fetchMyMenus().catch(() => [])`，失败时菜单为空数组且不触发 menuLoadFailed 降级提示；而刷新页面走 loadMenuPermissions 会正确降级。两条路径语义不一致，且重复逻辑。本任务统一。

### 步骤 1：统一 login/register 菜单加载

在 `frontend/src/contexts/AuthContext.tsx` 中：

1. `login` 成功设置用户后，将：

```tsx
const menus = await fetchMyMenus().catch(() => []);
setState((prev) => ({ ...prev, menuPermissions: menus }));
```

替换为调用 `await loadMenuPermissions()`（复用降级逻辑；若 login 里已有该调用则确认其失败路径是否走 catch 降级）。同时确保 `menuLoadFailed: false` 在用户设置时重置。

2. `register` 成功路径做同样处理。

3. 若 `loadMenuPermissions` 的 catch 目前静默，加一行 `console.warn("菜单权限加载失败，已降级为核心菜单")`（次要项）。

4. 检查 `AuthContextValue` 与 `AuthState` 中 `menuLoadFailed` 是否有重复声明（若 AuthContextValue 是独立 interface 与 AuthState 并列，二者都需要；若 extends 则去掉重复）——按实际结构保持正确且不冗余。

### 步骤 2：tsc 验证

运行：`cd frontend && npx tsc -p tsconfig.app.json --noEmit`

预期：无类型错误。

### 步骤 3：Commit

```bash
git add frontend/src/contexts/AuthContext.tsx
git commit -m "fix(auth): unify menu permission degradation on login and register"
```

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 先读 AuthContext.tsx 全文理解现有结构
2. 按步骤实现
3. tsc 验证
4. 提交
5. 自审：login/register 与刷新路径现在是否都走同一降级？无回归？
6. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、tsc 结果、提交 SHA、自审发现
