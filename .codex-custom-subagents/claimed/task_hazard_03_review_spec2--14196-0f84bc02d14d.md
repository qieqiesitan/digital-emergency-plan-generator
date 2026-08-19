# Codex Custom Subagents task handoff v1

Task: task_hazard_03_review_spec2

## 目标

对隐患任务 3 质量修复提交 `96e2c71`（父 `5af505b`）做只读规格合规复审，核对修复是否全部落地且不引入规格偏离，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`96e2c71`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 审查清单（逐项核验并给出证据）

1. **必须项——task_id 顺序**：`generate_tasks_for_plan` 现在 `db.add(task)` → `await db.flush()` 后再构建清单项；`task.id` 在构建 items 时已生成；新增测试断言 `task.id is not None` 且每个 item 的 `task_id == task.id`；测试的 flush 桩语义贴近真实（add 时不再立即赋 id，或 flush 时赋）。
2. **建议项——停用计划**：`plan.enabled is False → 返回 None`（docstring 说明），与防重返回 None 语义一致；有对应测试断言返回 None 且未调用 add/flush。
3. **文档约定**：docstring 已补充时区约定（due_at naive 本地时间当日 18:00 的取舍）与 `next_hazard_code` 并发兜底说明（`uq_hazard_records_ent_code` 唯一约束）。
4. **无回归偏离**：修复不改变计划 CRUD/任务端点/to-record 的既有契约（§5.1-5.3、§6、§14）；防重/软删/状态流转语义不变。
5. **无越界**：`git show 96e2c71 --stat` 恰 2 个清单文件（services/hazard_service.py、tests/test_hazard_plan_api.py），消息精确匹配「fix(hazard): flush task id before building items and skip disabled plans」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_plan_api.py -v`（预期 55 passed）
- `python -m pytest tests/ -q`（预期 690 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check 96e2c71`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_03_review_spec2 --claim-id <claim_id> --exit-code 0 --summary "隐患任务3修复规格复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
