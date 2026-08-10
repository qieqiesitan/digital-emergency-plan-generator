# Codex Custom Subagents task handoff v1

Task: task_a4_review_spec

## 任务：规格合规审查——task_a4_garbled_deadbtn 实现是否匹配任务要求

你是一个规格合规审查子智能体。目的：验证实现者是否构建了所要求的内容（不多不少）。关键：不要信任实现者的报告，必须独立阅读实际代码验证。

### 实现位置

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。审查提交 `2a9e3a3`：

git show 2a9e3a3 --stat 与 git show 2a9e3a3

### 要求的内容（任务 A4 原文）

1. frontend/src/pages/Enterprise/EnterpriseCreatePage.tsx 与 EnterpriseEditPage.tsx：「经济类型」placeholder 乱码（9 个问号）替换为「选择或输入经济类型」。
2. frontend/src/mobile/screens/LoginScreen.tsx：「忘记密码？」死按钮（纯 span 无事件、样式 text-primary-500 cursor-pointer）替换为静态提示「忘记密码？请联系管理员重置」（text-neutral-500，无点击暗示，保留布局）。
3. tsc -p tsconfig.app.json --noEmit 无类型错误。
4. Commit：fix(ui): repair garbled placeholder and dead forgot-password text。
5. 只改 3 个文件，只动显示文案。

### 实现者声称构建了什么

- 两处 placeholder 替换为「选择或输入经济类型」
- LoginScreen 忘记密码改为 text-neutral-500 静态提示「忘记密码？请联系管理员重置」，外层布局保留
- tsc 通过；提交 2a9e3a3（3 文件 4+/4-）

### 你的工作

阅读实际代码并验证：两处乱码是否都修了？死按钮是否静态化（无 cursor-pointer/无点击语义）？是否只改 3 个文件？有无范围外改动？

通过阅读代码来验证，而非信任报告。

### 汇报格式

- ✅ 符合规格（如果经过代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失或多余的内容，附带 file:line 引用]
