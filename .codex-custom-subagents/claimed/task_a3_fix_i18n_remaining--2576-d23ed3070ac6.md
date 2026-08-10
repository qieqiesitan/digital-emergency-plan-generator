# Codex Custom Subagents task handoff v1

Task: task_a3_fix_i18n_remaining

## 任务：补齐 VersionListPage 剩余英文文案 + AIConfigPage 全角冒号（A3 质量审查跟进修复）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 6df534e。启动时 `cd` 到该目录，git status 确认干净。

### 背景

任务 A3 已中文化 4 个文件，但质量审查发现 `frontend/src/pages/Plan/VersionListPage.tsx` 仍有用户可见英文（列头、回滚按钮、回滚确认弹窗），且 `frontend/src/pages/Settings/AIConfigPage.tsx` 拼接处用了半角冒号。本任务补齐。

### 步骤 1：VersionListPage 剩余中文化

在 `frontend/src/pages/Plan/VersionListPage.tsx` 中替换（先读文件确认实际字符串再改）：

- 表格列头 `"version"` → `"版本"`；`"type"` → `"类型"`；`"note"` → `"说明"`；`"time"` → `"时间"`
- 类型列取值 `"auto"` → `"自动"`；`"manual"` → `"手动"`
- 回滚按钮文本 `rollback` → `回滚`
- 回滚确认弹窗 `"rollback?"` / `"rollback to V{n}?"` → `"确定回滚？"` / `"确定回滚到 V{n}？"`（按实际模板字符串调整）
- 若还有其它用户可见英文文案（如空状态、提示），一并中文化；只改显示文案，不动 dataIndex/key/函数名

### 步骤 2：AIConfigPage 全角冒号

在 `frontend/src/pages/Settings/AIConfigPage.tsx` 中：

- `"连接成功: "` → `"连接成功："`（全角冒号）
- `"连接失败: "` → `"连接失败："`
- `"上次测试: "` → `"上次测试："`
- `"failed: "` / `"connected: "` 等拼接若有半角冒号一并改全角

### 步骤 3：tsc 验证

运行：`cd frontend && npx tsc -p tsconfig.app.json --noEmit`

预期：无类型错误。

### 步骤 4：Commit

```bash
git add frontend/src/pages/Plan/VersionListPage.tsx frontend/src/pages/Settings/AIConfigPage.tsx
git commit -m "fix(i18n): localize remaining version list copy and full-width colons"
```

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 先读文件确认实际字符串，再替换
2. tsc 验证
3. 提交
4. 自审：确认无遗漏英文文案、无误改
5. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 替换明细、tsc 结果、提交 SHA、自审发现
