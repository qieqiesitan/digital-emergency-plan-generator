# Codex Custom Subagents task handoff v1

Task: task_hazard_04_review_quality

## 目标

对隐患任务 4「检查表模板+AI 生成」提交 `b1bc6b2`（父 `96e2c71`）做只读代码质量复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`b1bc6b2`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 审查清单（逐项核验并给出证据）

1. **服务层结构**：`hazard_ai_service.py` 80 行——AI 生成函数遵循 `risk_dual_ai_service.py`/`risk_ai_service.py` 惯例（llm_text_completion timeout=60、_parse_ai_json、available:false 降级、异常兜底有日志）；prompt 可读；无重复逻辑。
2. **路由层质量**：模板/AI 端点 handler 单一职责；复用既有 `_get_ent`/`_get_admin_ent`/ApiResponse 惯例；错误消息中文可读；`_validate_items` 兼容 pydantic 模型与 dict 的防御是否必要且清晰；无状态反模式。
3. **数据正确性**：系统模板保护（PUT/DELETE 422）路径完整；复制 deepcopy 语义正确（不影响源模板）；同名冲突检查覆盖系统与企业的（名称,类别）组合；列表合并逻辑（企业优先）无遗漏/重复；AI 响应结构 `{available, items, note}` 与端点一致。
4. **测试质量**：31 个测试断言有效无空断言；mock 风格与既有测试一致（async 带 `@pytest.mark.asyncio`）；主路径与边界（409/422/403/404/AI 降级）覆盖；未固化错误语义。
5. **无过度工程**：改动最小化，无无关抽象/依赖。
6. **无越界**：`git show b1bc6b2 --stat` 恰 3 个清单文件，消息精确匹配「feat(hazard): checklist templates with AI generation」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_template_api.py -v`（预期 31 passed）
- `python -m pytest tests/ -q`（预期 721 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check b1bc6b2`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_04_review_quality --claim-id <claim_id> --exit-code 0 --summary "隐患检查表模板质量复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
