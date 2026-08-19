# Codex Custom Subagents task handoff v1

Task: cockpit_08_spec_review

你正在审查「企业驾驶舱」任务 8 的实现是否与其规格匹配（规格合规性审查，只读，不修改代码）。

## 要求的内容（任务 8 规格）

1. `frontend/src/routes/index.tsx`：
   - import 替换：EnterpriseDetailPage → EnterpriseCockpitPage / EnterpriseModulePage / ModulePageShell / RiskManagementTab / HazardInspectionTab / riskNavGroups + hazardNavGroups；顶部加 useParams；
   - 辅助组件 RiskRedirect（objectId/methodId 后缀）、RiskManagementRoute（embedded 风险树）、HazardLedgerRoute（embedded 台账）；
   - `/enterprises/:id` → EnterpriseCockpitPage；新增 `/enterprises/:id/modules/:moduleKey` → EnterpriseModulePage；
   - `/enterprises/:id/risk-management` 壳路由（ModulePageShell title=风险分级管控 groups=riskNavGroups）子路由：index=RiskManagementRoute、overview/workbench/control-list/notice-cards/notice-cards/:objectId/publicity/methods/methods/:methodId/data-dicts；
   - `/enterprises/:id/hazard` 壳路由（ModulePageShell title=隐患排查治理 groups=hazardNavGroups）子路由：index=HazardLedgerRoute、plans/tasks/templates/dashboard/publicity/records/:rid；
   - 旧路径重定向（RiskRedirect）：data-dicts、risk-overview、risk-mapping-workbench、risk-control-list、risk-publicity、risk-notice-cards(+:objectId)、risk-methods(+:methodId)；
   - 保留 org / edit / preview / /enterprises/:enterprise_id/plans / 预案与公开页路由；原隐患平级 6 条路由删除；
   - 删除 `frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx`，全仓无引用。
2. Commit：`feat(cockpit): restructure enterprise routes to cockpit and module shells`；只改这 2 个文件；不提交 TASKS.md。

## 实现者声称构建了什么
- 状态 DONE；commit 3b2164a（父 441fe4c）；routes/index.tsx 68+/19- + EnterpriseDetailPage.tsx 删除 259 行；tsc/eslint/vitest 全绿；为 3 个新组件补了 react-refresh 豁免注释（与既有 MobileRedirect 惯例一致）。

## 关键：不要信任报告

独立验证（只读）：

- 工作目录：C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit；`git show 3b2164a` / 直接读 routes/index.tsx 核验；
- 逐项核验上面清单：每个路由条目存在且 element 正确；旧隐患平级路由确实删除；重定向路径正确（含 :objectId/:methodId 后缀拼接）；无重复/冲突路由；
- `rg "EnterpriseDetailPage" frontend/src` 无命中；
- 检查是否有多余内容或范围外改动；
- 实际运行（工作目录 worktree\frontend）：
  - `npx tsc -b`
  - `npx eslint src/routes/index.tsx`
  - `npx vitest run`
- 检查提交只含 2 个文件（routes/index.tsx 修改 + EnterpriseDetailPage.tsx 删除）、无 TASKS.md。

## 输出格式
- ✅ 符合规格（经代码检查后一切匹配），或
- ❌ 发现问题：[具体列出缺失/多余/偏差，附 file:line 引用]

## 汇报格式
- 状态：DONE | BLOCKED | NEEDS_CONTEXT
- 结论与依据（检查输出、git show 核验、发现的任何问题）
