# Codex Custom Subagents task handoff v1

Task: task_q_t1_review_spec

## 任务：规格合规审查（quality 任务 1：C0 基础修正）

你是一个规格合规审查子智能体。审查实现是否符合规格，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check`

### 审查对象

1. 规格：`docs\superpowers\specs\2026-08-10-plan-quality-check-enhancement-design.md` §3.0
2. 计划：`docs\superpowers\plans\2026-08-10-plan-quality-check-enhancement.md` 任务 1
3. 实现：git commit `a727bfa`（`git show a727bfa`）

### 审查重点

- MUST_HAVE_SECTION 映射（comprehensive=sec_2 / special=sec_1 / onsite=sec_1）与规格一致
- 档案字段未体现仅作用于必含章节
- 地址用关键片段匹配（路/街/门牌 + 区/开发区级），非必含章节不再误报
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
