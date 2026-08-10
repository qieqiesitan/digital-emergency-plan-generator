# Codex Custom Subagents task handoff v1

Task: task_final_fix_frontend

## 任务：最终收敛·批次 2（前端引导/风险接线 4 项）

你是实现子智能体。最终整体审查发现 4 个前端缺口/遗留，请修复并提交。规格出处：`docs/superpowers/specs/2026-08-08-usability-enhancement-design.md`。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul，HEAD 2f3a2f0）。必须 cd 到该目录操作，不要动主工作区。

### 修复项

**1. 规格 6.3/6.4 引导页导入 + 手动填写入口接线（核心）**
- 现有 `ImportDrawer.tsx`（frontend/src/pages/Onboarding/）全仓无引用方。先通读：ImportDrawer、OnboardingPage、各步骤组件（StepEnterprise/StepOrg/StepRiskChemical/StepResources/StepSurrounding）、onboardingService（import/batch 接口）、后端 onboarding.py 的 import 单文件与 batch 语义。
- 接线要求：
  a) 引导页步骤列表上方加「📦 导入企业资料包」独立入口（可选），打开 ImportDrawer 资料包模式：一次多文件 → 后端 batch 分流 → 候选按模块落到各步骤候选区（各步骤「新增候选」区展示，标注来源）。分流结果不落库。
  b) 每个数据步骤（1-5）右上角常驻「✍️ 手动填写」入口：复用该步骤对应录入表单（组织架构编辑器/危化品表/资源表/周边环境/企业信息），填完关闭后数据总览刷新（invalidate 对应查询 + completion）。
  c) 每个数据步骤生成按钮旁加「📄 导入现有数据」入口：单文件导入 → 解析 → 候选区展示（来源文件名+行号），逐条核对。
- ImportDrawer 本身质量修复（审查 C1-6 记录）：单文件也走 batch 会静默 skip 致「已提取 0 条」假成功 → 单文件走单文件导入接口并明确反馈；多文件才走 batch 且一次请求（不要逐文件 N 次并发）；保留 module/source 归属；错误分支清理冗余。
- 完成后 `rg "ImportDrawer"` 应至少 1 处真实挂载点（引导页）。

**2. 规格 10 风险事件表单危化品关联下拉**
- 后端已有 `risk_events.chemical_id` + schema/路由校验。前端 `RiskManagementTab.tsx` 事件表单（约 :243 payload）加「关联危化品」下拉：选项为当前企业危化品列表（HazardousChemical，查现有 service），可空；payload 传 chemical_id。保存后完成度 risk_chemical 模块「已关联」判定可达。
- 引导第 3 步（StepRiskChemical）已采纳危化品后，如规格允许可在 UI 提示「可在风险分级管控中关联危化品」（若实现成本低可加，否则仅桌面端下拉即可，任务内说明取舍）。

**3. 规格 6.1 创建第一个企业后自动进入引导**
- `EnterpriseCreatePage.tsx`（或对应创建成功回调）onSuccess 后跳转：若为「第一个企业」（创建前企业列表为空/新用户场景，读代码确定可行判断）跳 `/onboarding?enterprise_id=<newId>`，否则维持跳详情页。若前端无法可靠判断「第一个」，读取规格原文按最接近意图实现并说明。

**4. 报告徽标同窗不刷新**
- `RiskAssessmentTab.tsx` / `ResourceInvestigationTab.tsx` merge 报告后仅 loadReport，未 invalidate 徽标查询（`["enterprise", id, "risk-assessment"]` 等）。补 invalidate 使徽标状态同窗刷新。

### 质量门禁（必须全部通过）

1. `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
2. `npx eslint` 改动文件不得新增 error（与 BASE 2f3a2f0 逐项对比）
3. `git diff --check` 干净；改动文件不得新增 `any`；新增代码无 >100 字符行
4. 单提交或按修复项拆 2-4 个逻辑提交均可（信息清晰），只含相关文件

### 提交

完成后 `git add` + `git commit`，运行 complete 脚本，报告：改动文件清单 + 提交 SHA、每项修法简述（含 ImportDrawer 接线方式与手动填写抽屉复用策略）、门禁验证输出摘要。

