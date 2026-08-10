# Codex Custom Subagents task handoff v1

Task: task_b1_t4_review_spec

## 任务：规格合规审查（任务 4：数据防幻觉护栏）

你是一个规格合规审查子智能体。审查实现是否符合规格，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement`

### 审查对象

1. 规格：`docs\superpowers\specs\2026-08-08-plan-generation-enhancement-design.md` 第 3.1 节
2. 计划：`docs\superpowers\plans\2026-08-08-plan-generation-batch1.md` 任务 4
3. 实现：git commit `da5f2d5`（`git show da5f2d5` 查看 diff）

### 审查重点

- `_collect_enterprise_data` 缺失字符串字段是否标「（待补充）」（address/industry/legal_representative/phone 等），非空值是否保持原样
- 数值/日期字段是否保持原样（employee_count/established_date/registered_capital/land_area/building_area）
- `risk_sources`/`emergency_resources` 列表逻辑是否保留
- COMPLIANCE_BLOCK 是否含「数据真实性护栏」且含「禁止推断」「（待补充）」规则
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
