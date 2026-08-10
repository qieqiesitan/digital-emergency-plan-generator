# Codex Custom Subagents task handoff v1

Task: task_b23_review_quality

## 任务：代码质量审查——task_b23_org_gen（规格审查已通过）

你是一个代码质量审查子智能体。目的：验证实现是否构建良好。规格合规性已由前序审查通过，本任务只关注代码质量。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。

BASE_SHA：28923cb；HEAD_SHA：f204355。

审查命令：cd 到 worktree 后运行 git diff 28923cb..f204355 并阅读实际代码。

### 实现内容

- generate_org_candidates（企业概况 → 应急组织框架，姓名/电话留空，防御解析）
- 1 个测试（monkeypatch llm）
- 提交 f204355（2 文件）

### 审查重点

1. Prompt 质量（组织框架合理性、防编造、JSON 示例）？
2. 防御解析是否完整（groups 非 list/null）？与 B2-2 的 extract 模式一致性？
3. 测试是否真实（RuntimeWarning 卫生问题）？
4. 复用 helper 是否正确、无重复逻辑？
5. 有无明显缺陷？

### 汇报格式

- 优点
- 问题（关键/重要/次要，带 file:line）
- 评估结论：✅ 通过 或 ❌ 需修复
