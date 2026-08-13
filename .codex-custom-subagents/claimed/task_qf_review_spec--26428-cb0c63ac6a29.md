# Codex Custom Subagents task handoff v1

Task: task_qf_review_spec

## 任务：规格合规审查（quality 规则修复）

你是一个规格合规审查子智能体。审查修复是否符合任务要求与规格，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-fixes`

### 审查对象

1. 修复任务：`.codex-custom-subagents\pending\task_qf_fix.md` 或 git commit `8355151`
2. 规格：`docs\superpowers\specs\2026-08-10-plan-quality-check-enhancement-design.md`
3. 实现：`git show 8355151`

### 审查重点

1. C1：职务后须有分隔符才捕获姓名（「总指挥不在岗时」不误报）；组长已从 ROLE_PATTERNS 移除；总经理→总指挥语义映射实现
2. C3：响应分级排除「设置/分为」数量表述；时限全局比对已删除
3. E3：类别下所有资源为 0 才报（有正数不报）
4. 规格文档已同步
5. 是否有多余改动

### 输出

```
结论：PASS / FAIL
问题清单：
- [严重/一般] 描述（如无问题写「无」）
缺失项：...
多余项：...
```

不要修改任何文件、不要提交。
