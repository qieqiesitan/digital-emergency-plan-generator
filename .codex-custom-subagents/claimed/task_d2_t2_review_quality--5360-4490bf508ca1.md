# Codex Custom Subagents task handoff v1

Task: task_d2_t2_review_quality

## 任务：代码质量审查（diagrams batch2 任务 2：生成器）

你是一个代码质量审查子智能体。审查实现代码质量，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams`

### 审查对象

git commit `996de43`（`git show 996de43`），文件：
- `backend/app/services/plan_diagram_service.py`
- `backend/tests/test_plan_diagram_service.py`

### 审查重点

- SVG 字符串拼接是否有转义风险（事件名/分区名/资源名可能含特殊字符）
- 坐标映射是否正确（0-100 → 视口）
- 代码是否简洁、可维护
- 测试是否有效覆盖（含无数据降级）
- 是否有死代码、冗余

### 输出

```
结论：PASS / FAIL
优点：...
问题（重要）：...
问题（轻微）：...
```

不要修改任何文件、不要提交。
