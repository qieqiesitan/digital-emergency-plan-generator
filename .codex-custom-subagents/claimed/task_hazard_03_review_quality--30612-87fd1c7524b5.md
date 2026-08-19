# Codex Custom Subagents task handoff v1

Task: task_hazard_03_review_quality

## 目标

对隐患任务 3「排查计划/任务/清单项端点」提交 `5af505b`（父 `16b3656`）做只读代码质量复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`5af505b`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 审查清单（逐项核验并给出证据）

1. **服务层结构**：`hazard_service.py` 的 `generate_tasks_for_plan`/`next_hazard_code` 职责单一、纯服务层（不掺 HTTP/响应组装）、docstring 说明频次/时区/防重约定；无重复逻辑；AI 补全占位注释清晰。
2. **路由层质量**：`hazard_management.py` 569 行内各端点 handler 单一职责；复用既有 helper（企业归属/角色判断/ApiResponse 信封风格）；权限分层合理（读=归属 404、写=企业主/管理员 403、任务提交=责任人本人 403/422）；错误消息中文可读；无状态反模式/无裸 dict 响应。
3. **数据正确性**：任务提交的 items 归属校验（item 属于 task、task 属于企业）；result 枚举校验；转隐患时 abnormal 前置校验与字段预填正确；code 生成无并发/复用问题（说明取舍）；软删语义下列表/详情/生成是否过滤 enabled=False 的计划。
4. **测试质量**：53 个测试断言有效无空断言；mock db 风格与 `test_enterprise_org.py` 一致（async 测试带 `@pytest.mark.asyncio`）；主路径与边界（422/403/404）均有覆盖；测试未固化错误语义。
5. **无过度工程**：改动最小化，无无关抽象/依赖；main.py 挂载为最小改动（2 行）。
6. **无越界**：`git show 5af505b --stat` 恰 4 个清单文件，消息精确匹配「feat(hazard): plan, task and checklist item endpoints」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_plan_api.py -v`（预期 53 passed）
- `python -m pytest tests/ -q`（预期 688 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check 5af505b`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_03_review_quality --claim-id <claim_id> --exit-code 0 --summary "隐患计划/任务/清单项端点质量复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
