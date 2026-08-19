# Codex Custom Subagents task handoff v1

Task: task_hazard_09_fix_frontend_review_spec

## 目标

对任务 9 前端修复提交 `9af4cb3`（父 `c8dff5b`）做只读规格合规复审：核对未闭环 badge 在四个视图的渲染与规格 §11.1 一致。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`9af4cb3`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。
- 规格文档：`docs/superpowers/specs/2026-08-14-hazard-management-design.md`（重点 §11.1：展示位置=风险层级树/风险总览/风险告知卡 badge/管控清单）。

## 审查清单（逐项核验并给出证据）

1. **风险总览/层级树（RiskOverviewPage.tsx）**：分区行与风险点对象行 `open_hazard_count > 0` 渲染「未闭环 N」Badge；0/undefined 不渲染；OpenHazardBadge helper 复用。
2. **工作台（WorkbenchZonePanel.tsx）**：分区卡片名称旁 `typeof open_hazard_count === "number" && > 0` 时显示「未闭环 N」；新分区无字段不显示。
3. **告知卡（RiskNoticeCardPage.tsx）**：表格「隐患状态」列 `has_open_hazard === true` 显示「存在未闭环隐患」Badge、false 显示「—」。
4. **管控清单（RiskControlListPage.tsx）**：表格「未闭环隐患」列 `open_hazard_count > 0` 显示「未闭环 N」、否则「—」。
5. **规格一致性**：四处渲染与 §11.1 展示位置一致；文案中文可读；纯展示无后端/类型/service 改动。
6. **门禁**：tsc -b/eslint/vitest 111/后端 952 全绿；git show --check 干净。
7. **无越界**：`git show 9af4cb3 --stat` 恰 4 个清单文件，消息精确匹配「fix(hazard): render open hazard badges on risk views」，TASKS.md 未提交（项目惯例）。

## 验证命令

- `npx tsc -b` exit 0、`npx vitest run` 全绿、`npx eslint` 改动文件 exit 0
- `python -m pytest tests/ -q`（预期 952 passed）
- `git show --check 9af4cb3`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_09_fix_frontend_review_spec --claim-id <claim_id> --exit-code 0 --summary "风险视图未闭环badge规格复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
