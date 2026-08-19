# Codex Custom Subagents task handoff v1

Task: task_hazard_09_review_quality

## 目标

对隐患任务 9「联动回写派生+四色图叠加」提交 `25e3328`（父 `3225ed2`）做只读代码质量复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`25e3328`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 审查清单（逐项核验并给出证据）

1. **服务层质量**：`open_hazard_count`/`open_hazard_count_by_objects` 实现正确（SQL 归属/分组/status 过滤），无 N+1（批量端点复用）；docstring 说明口径（object/measure、双对象各计一次）；无重复逻辑。
2. **端点接线质量**：workbench/overview/hierarchy/管控清单/告知卡字段组装正确；分区级=区内风险点和；批量查询结果映射无误；既有端点行为无回归（告知卡三链路统一）。
3. **schema/类型一致性**：后端 schema 默认值（open_hazard_count: int = 0 / has_open_hazard: bool）与前端类型字段对齐；前端 service 解包一致。
4. **测试质量**：15 个测试断言有效无空断言；mock 风格一致（async 带 @pytest.mark.asyncio）；覆盖计数/归零/字段存在/批量；既有告知卡测试补 mock 后仍有效。
5. **无过度工程**：改动最小化；无无关抽象。
6. **无越界**：`git show 25e3328 --stat` 恰 15 个清单文件，消息精确匹配「feat(hazard): derived open-hazard linkage on risk views」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_linkage.py -v`（预期 15 passed）
- `python -m pytest tests/ -q`（预期 867 passed，Event loop ResourceWarning 为既有非失败噪音）
- `npx tsc -b` exit 0、`npx vitest run` 全绿（可抽验）
- `git show --check 25e3328`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_09_review_quality --claim-id <claim_id> --exit-code 0 --summary "隐患派生联动质量复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
