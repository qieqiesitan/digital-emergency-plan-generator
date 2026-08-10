# Codex Custom Subagents task handoff v1

Task: task_ai_generate_review_quality

## 任务：代码质量审查——task_ai_generate_experience（规格审查通过后）

你是代码质量审查子智能体。请审查 AI 生成体验修复的代码质量。只读 + 验证，不要修改任何文件。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2`（master 分支，HEAD 视当前最新提交，含 2d1a8ff）。

审查命令：`git show 2d1a8ff`，逐文件阅读实际代码。

### 审查重点

1. errorDetail helper 实现（axios 判定、detail 取值、fallback 顺序）在各文件的复用一致性与正确性；
2. 超时 180000 的合理性（后端 120s + 余量，SSE 流式请求是否受影响——chat/生成流是否也走 api 实例）；
3. AuthContext 登出提示（message 使用方式、一次性语义、与既有登出逻辑冲突？）；
4. loading 文案改动无回归（按钮 disabled/loading 逻辑）；
5. 类型/样式：无 any、无 >100 字符行、无未使用导入。

### 门禁

- `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
- `npx eslint` 改动文件不得新增 error（与基线逐项对比）
- `git diff --check` 干净；diff 无 any

### 汇报格式

- 优点
- 问题（关键/重要/次要，带 file:line）
- 评估结论：✅ 通过 或 ❌ 需修复

