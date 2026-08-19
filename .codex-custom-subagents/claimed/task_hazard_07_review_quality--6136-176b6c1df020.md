# Codex Custom Subagents task handoff v1

Task: task_hazard_07_review_quality

## 目标

对隐患任务 7「整改/复查/销号端点」提交 `8e69550`（父 `079a5f0`）做只读代码质量复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`8e69550`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 审查清单（逐项核验并给出证据）

1. **状态机接线正确性**：rectify/review/close 正确调用 apply_transition（payload 契约一致）；未修改状态机逻辑；错误状态码透传正确（409/422/403 分层）。
2. **actor_role 映射质量**：`_map_actor_role` 按动作取本人字段判定（rectify→rectification_user_id/rectifier、review→reviewer_user_id/reviewer），企业主/启用 admin→enterprise_admin；非企业人员 404 拦截；与任务 6 映射复用一致；无逻辑重复。
3. **复查期限提醒实现**：`_dict_rule_days` 与状态机 `_rule_days` 对齐（兼容 {days}/N/JSON 字符串三形态）；review_due 通知字段（type/user_id/record_id/message）正确；字典缺天数时不创建通知的取舍说明；响应 review_deadline 序列化正确。
4. **数据正确性**：reviewer_user_id 校验（≠ 整改人、enabled 成员）；HazardRectification/HazardReview/HazardNotification 落库字段正确；audit log 留痕（状态机负责）；close 的 closed_at。
5. **测试质量**：27 个测试断言有效无空断言；mock 风格一致（async 带 @pytest.mark.asyncio）；覆盖全路径/权限/退回/二次复核/销号留痕。
6. **无过度工程**：改动最小化；无无关抽象。
7. **无越界**：`git show 8e69550 --stat` 恰 2 个清单文件，消息精确匹配「feat(hazard): rectify, review and close endpoints wired to state machine」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_review_api.py -v`（预期 27 passed）
- `python -m pytest tests/ -q`（预期 836 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check 8e69550`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_07_review_quality --claim-id <claim_id> --exit-code 0 --summary "隐患整改/复查/销号质量复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
