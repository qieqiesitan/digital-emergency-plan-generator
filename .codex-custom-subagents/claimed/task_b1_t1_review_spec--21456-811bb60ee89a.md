# Codex Custom Subagents task handoff v1

Task: task_b1_t1_review_spec

## 任务：规格合规审查（任务 1：PlanSection 元数据字段）

你是一个规格合规审查子智能体。审查实现是否符合规格，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement`

### 审查对象

1. 规格：`docs\superpowers\specs\2026-08-08-plan-generation-enhancement-design.md` 第 3.2 节（模板元数据落地）
2. 计划：`docs\superpowers\plans\2026-08-08-plan-generation-batch1.md` 任务 1
3. 实现：git commit `8cf653a`（`git show 8cf653a` 查看 diff）

### 审查重点

- PlanSection 是否新增且仅新增规格要求的 4 个字段（ai_generatable/auto_fill/auto_fill_source/data_dependencies），类型与默认值是否与规格一致（Boolean/Boolean/String(50) nullable/JSONB list）
- 迁移 SQL 是否与规格一致且幂等（ADD COLUMN IF NOT EXISTS、默认值、NOT NULL）
- 是否有多余改动（超出任务范围的修改）
- 测试是否覆盖规格验收标准（列存在、默认值）

### 输出

最终回复格式：

```
结论：PASS / FAIL
问题清单：
- [严重/一般] 描述（如无问题写「无」）
缺失项：...
多余项：...
```

不要修改任何文件、不要提交。
