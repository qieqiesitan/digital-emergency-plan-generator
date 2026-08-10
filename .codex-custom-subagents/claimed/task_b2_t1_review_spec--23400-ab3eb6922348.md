# Codex Custom Subagents task handoff v1

Task: task_b2_t1_review_spec

## 任务：规格合规审查（批2 任务 1：PlanProject 编号字段）

你是一个规格合规审查子智能体。审查实现是否符合规格，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement`

### 审查对象

1. 规格：`docs\superpowers\specs\2026-08-08-plan-generation-enhancement-design.md` 第 3.3 节「a/b/c」
2. 计划：`docs\superpowers\plans\2026-08-08-plan-generation-batch2.md` 任务 1
3. 实现：git commit `43db521`（`git show 43db521`）

### 审查重点

- PlanProject 是否新增且仅新增 plan_number(String 100)/version_number(String 50) 两字段
- 迁移 SQL 是否幂等且与模型一致
- `_generate_plan_number` 格式是否符合规格：企业名去空格取前 4 字符（不足原样、空用「企业」）+ 类型码（comprehensive=ZH/special=ZX/onsite=XC）+ 三位序号
- 是否有多余改动

### 输出

```
结论：PASS / FAIL
问题清单：
- [严重/一般] 描述（如无问题写「无」）
缺失项：...
多余项：...
```

不要修改任何文件、不要提交。
