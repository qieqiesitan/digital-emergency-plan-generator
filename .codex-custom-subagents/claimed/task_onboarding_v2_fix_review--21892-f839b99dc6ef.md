# Codex Custom Subagents task handoff v1

Task: task_onboarding_v2_fix_review

## 任务：复审——task_onboarding_v2_fix（StepOrg 单组采纳修复）

你是代码审查子智能体。批次 A 质量审查发现 StepOrg 单组采纳误删候选的重要问题，实现者已修复（提交 3b95404）。请做合并复审（规格+质量合一，改动小）。只读 + 验证，不要修改任何文件。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2`（master 分支，HEAD 3b95404）。

审查命令：`git show 3b95404`，逐文件阅读实际代码。

### 复审重点

1. `generate()` 归一化 `_key`（group_key || group_name || imp-org-ts-i）是否正确且唯一；`adoptGroup` filter 是否只移除被采纳组；
2. adoptAll 无回归（全量合并后清空候选）；
3. 回显/取消采纳/成员编辑逻辑未被破坏；
4. 门禁：tsc/eslint/diff 全绿，无 any、无 >100 字符行。

### 汇报格式

```
结论：PASS / FAIL（✅ 通过 / ❌ 需修复）
逐项核验：...
参考建议（非阻塞）：...
```

