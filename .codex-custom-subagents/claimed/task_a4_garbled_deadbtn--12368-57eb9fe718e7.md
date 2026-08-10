# Codex Custom Subagents task handoff v1

Task: task_a4_garbled_deadbtn

## 任务：乱码 placeholder 与移动端死按钮修复（易用性优化计划 A 任务 4）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 A1-A3 提交。启动时 `cd` 到该目录，git status 确认干净。

### 步骤 1：修复「经济类型」乱码 placeholder

在 `frontend/src/pages/Enterprise/EnterpriseCreatePage.tsx` 和 `frontend/src/pages/Enterprise/EnterpriseEditPage.tsx` 中，将：

placeholder="?????????"

替换为：

placeholder="选择或输入经济类型"

（先读文件确认乱码字符串的确切形式，若与实际略有差异按实际替换为正确中文。）

### 步骤 2：修复移动端忘记密码死按钮

在 `frontend/src/mobile/screens/LoginScreen.tsx` 中，将「忘记密码？」的 `<span>`（当前样式 text-primary-500 cursor-pointer，无点击事件）替换为静态提示（保留布局）：

```tsx
<div className="flex justify-end mt-sm">
  <span className="text-body-sm text-neutral-500">
    忘记密码？请联系管理员重置
  </span>
</div>
```

删除原 text-primary-500 cursor-pointer 样式，去掉可点击暗示。若原有结构不是 div+span，按实际结构调整但保持文案与静态化意图。

### 步骤 3：tsc 验证

运行：`cd frontend && npx tsc -p tsconfig.app.json --noEmit`

预期：无类型错误。

### 步骤 4：Commit

```bash
git add frontend/src/pages/Enterprise/EnterpriseCreatePage.tsx frontend/src/pages/Enterprise/EnterpriseEditPage.tsx frontend/src/mobile/screens/LoginScreen.tsx
git commit -m "fix(ui): repair garbled placeholder and dead forgot-password text"
```

## 上下文

- 纯界面文案修复，不改变行为/逻辑。
- EnterpriseCreatePage 与 EnterpriseEditPage 各有一处「经济类型」下拉的乱码 placeholder（此前确认文件里是 9 个问号）。
- LoginScreen 的「忘记密码？」是纯 span 无点击事件（死按钮），本任务只做静态化提示。

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 严格按任务描述修复
2. tsc 验证
3. 提交
4. 自审：确认两处乱码都修了、死按钮已静态化、无误改
5. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修复明细、tsc 结果、提交 SHA、自审发现
