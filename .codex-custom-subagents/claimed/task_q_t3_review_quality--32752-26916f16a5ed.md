# Codex Custom Subagents task handoff v1

Task: task_q_t3_review_quality

## 任务：代码质量审查（quality 任务 3：L1-L3 合规性）

你是一个代码质量审查子智能体。审查实现代码质量，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check`

### 审查对象

git commits `3c7ad30` + `a27df46`（`git show`），文件：
- `backend/app/services/plan_quality_service.py`
- `backend/app/routers/export.py`
- `backend/tests/test_plan_quality_compliance.py`

### 审查重点

- 法规引用提取正则是否稳健（避免误抓正文里的书名号、标准号）
- 法规库加载缓存是否合理（路径、异常处理）
- L1 required_sections 传参与空章节 issue 的边界
- L3 术语对是否与 COMPLIANCE_BLOCK 一致
- 是否有死代码（如未使用的 _regulation_exists）、冗余

### 输出

```
结论：PASS / FAIL
优点：...
问题（重要）：...
问题（轻微）：...
```

不要修改任何文件、不要提交。
