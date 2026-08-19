# Codex Custom Subagents task handoff v1

Task: task_hazard_05_review_quality

## 目标

对隐患任务 5「隐患登记三渠道+AI 摘要分类」提交 `e924dd3`（父 `b1bc6b2`）做只读代码质量复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`e924dd3`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 审查清单（逐项核验并给出证据）

1. **服务层结构**：`hazard_ai_service.py` 的 `record_assist` 遵循既有 AI 惯例（llm_text_completion timeout=60、_parse_ai_json、get_system_ai_config、available:false 降级、异常兜底有日志）；prompt 可读；返回结构合法校验（title 空/hazard_type 非字典码值/suggested_level 非法 → 降级）。
2. **路由层质量**：`hazard_management.py` 登记端点与 `public_hazard.py` 扫码端点 handler 单一职责；复用既有 helper（_get_ent/ApiResponse/next_hazard_code）；错误消息中文可读；无状态反模式（nonce 缓存实现为进程内 dict+时间戳惰性清理，说明单进程假设与并发安全）；token 匹配优先级实现清晰。
3. **数据正确性**：hazard_type 字典校验实现（数据字典查询方式正确）；object/measure 归属校验；扫码上报 created_by=NULL 且 source_type=report；code 生成复用 next_hazard_code；nonce 写入时机（成功落库后）合理。
4. **测试质量**：45 个测试断言有效无空断言；mock 风格与既有测试一致（async 带 @pytest.mark.asyncio）；三渠道/nonce 幂等/token 404/AI 降级/权限覆盖；未固化错误语义。
5. **无过度工程**：改动最小化；main.py 挂载为最小改动。
6. **无越界**：`git show e924dd3 --stat` 恰 6 个清单文件，消息精确匹配「feat(hazard): record registration via web, qr and mobile with AI assist」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_record_api.py tests/test_hazard_public_api.py -v`（预期 45 passed）
- `python -m pytest tests/ -q`（预期 766 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check e924dd3`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_05_review_quality --claim-id <claim_id> --exit-code 0 --summary "隐患登记三渠道质量复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
