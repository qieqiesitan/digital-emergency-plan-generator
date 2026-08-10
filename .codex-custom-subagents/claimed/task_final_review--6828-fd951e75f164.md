# Codex Custom Subagents task handoff v1

Task: task_final_review

## 任务：预案生成增强全量最终审查

你是一个最终代码审查子智能体。三批实现已完成，请对整体实现做最终审查（规格覆盖度 + 跨批一致性 + 质量），只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement`

当前 HEAD 应为 `6360dcb`，分支 `codex/plan-generation-enhancement`。

### 审查对象

1. 规格：`docs\superpowers\specs\2026-08-08-plan-generation-enhancement-design.md`（全量 3 批）
2. 计划：`docs\superpowers\plans\2026-08-08-plan-generation-batch1.md` / `batch2.md` / `batch3.md`
3. 实现范围：`git log master..HEAD --oneline`（约 23 commits）

### 审查重点

**规格覆盖度**（逐节核对）：
- 批 1：3.1 数据防幻觉护栏（缺失标注+护栏）；3.2 模板元数据（模型/迁移/复制/duplicate/schema/autofill 接口/桌面+移动端）
- 批 2：3.3 导出编号（字段/迁移/生成/覆盖/导出真实值/签署页/前端输入）；3.4 版本快照（_build_snapshot/_apply_snapshot/回滚/旧快照兼容）
- 批 3：3.5 质量校验（6 规则/validate 接入/前端报告）；3.6 失败重试（failed_sections/status/前端）；3.7 批量去重+移动端；3.8 Diff 弹窗

**跨批一致性**：
- 迁移 SQL 与模型一致（plan_sections 4 字段、plan_projects 2 字段）
- 版本快照两处（versions.py + generation.py）一致
- 前端类型与后端 schema 一致（PlanSection 元数据、PlanProject 编号、SSEEvent failed_sections）

**质量**：
- 无死代码/重复实现/明显缺陷
- 关键安全点（XSS 转义、权限校验）

### 输出

```
结论：PASS / FAIL
规格覆盖度：逐节列出（覆盖/缺失/偏差）
跨批一致性问题：...
质量问题（重要）：...
质量问题（轻微）：...
建议（可选）：...
```

不要修改任何文件、不要提交。
