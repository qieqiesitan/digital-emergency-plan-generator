# Codex Custom Subagents task handoff v1

Task: task_q_final_fix

## 任务：同步 C3 时限规则规格描述

你是一个实现子智能体。最终审查发现 `docs\superpowers\specs\2026-08-10-plan-quality-check-enhancement-design.md` 的 C3 时限规则描述与实现不一致：

- 规格写：`30分钟与0.5小时并存 → warning`（并存即报）
- 实现（更合理）：等价时长（30分钟 vs 0.5小时）**不报**，仅不等价时长（如 30分钟 vs 2小时）才报

实现语义更合理（等价表述不应视为不一致），请更新规格文档与实现对齐。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check`

当前 HEAD 应为 `6fc7eda`。启动时 `cd` 到该目录，`git status` 确认干净。

### 修改内容

规格 §3.1 规则 C3（约 79 行）的时限部分改为：

```markdown
- 时限单位混用：同时出现 `分钟` 与 `小时` 且数值**不等价**（如「30分钟」与「2小时」并存；「30分钟」与「0.5小时」等价不报）→ warning：`时限表述不统一`。
```

规格 §6 测试计划中 C3 行（约 170 行）改为：

```markdown
- C3：III级与一级混用 → warning；30分钟与2小时并存（不等价）→ warning；30分钟与0.5小时并存（等价）→ 不报。
```

若规格中还有其他描述旧语义的位置（如 §7 自检或 §1 概述），一并同步。

### 验证

`git diff --check` 干净；无需跑测试（纯文档变更）。

### Commit

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check
git add docs/superpowers/specs/2026-08-10-plan-quality-check-enhancement-design.md
git commit -m "docs(plan): sync C3 time-unit rule with equivalent-duration semantics (quality)"
```

### 完成报告

最终回复报告：
1. 状态：DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED
2. 修改位置
3. commit SHA

不要提交其他文件；不要推送；不要动 TASKS.md。
