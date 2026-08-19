# Codex Custom Subagents task handoff v1

Task: task_hazard_12_review_quality

## 目标

对隐患任务 12「AI 辅助端点」提交 `eb846dc`（父 `2e4238b`）做只读代码质量复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`eb846dc`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 审查清单（逐项核验并给出证据）

1. **服务层结构**：`hazard_ai_service.py` 四个新函数（build_inspection_plans/suggest_schedule/suggest_checklist_items/run_setup_wizard）遵循既有 AI 惯例（llm_text_completion timeout=60、_parse_ai_json、available:false 降级）；prompt 可读；返回结构校验完整；无重复逻辑（setup-wizard 复用既有函数方式合理）；无重名覆盖（_normalize_plan_suggestion 与既有治理方案归一化函数区分）。
2. **路由层质量**：四端点 handler 单一职责；复用 _get_ent/ApiResponse；输入必填校验 422；错误消息中文可读；无状态反模式。
3. **数据正确性**：plan-builder 数量约束（2-6、不足降级、超截断）；schedule-suggestion 码值校验；setup-wizard 三块逐块防御与整体降级语义（任一可用 available=True）；返回结构与端点一致。
4. **测试质量**：38 个测试断言有效无空断言；mock LLM 风格一致（async 带 @pytest.mark.asyncio）；ok/fallback/未配置/空输入/非法返回全覆盖。
5. **无过度工程**：改动最小化；无无关抽象。
6. **无越界**：`git show eb846dc --stat` 恰 3 个清单文件，消息精确匹配「feat(hazard): text-only AI assist endpoints」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_ai_api.py -v`（预期 38 passed）
- `python -m pytest tests/ -q`（预期 942 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check eb846dc`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_12_review_quality --claim-id <claim_id> --exit-code 0 --summary "隐患AI端点质量复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
