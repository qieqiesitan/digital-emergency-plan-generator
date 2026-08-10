# Codex Custom Subagents task handoff v1

Task: task_final_fix_backend2_review

## 任务：复审——task_final_fix_backend2（draft+跳过修复）

你是代码审查子智能体。批次 1 质量审查发现 draft+跳过→生成/合并 500 的重要问题，实现者已修复（提交 c721578）。请做合并复审（规格 + 质量合一，改动小）。只读 + 验证，不要修改任何文件。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul，HEAD c721578）。

审查命令：cd 到 worktree 后 `git show c721578`，逐文件阅读实际代码。

### 复审重点

1. skip 接口是否改为 upsert 语义（有非 skipped 记录则改写状态、无则插入；generating/completed 拦截保留）？两处（risk_assessment/resource_investigation）对称？
2. generate/merge 查询是否加状态过滤（排除 skipped）+ `.first()` 防 MultipleResultsFound？历史脏数据不再 500？
3. 测试是否覆盖：draft+skip 不重复、重复行下生成/合并不 500、跳过后再生成/合并不 500？
4. 无回归：既有 skip 幂等、已完成拒绝、生成中拒绝语义保持？
5. 门禁：`cd backend && .\.venv\Scripts\python -m pytest -q --ignore=_docker_test.py` 全绿；`git diff --check` 干净。

### 汇报格式

```
结论：PASS / FAIL（✅ 通过 / ❌ 需修复）
逐项核验：...
参考建议（非阻塞）：...
```

