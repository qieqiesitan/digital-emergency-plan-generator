# Codex Custom Subagents task handoff v1

Task: task_hazard_11_review_quality

## 目标

对隐患任务 11「驾驶舱+台账/监管导出」提交 `2e4238b`（父 `e264815`）做只读代码质量复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`2e4238b`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 审查清单（逐项核验并给出证据）

1. **服务层结构**：`hazard_export_service.py` 220 行 openpyxl 纯函数（台账 3 sheet 构建/监管脱敏构建/部门名推导）职责单一、无 HTTP/响应组装、无重复逻辑；docstring 说明口径。
2. **路由层质量**：dashboard/ledger/report 三端点 handler 单一职责；复用 _get_ent/ApiResponse；统计逻辑清晰（指标聚合查询无 N+1 明显问题，报告实现）；错误消息中文可读。
3. **数据正确性**：及时率/周期/环比公式正确且分母 0 处理；超期数双口径（记录+任务）说明；未读数 total/mine/by_type；导出列与模型字段一致；监管脱敏无泄漏（责任单位推导不暴露责任人姓名）。
4. **测试质量**：19 个测试断言有效无空断言；mock 风格一致（async 带 @pytest.mark.asyncio）；覆盖统计口径/导出内容/脱敏/未读数/权限。
5. **无过度工程**：改动最小化；无无关抽象。
6. **无越界**：`git show 2e4238b --stat` 恰 3 个清单文件，消息精确匹配「feat(hazard): dashboard stats and ledger/report export」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_dashboard_api.py -v`（预期 19 passed）
- `python -m pytest tests/ -q`（预期 904 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check 2e4238b`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_11_review_quality --claim-id <claim_id> --exit-code 0 --summary "隐患驾驶舱导出质量复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
