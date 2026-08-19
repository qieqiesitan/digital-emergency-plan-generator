# Codex Custom Subagents task handoff v1

Task: task_hazard_09_fix_frontend_review_quality

## 目标

对任务 9 前端修复提交 `9af4cb3`（父 `c8dff5b`）做只读代码质量复审。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`9af4cb3`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 审查清单（逐项核验并给出证据）

1. **渲染正确性**：四处的条件判断（>0/===true/0/undefined 分支）正确；Badge 语义（未闭环 N/存在未闭环隐患）准确；0/undefined 不渲染无空状态污染。
2. **代码质量**：OpenHazardBadge helper 复用合理；改动最小化（32+/7-）；与既有页面样式/惯例一致；无类型断言滥用（typeof 守卫必要且正确）。
3. **无回归**：表格新增列不破坏既有列/排序/分页逻辑；树节点 badge 不影响展开折叠；eslint react-hooks 合规。
4. **门禁**：tsc -b/eslint/vitest/后端全量 pytest 全绿；git diff --check 干净。
5. **无越界**：`git show 9af4cb3 --stat` 恰 4 个清单文件，消息精确匹配「fix(hazard): render open hazard badges on risk views」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `npx tsc -b` exit 0、`npx vitest run` 全绿、`npx eslint` 改动文件 exit 0
- `python -m pytest tests/ -q`（预期 952 passed）
- `git show --check 9af4cb3`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_09_fix_frontend_review_quality --claim-id <claim_id> --exit-code 0 --summary "风险视图未闭环badge质量复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
