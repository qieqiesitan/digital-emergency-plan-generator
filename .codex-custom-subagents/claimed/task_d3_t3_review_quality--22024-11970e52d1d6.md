# Codex Custom Subagents task handoff v1

Task: task_d3_t3_review_quality

## 任务：代码质量审查（diagrams batch3 任务 3：缺数据提示条 + 补图按钮）

你是一个代码质量审查子智能体。审查实现代码质量，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams`

### 审查对象

git commit `7d256c5`（`git show 7d256c5`），文件：
- `frontend/src/pages/Plan/PlanEditorPage.tsx`

### 审查重点

- missingDiagrams 计算是否高效（useMemo 依赖正确）
- 补图 mutation 是否合理（成功后刷新、失败提示）
- 提示条布局是否不破坏现有 UI
- 是否有死代码、未使用导入

### 输出

```
结论：PASS / FAIL
优点：...
问题（重要）：...
问题（轻微）：...
```

不要修改任何文件、不要提交。
