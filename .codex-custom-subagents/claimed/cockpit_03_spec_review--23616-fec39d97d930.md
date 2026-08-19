# Codex Custom Subagents task handoff v1

Task: cockpit_03_spec_review

你正在审查「企业驾驶舱」任务 3 的实现是否与其规格匹配（规格合规性审查，只读，不修改代码）。

## 要求的内容（任务 3 规格）

1. 新建 `frontend/src/types/cockpit.ts`：9 个接口（RiskCounts/TopRisk/ZoneRisk/CockpitTodo/CompletionModule/CockpitCompletion/ActivityItem/HazardCounts/CockpitSummary），字段与后端 `backend/app/schemas/enterprise_cockpit.py` 一一对应；TopRisk.score 为 number | null；CockpitTodo.priority 为 "high"|"medium"|"low"；**本任务不含 RISK_LEVEL_COLORS 常量**（留给任务 5）。
2. 新建 `frontend/src/services/cockpitService.ts`：`getCockpitSummary(enterpriseId)` 箭头函数 + `.then(r => r.data.data)` 解包，GET `/enterprises/${enterpriseId}/cockpit-summary`。
3. 新建 `frontend/src/services/cockpitService.test.ts`：vi.mock("@/services/api")，断言 URL 与解包结果。
4. Commit：`feat(cockpit): cockpit summary frontend service`；只改这 3 个文件；不提交 TASKS.md。

## 实现者声称构建了什么
- 状态 DONE；commit 1b44b1f；目标测试 1 passed；全量 vitest 127 passed；tsc exit 0。

## 关键：不要信任报告

独立验证（只读）：

- 工作目录：C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit；`git show 1b44b1f --stat` / 直接读文件核验；
- 逐项比对：类型字段与后端 schema（可读 `backend/app/schemas/enterprise_cockpit.py` 对照）、service 解包方式与项目惯例（对照 `frontend/src/services/dataDictService.ts`）、测试是否真实断言；
- 检查是否有多余内容（尤其是否误加 RISK_LEVEL_COLORS）；
- 实际运行（工作目录 worktree\frontend）：
  - `npx vitest run src/services/cockpitService.test.ts`
  - `npx tsc -b`
- 检查提交只含 3 个目标文件、无 TASKS.md。

## 输出格式
- ✅ 符合规格（经代码检查后一切匹配），或
- ❌ 发现问题：[具体列出缺失/多余/偏差，附 file:line 引用]

## 汇报格式
- 状态：DONE | BLOCKED | NEEDS_CONTEXT
- 结论与依据（测试输出、git show 核验、发现的任何问题）
