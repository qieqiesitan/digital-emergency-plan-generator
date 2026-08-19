# Codex Custom Subagents task handoff v1

Task: task_hazard_10_review_quality

## 目标

对隐患任务 10「隐患公示」提交 `e264815`（父 `25e3328`）做只读代码质量复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`e264815`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 审查清单（逐项核验并给出证据）

1. **路由层质量**：企业内公示/token/公开页 handler 单一职责；共享 helper（scope 口径、整改摘要、脱敏）复用无重复；错误消息中文可读；ApiResponse 信封一致；无状态反模式。
2. **数据正确性**：scope 字典合并（企业覆盖>系统默认）与兜底；整改摘要三态优先级正确（最近整改记录批量查询按 created_at DESC 取首条）；脱敏白名单字段无泄漏（责任人/联系方式/照片/位置/内部备注不出现）；token 生成 secrets 安全。
3. **公开页安全性**：免登录端点不暴露内部字段；404 语义（token 无效不区分存在性）；masked 标记。
4. **测试质量**：18 个测试断言有效无空断言；mock 风格一致（async 带 @pytest.mark.asyncio）；覆盖主路径/边界/权限/脱敏断言。
5. **无过度工程**：改动最小化；无无关抽象。
6. **无越界**：`git show e264815 --stat` 恰 3 个清单文件，消息精确匹配「feat(hazard): publicity page with desensitized public endpoint」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_publicity_api.py -v`（预期 18 passed）
- `python -m pytest tests/ -q`（预期 885 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check e264815`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_10_review_quality --claim-id <claim_id> --exit-code 0 --summary "隐患公示质量复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
