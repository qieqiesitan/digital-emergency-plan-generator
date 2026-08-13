# Codex Custom Subagents task handoff v1

Task: task_q_t2_review_spec

## 任务：规格合规审查（quality 任务 2：C1-C3 一致性）

你是一个规格合规审查子智能体。审查实现是否符合规格，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check`

### 审查对象

1. 规格：`docs\superpowers\specs\2026-08-10-plan-quality-check-enhancement-design.md` §3.1
2. 计划：`docs\superpowers\plans\2026-08-10-plan-quality-check-enhancement.md` 任务 2
3. 实现：git commit `6d21c65`（`git show 6d21c65`）

### 审查重点

- C1：跨章节人物提取正则、同名冲突 warning、与 org_structure 比对
- C2：地址/法人/安全负责人冲突检测（仅必含章节）
- C3：响应分级混用检测（III级 vs 一/二/三级）
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
