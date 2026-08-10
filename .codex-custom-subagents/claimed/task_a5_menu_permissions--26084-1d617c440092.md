# Codex Custom Subagents task handoff v1

Task: task_a5_menu_permissions

## 任务：菜单与权限修正（易用性优化计划 A 任务 5）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 A1-A4 提交。启动时 `cd` 到该目录，git status 确认干净。

### 步骤 1：AuthContext 菜单权限失败降级

在 `frontend/src/contexts/AuthContext.tsx` 中：

1. `AuthContextValue` 接口增加字段 `menuLoadFailed: boolean`。
2. `AuthState` 类型增加 `menuLoadFailed: boolean`，初始状态 `false`（所有初始化位置都要加）。
3. `loadMenuPermissions` 的 catch 改为：

```tsx
} catch {
  // 菜单权限加载失败：降级为核心菜单（工作台/企业/预案/个人资料），并标记提示
  setState((prev) => ({
    ...prev,
    menuPermissions: ["menu:dashboard", "menu:enterprises", "menu:plans", "menu:profile"],
    menuLoadFailed: true,
  }));
}
```

4. `login` / `register` 成功后设置 `menuLoadFailed: false`；`logout` 与 `auth:logout` 事件 handler 重置 `menuLoadFailed: false`。

### 步骤 2：MainLayout 权限失败提示、法规库过滤、移除 AI 助手菜单

在 `frontend/src/layouts/MainLayout.tsx` 中：

1. 从 `useAuth()` 解构增加 `menuLoadFailed`。
2. 顶部导入追加 `Alert`（Ant Design）。
3. 在 `<Content>` 顶部（`<Outlet />` 前）增加可关闭提示：

```tsx
{menuLoadFailed && (
  <Alert
    type="warning"
    showIcon
    closable
    message="部分菜单加载失败，已显示核心菜单"
    style={{ marginBottom: 16 }}
  />
)}
```

4. 菜单项移除 AI 助手：删除 `{ key: "/chat", icon: <RobotOutlined />, label: "AI 助手" }`；菜单 onClick 中 `/chat` 特殊分支删除，统一 `navigate(key)`；`RobotOutlined` 导入若不再使用则删除。
5. 「法规库管理」纳入权限过滤：改为 `...(hasMenu("/settings/regulations") ? [{ key: "/settings/regulations", icon: <FileTextOutlined />, label: "法规库管理" }] : [])`。

### 步骤 3：tsc 验证

运行：`cd frontend && npx tsc -p tsconfig.app.json --noEmit`

预期：无类型错误。

### 步骤 4：Commit

```bash
git add frontend/src/layouts/MainLayout.tsx frontend/src/contexts/AuthContext.tsx
git commit -m "fix(menu): filter regulations menu, remove AI assistant entry, degrade menus on permission load failure"
```

## 上下文

- 现有 MainLayout 的 menuItems 含 AI 助手（点击打开聊天抽屉）、法规库管理（未走 hasMenu）；AuthContext 的 menuPermissions 加载失败时静默 catch。
- 注意：FloatingChat（右下角浮动球）保留不动；AI 助手菜单移除后聊天功能仍可用。
- 不要改动其它文件。

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 严格按任务描述实现（先读两个文件确认现有结构再改）
2. tsc 验证
3. 提交
4. 自审：menuLoadFailed 所有状态初始化/重置是否覆盖完整？法规库是否已过滤？AI 助手菜单是否移除且无残留引用？
5. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、tsc 结果、提交 SHA、自审发现
