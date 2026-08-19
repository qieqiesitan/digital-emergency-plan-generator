# Codex Custom Subagents task handoff v1

Task: task_hazard_14_review_quality

## 目标

对隐患任务 14「HazardPlanPage+HazardTaskPage」提交 `b572a59`（父 `cfd2cbd`）做只读代码质量复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`b572a59`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 审查清单（逐项核验并给出证据）

1. **页面结构**：HazardPlanPage 514 行/HazardTaskPage 508 行——组件分层清晰、状态管理合理（无状态反模式、eslint react-hooks 规则合规）；handler 单一职责；常量/类型提取；无重复逻辑。
2. **数据正确性**：责任人选择器 user_id 语义与后端校验一致（listMembers 过滤 enabled）；AI 采纳回填（weekly/custom 出现星期必填）；超期判断口径与后端 overdue 一致；转隐患交互顺序（先提交核对后转）与后端 to-record 语义一致；403/404 错误提示（extractDetail）。
3. **交互细节**：启用 Switch 软删语义（DELETE→enabled=false）；任务 done 后清单只读；照片上传/预览；超期时间刷新（每分钟）实现无 setState-in-effect 违规。
4. **门禁**：tsc -b/eslint/vitest/后端全量 pytest 全绿；git diff --check 干净。
5. **无过度工程**：改动最小化；无无关抽象。
6. **无越界**：`git show b572a59 --stat` 恰 3 个清单文件，消息精确匹配「feat(hazard): plan and task execution pages」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `npx tsc -b` exit 0、`npx vitest run` 全绿、`npx eslint` 改动文件 exit 0
- `python -m pytest tests/ -q`（预期 952 passed）
- `git show --check b572a59`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_14_review_quality --claim-id <claim_id> --exit-code 0 --summary "隐患计划任务页质量复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
