# Codex Custom Subagents task handoff v1

Task: task_c22_pro_mode

## 任务：专业模式开关（易用性优化计划 C2 任务 C2-2）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 C2-1 提交（062afd8）。启动时 `cd` 到该目录，git status 确认干净。

### 背景

- `frontend/src/layouts/MainLayout.tsx` 已由计划 A 任务 A5 修改（法规库 hasMenu、AI 助手菜单移除、menuLoadFailed 提示）。
- 本任务：顶部「专业模式」开关（localStorage 记忆 + 有权限用户可见），开启时展开管理分组（系统管理/AI 管理/法规库等），关闭时隐藏。

### 步骤 1：实现专业模式开关

`frontend/src/layouts/MainLayout.tsx`：

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

2. 管理分组（系统管理/AI 管理/法规库管理）仅在 `proMode && hasMenu(...)` 时渲染；普通菜单（工作台/企业/预案/设置）始终渲染。

3. 顶部（企业切换旁）开关，仅对有权限用户显示（`showSystemGroup || showAIGroup || hasMenu("/settings/regulations")`）：

```tsx
{(showSystemGroup || showAIGroup || hasMenu("/settings/regulations")) && (
  <Button size="small" onClick={togglePro}>
    {proMode ? "专业模式 开" : "专业模式 关"}
  </Button>
)}
```

4. `defaultOpenKeys` 根据 proMode 调整（proMode 时展开管理分组）。

### 步骤 2：tsc + eslint 验证

运行：`cd frontend && npx tsc -p tsconfig.app.json --noEmit`

再运行：`cd frontend && npx eslint src/layouts/MainLayout.tsx`

预期：无类型/ESLint 错误（无 no-explicit-any）。

### 步骤 3：Commit

```bash
git add frontend/src/layouts/MainLayout.tsx
git commit -m "feat(layout): professional mode toggle to expand management menus"
```

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 先读 MainLayout.tsx 现状（A5 已改）
2. 按步骤实现
3. tsc + eslint 验证
4. 提交
5. 自审：开关仅权限用户可见？proMode 持久化？管理分组开/关正确？普通菜单始终可见？
6. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、tsc/eslint 结果、提交 SHA、自审发现
