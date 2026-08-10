# Codex Custom Subagents task handoff v1

Task: task_c22_review_spec

## 任务：规格合规审查——task_c22_pro_mode

你是一个规格合规审查子智能体。目的：验证实现者是否构建了所要求的内容（不多不少）。关键：不要信任实现者的报告，必须独立阅读实际代码验证。

### 实现位置

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。审查提交 `a40dc54`：

git show a40dc54 --stat 与 git show a40dc54

### 要求的内容（任务 C2-2 原文摘要）

1. proMode state + localStorage 持久化。
2. 管理分组（系统管理/AI 管理/法规库）仅 proMode && hasMenu 时渲染；普通菜单始终渲染。
3. 顶部开关仅权限用户可见；defaultOpenKeys 随 proMode 调整。
4. tsc + eslint 通过。
5. Commit：feat(layout): professional mode toggle to expand management menus。

### 实现者声称构建了什么

- +19/-6：proMode state、分组门控、顶部开关、defaultOpenKeys + Menu key 重挂载
- 提交 a40dc54（1 文件），tsc + eslint 通过

### 你的工作

阅读实际代码验证：持久化/门控/开关可见性/默认展开正确？普通菜单始终渲染？只改 1 文件？

### 汇报格式

- ✅ 符合规格（如果经过代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失或多余的内容，附带 file:line 引用]
