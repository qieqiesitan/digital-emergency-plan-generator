# Codex Custom Subagents task handoff v1

Task: task_hazard_09_review_spec

## 目标

对隐患任务 9「联动回写派生+四色图叠加」提交 `25e3328`（父 `3225ed2`）做只读规格合规复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`25e3328`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。
- 规格文档：`docs/superpowers/specs/2026-08-14-hazard-management-design.md`（重点 §11.1、§14 扩展行）。

## 审查清单（逐项核验并给出证据）

1. **派生计数**：`open_hazard_count(db, object_id=None, measure_id=None)` 统计 status != closed 记录数；`open_hazard_count_by_objects` 批量（GROUP BY object_id + measure 经 risk_events 子查询归属）；不修改风险源表字段（实时派生、闭环归零）；object/measure 双空返回 0；同记录双对象各计一次的 docstring 说明。
2. **视图扩展**：workbench/overview/hierarchy/管控清单响应含 open_hazard_count（分区级=区内风险点和）；告知卡 has_open_hazard 标记（列表批量、详情/导出/公开三链统一 build_card_data）；schema 字段与端点组装一致。
3. **前端类型**：types/riskManagement.ts、riskMappingWorkbench.ts、riskNoticeCard.ts 与 service 补字段，与后端契约一致。
4. **测试有效性**：15 个测试断言有效无空断言；覆盖派生计数正确/闭环归零/端点字段存在/批量计数。
5. **无越界**：`git show 25e3328 --stat` 恰 15 个清单文件（后端 7 + 测试 4 + 前端 4），消息精确匹配「feat(hazard): derived open-hazard linkage on risk views」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_linkage.py -v`（预期 15 passed）
- `python -m pytest tests/ -q`（预期 867 passed，Event loop ResourceWarning 为既有非失败噪音）
- 前端（可抽验）：`npx tsc -b` exit 0、`npx vitest run` 全绿
- `git show --check 25e3328`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_09_review_spec --claim-id <claim_id> --exit-code 0 --summary "隐患派生联动规格复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
