# Codex Custom Subagents task handoff v1

Task: task_d2_t2_review_spec

## 任务：规格合规审查（diagrams batch2 任务 2：生成器）

你是一个规格合规审查子智能体。审查实现是否符合规格，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams`

### 审查对象

1. 规格：`docs\superpowers\specs\2026-08-08-plan-diagrams-enhancement-design.md` §4.1、§6.2
2. 计划：`docs\superpowers\plans\2026-08-08-plan-diagrams-batch2.md` 任务 2
3. 实现：git commit `996de43`（`git show 996de43`）

### 审查重点

- make_placeholder 结构（key/placeholder/reason）
- build_risk_matrix_svg：5×5 矩阵、L/S 定位、risk_level 着色、无数据返回 placeholder
- build_evacuation_svg：坐标映射、分区多边形、风险点、集合点、消防设施、无数据 placeholder
- 返回结构（key/placeholder/svg）一致
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
