# Codex Custom Subagents task handoff v1

Task: task_07_fix_linkage

## 目标

按任务 7 质量/规格审查建议，让风险总览的层级树事件标签、风险统计饼图、拓扑图等级随「现有/固有」模式联动（固有数据缺失时回退现有），提交后复审。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，当前 HEAD=`50010f1`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 背景

任务 7 已让分布图/图例/矩阵随模式切换；`RiskOverviewPage` 的层级树（treeData）、`RiskOverviewStats` 统计饼图、拓扑图仍固定取现有等级。数据已就绪：`z.inherent_max_level`、`e.inherent_risk_level`（HierarchyEventResponse 已带）。本次让同一视图内全部等级展示一致。

## 文件

- 修改：`frontend/src/pages/Enterprise/RiskOverviewPage.tsx`
- 修改：`frontend/src/components/enterprise/RiskOverviewStats.tsx`
- 拓扑图组件（若在独立文件，如 `TopologySVG`/`RiskOverviewTopology`，一并修改；先读代码确认位置）

## 步骤

- [ ] **步骤 1：总览层级树随模式**（`RiskOverviewPage.tsx` treeData）

事件标签等级改为 `mode === "inherent" ? (e.inherent_risk_level ?? e.risk_level) : e.risk_level`；分区 Tag 等级改为 `mode === "inherent" ? (z.inherentMaxLevel ?? getMaxLevel(z)) : getMaxLevel(z)`（或 `getMaxLevel(z, mode)` 统一封装，选可读性更好的方式）。

- [ ] **步骤 2：风险统计随模式**（`RiskOverviewStats.tsx`）

饼图/计数的事件等级按 `mode` 取 `inherent_risk_level ?? risk_level`；组件新增 `mode?: "current" | "inherent"` 入参，`RiskOverviewPage` 传入。

- [ ] **步骤 3：拓扑图随模式**

`getMaxLevel`/事件等级渲染处按 `mode` 取固有（回退现有）；组件新增 mode 入参并透传。

- [ ] **步骤 4：门禁**

在 `frontend` 目录：`npx tsc -b`、`npx eslint`（改动文件）、`npx vitest run`，全部通过；`git diff --check` 干净。

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/pages/Enterprise/RiskOverviewPage.tsx frontend/src/components/enterprise/RiskOverviewStats.tsx <拓扑文件>
git commit -m "feat(risk): link tree, stats and topology levels to map mode"
```

不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_07_fix_linkage --claim-id <claim_id> --exit-code 0 --summary "总览树/统计/拓扑随模式联动完成"
```

最终回复报告：task_id、claim_id、commit SHA、门禁结果、改动文件列表。

## 规则

- 用 `apply_patch` 编辑；只改总览相关文件；阻塞时停下汇报。
