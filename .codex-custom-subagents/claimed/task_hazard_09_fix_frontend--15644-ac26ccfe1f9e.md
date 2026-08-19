# Codex Custom Subagents task handoff v1

Task: task_hazard_09_fix_frontend

## 目标

修复最终整体审查发现的缺口：任务 9「派生联动+四色图叠加」的前端 badge 未渲染。后端派生字段（`open_hazard_count`/`has_open_hazard`）与前端类型已就绪，需在页面组件中消费展示（规格 §11.1「展示位置：风险层级树、风险总览、风险告知卡 badge、管控清单」+ 计划任务 9「工作台分区 badge 显示未闭环数」）。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`c8dff5b`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 修复清单（4 处渲染，字段均已存在于类型）

1. **风险总览/层级树（`frontend/src/pages/Enterprise/RiskOverviewPage.tsx`）**：风险点/分区行展示未闭环 badge（`open_hazard_count > 0` 时显示红色/橙色 Badge「未闭环 N」或类似，0 时不显示；分区级已有 `open_hazard_count` 字段）。
2. **工作台（`frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx`）**：分区 badge 显示未闭环数（`WorkbenchZone.open_hazard_count`，>0 时展示）。
3. **告知卡（`frontend/src/pages/Enterprise/RiskNoticeCardPage.tsx`）**：卡片/列表「存在未闭环隐患」badge（`has_open_hazard === true` 时展示，规格 §11.1「风险告知卡（存在未闭环隐患）badge」）。
4. **管控清单（`frontend/src/pages/Enterprise/RiskControlListPage.tsx`）**：行内展示 `open_hazard_count`（>0 时 badge）。

实现要求：
- 复用 antd `Badge`/`Tag`，样式与既有页面一致；中文文案（「未闭环 N」「存在未闭环隐患」等）；0/undefined 不渲染；
- 纯展示改动，不改后端、不改类型、不改 service；
- 跑门禁：`npx tsc -b`、`npx eslint` 改动文件、`npx vitest run`、`git diff --check`、后端全量 pytest 无回归。

## Commit

```bash
git add frontend/src/pages/Enterprise/RiskOverviewPage.tsx frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx frontend/src/pages/Enterprise/RiskNoticeCardPage.tsx frontend/src/pages/Enterprise/RiskControlListPage.tsx
git commit -m "fix(hazard): render open hazard badges on risk views"
```

按实际改动文件调整 add 列表；不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_09_fix_frontend --claim-id <claim_id> --exit-code 0 --summary "风险视图未闭环badge渲染完成"
```

最终回复报告：task_id、claim_id、commit SHA、改动文件清单、门禁结果、每处渲染位置与条件说明、git diff --check 结果。

## 规则

- 用 `apply_patch` 编辑；范围限制在任务文件所述文件（4 个页面，若某页面无对应展示位置可在报告中说明取舍）；阻塞时停下汇报。
- 全程用简体中文交流；代码注释/变量名可用英文。
