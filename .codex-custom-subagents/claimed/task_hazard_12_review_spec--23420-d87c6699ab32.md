# Codex Custom Subagents task handoff v1

Task: task_hazard_12_review_spec

## 目标

对隐患任务 12「AI 辅助端点」提交 `eb846dc`（父 `2e4238b`）做只读规格合规复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`eb846dc`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。
- 规格文档：`docs/superpowers/specs/2026-08-14-hazard-management-design.md`（重点 §3.7、§3.8、§6、§7、§16）。

## 审查清单（逐项核验并给出证据）

1. **统一模式**：四端点均文本输入 → llm_text_completion(timeout=60) → _parse_ai_json → 结构校验 → 失败/未配置/非法返回 {available:false}（200 降级）；不落库。
2. **plan-builder**：areas/frequency_preference 必填非空 422；返回 {available, plans, note}；plans 元素 {name, category, frequency, weekdays?, responsible_user_name?, zone_names?}；2-6 套（不足 2 降级、超 6 截断）；responsible/zone 为建议文本、页面确认后映射（docstring 说明）。
3. **schedule-suggestion**：plan_draft 必填；返回 {available, suggested_frequency, suggested_responsible_user_id, reason, note}；frequency 码值 daily/weekly/monthly/custom；id 不校验存在性（确认后落库前校验）；无法给出时 null+reason。
4. **checklist**：task_context 必填；返回 {available, items, note}；items {content, expected_note} 建议新增项。
5. **setup-wizard**：industry+areas 必填；返回 {available, org_suggestion, plans_suggestion, checklist_suggestion, note} 三块；复用既有服务函数（suggest_org_tree/plan-builder/checklist-template）避免重复实现；逐块防御、任一可用 available=True。
6. **既有端点未改动**：ai/grade、ai/governance-plan、ai/record-assist、ai/checklist-template 未动，全量回归覆盖。
7. **测试有效性**：38 个测试断言有效无空断言；四端点 ok/异常降级/未配置降级/空输入 422/非法返回降级；setup-wizard 三块结构。
8. **无越界**：`git show eb846dc --stat` 恰 3 个清单文件（services/hazard_ai_service.py、routers/hazard_management.py、tests/test_hazard_ai_api.py），消息精确匹配「feat(hazard): text-only AI assist endpoints」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_ai_api.py -v`（预期 38 passed）
- `python -m pytest tests/ -q`（预期 942 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check eb846dc`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_12_review_spec --claim-id <claim_id> --exit-code 0 --summary "隐患AI端点规格复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
