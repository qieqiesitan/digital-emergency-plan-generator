# Codex Custom Subagents task handoff v1

Task: task_d2_t4_review_spec

## 任务：规格合规审查（diagrams batch2 任务 4：补图接口 + 占位 warning）

你是一个规格合规审查子智能体。审查实现是否符合规格，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams`

### 审查对象

1. 规格：`docs\superpowers\specs\2026-08-08-plan-diagrams-enhancement-design.md` §4.3、§5
2. 计划：`docs\superpowers\plans\2026-08-08-plan-diagrams-batch2.md` 任务 4
3. 实现：git commit `cc24825`（`git show cc24825`）

### 审查重点

- 路由是否 `POST /api/v1/plans/{plan_id}/diagrams/regenerate-missing`、权限校验（当前用户）存在
- regenerate_missing_diagrams 逻辑：只处理含占位的章节、regenerated/skipped/placeholders_remaining 计数正确
- plan_quality_service 是否增加占位 warning（含 key 与 reason）
- 路由是否注册到 main.py
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
