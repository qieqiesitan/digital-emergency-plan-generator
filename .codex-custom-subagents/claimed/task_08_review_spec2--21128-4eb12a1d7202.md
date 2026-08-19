# Codex Custom Subagents task handoff v1

Task: task_08_review_spec2

## 目标

对任务 8 的**规格修复提交做只读复审**。首次规格审查发现 2 条必须修复 + 1 条建议修改，实现者已修复并提交 `0b9647e`，现复审修复是否到位。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`0b9647e`（父 `70c9b57`）
- 文件：
  - `backend/app/services/risk_control_list_service.py`
  - `backend/app/routers/risk_management.py`
  - `backend/app/routers/public_risk.py`
  - `backend/tests/test_risk_control_list.py`

## 复审要点

1. **必须修复 1**：`build_ledger_workbook` 是否新增 sheet2 汇总（固有等级计数 + 管控层级计数，顺序合理），测试断言双 sheet 与汇总值；
2. **必须修复 2**：risk-publicity 响应是否含 `zones`（id/floor_id/floor_name/name/floor_plan_polygon/max_level/effective_color/inherent_max_level/inherent_effective_color），复用 `_zone_dual_levels`，floor selectinload 补齐；测试断言结构；
3. **建议 3**：公开端点与 risk-publicity 是否补 `generated_at`（ISO 可解析）；
4. 无越界改动：提交仅含上述 4 个文件。

## 验证

- backend 目录只读运行 `python -m pytest tests/test_risk_control_list.py -v`，预期全部 PASS（16 个）；
- `git show --check 0b9647e` 干净。

## 输出格式

- 结论：✅ 通过（必须修复与建议均已解决）/ ❌ 仍有问题（列明）
- 新问题标注严重级：**必须修复 / 建议修改 / 仅供参考**
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_08_review_spec2 --claim-id <claim_id> --exit-code 0 --summary "任务8规格复审完成"
```

## 规则

- 全程只读；任务池命令在任务池目录执行；代码审查在工作树目录进行。
