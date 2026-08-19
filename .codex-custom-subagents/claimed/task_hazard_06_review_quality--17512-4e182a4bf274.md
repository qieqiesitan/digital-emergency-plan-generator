# Codex Custom Subagents task handoff v1

Task: task_hazard_06_review_quality

## 目标

对隐患任务 6「分级/治理方案/挂牌审批」提交 `079a5f0`（父 `e924dd3`）做只读代码质量复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`079a5f0`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 审查清单（逐项核验并给出证据）

1. **状态机接线正确性**：grade/approve/reject 端点正确调用 `apply_transition`（payload 契约与状态机一致：level/grading_basis/hazard_type/rectification_user_id/level_source/deadline_rules/rectification_plan/comment）；actor_role 映射（企业主→enterprise_admin）实现清晰；未修改状态机逻辑。
2. **服务层结构**：`hazard_ai_service.py` 的 `ai_grade`/`ai_governance_plan` 遵循既有 AI 惯例（llm_text_completion timeout=60、_parse_ai_json、available:false 降级）；JUDGMENT_POINTS 常量中文内容可读、来源标注合规；无重复逻辑。
3. **路由层质量**：各端点 handler 单一职责；复用既有 helper（_get_ent/_get_admin_ent/ApiResponse/get_dict_map）；错误消息中文可读；`_deadline_rules` 字典转换（value 提取为 {days}）正确；无状态反模式。
4. **数据正确性**：deadline 计算（数据字典 major/general → 状态机天数）；rectification_user_id 校验；重大治理方案五键；approve/reject 写 HazardApproval 路径（状态机负责）；_record_dict 扩展字段正确。
5. **测试质量**：43 个测试断言有效无空断言；mock 风格一致（async 带 @pytest.mark.asyncio）；覆盖主路径/边界/权限/AI 降级；测试污染 data_dicts 缓存问题的修复（autouse 清理）合理。
6. **无过度工程**：改动最小化；reject 为可选实现（含测试说明）。
7. **无越界**：`git show 079a5f0 --stat` 恰 3 个清单文件，消息精确匹配「feat(hazard): grading, governance plan and major hazard approval」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_grade_api.py -v`（预期 43 passed）
- `python -m pytest tests/ -q`（预期 809 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check 079a5f0`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_06_review_quality --claim-id <claim_id> --exit-code 0 --summary "隐患分级/审批质量复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
