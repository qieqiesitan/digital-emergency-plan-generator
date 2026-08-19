# Codex Custom Subagents task handoff v1

Task: task_hazard_03_fix

## 目标

按隐患任务 3 质量复审的 1 条必须修复 + 3 条建议修改修复，提交后复审。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`5af505b`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 修复清单

**1（必须，高严重）：`generate_tasks_for_plan` 在 `db.add(task)` 之前用 `task.id` 构造清单项**

`backend/app/services/hazard_service.py` 中先调用 `_build_inspection_items(db, plan, task.id)` 再 `db.add(task)`，而 `HazardInspectionTask.id` 的 `default=lambda: str(uuid4())` 在 **flush 时**才生成——真实数据库下所有清单项 `task_id=None`，`hazard_inspection_items.task_id` NOT NULL → 生产入库必然失败，任务生成功能不可用（现有测试 mock 的 fake_add 立即赋 id 掩盖了该缺陷）。

修复：`db.add(task)` 后先 `await db.flush()` 生成主键，再构建清单项（或构建后回填 task_id），保证 items.task_id == task.id。

**2（必须配套）：补测试防回归**

在 `backend/tests/test_hazard_plan_api.py` 补断言：生成的每个 item 的 `task_id == task.id`（且 task.id 非 None）。若 mock 的 `db.flush` 需要 stub，参照测试文件既有 fake 结构补一个 `flush` 桩（可复用现有 fake_add 的「add 时赋 id」语义，把赋值时机移到 flush 以贴近真实语义，或直接断言 items 的 task_id 与 task.id 一致）。

**3（建议）：软删计划不再生成任务**

`generate_tasks_for_plan` 开头校验 `plan.enabled is False → 返回 None`（与防重返回 None 同语义，docstring 说明），防止任务 8 调度器对停用计划继续出任务；补一条「enabled=False 计划 → 返回 None」测试。

**4（建议）：时区/并发约定写入 docstring**

`generate_tasks_for_plan` docstring 补充时区约定（due_at 用 naive 本地时间当日 18:00 的取舍与依据）与 `next_hazard_code` 并发兜底说明（count+1 并发窗口由 `uq_hazard_records_ent_code` 唯一约束兜底）。仅文档，不改逻辑。

## 验证

- `python -m pytest tests/test_hazard_plan_api.py -v` 全部 PASS（含新增 task_id 断言与 disabled 计划测试）；
- `python -m pytest tests/ -q` 无回归（Event loop ResourceWarning 为既有非失败噪音）；
- `git diff --check` 干净。

## Commit

```bash
git add backend/app/services/hazard_service.py backend/tests/test_hazard_plan_api.py
git commit -m "fix(hazard): flush task id before building items and skip disabled plans"
```

不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_03_fix --claim-id <claim_id> --exit-code 0 --summary "隐患任务生成 task_id 顺序修复完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试结果、修复说明（含问题复现与修复对照）。

## 规则

- 用 `apply_patch` 编辑；只改列出的 2 个文件；阻塞时停下汇报。
