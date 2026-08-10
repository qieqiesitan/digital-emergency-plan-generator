# Codex Custom Subagents task handoff v1

Task: task_onboarding_v2_features

## 任务：引导页 4 项功能增强（姓名电话补充/步骤回显/批量采纳/跳过完成）

你是实现子智能体。用户使用引导页后提出 4 项功能需求，请实现并提交。涉及文件主要在 `frontend/src/pages/Onboarding/`。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2`（主工作区，master 分支，HEAD 69f97da）。直接在主工作区修改并提交（Docker 前端挂载本地 src，热更新即时生效）。不要动 worktree（已删除）。

### 需求 1：组织架构候选核对时内联补充姓名/电话

`StepOrg.tsx` 组织架构 AI 生成候选后，成员姓名/电话为空（设计原则：姓名电话人工填）。当前候选核对只能展示，用户希望**直接在引导候选区补充姓名电话**，采纳时保存。

实现要求：
- 候选区每个组的成员列表中，姓名、电话用可编辑输入框展示（默认空/原值），用户可直接输入；
- 采纳（单组采纳/adoptAll）时把编辑后的 members（含姓名电话）随组保存到 org_structure（updateOrgStructure）；
- 已采纳区保持只读展示已保存的姓名电话；
- 编辑状态本地维护（候选卡片内 useState 或受控组件均可），不阻塞生成/采纳流程；改动小优先，不要重构现有组织结构编辑逻辑。

### 需求 2：步骤回显（返回上一步能看到已确认内容）

根因：`StepRiskChemical`/`StepResources`/`StepSurrounding` 的 accepted 是**组件内部 useState**，OnboardingPage 用 `STEPS[current]` 条件渲染，步骤切换即卸载组件、state 丢失；返回该步骤时 accepted 为空（虽然后端已保存）。

实现要求：
- 三个步骤组件**挂载时从后端加载已保存数据**，初始化到已采纳区：
  - StepRiskChemical：现有 hazardousChemicalService.listChemicals(enterpriseId)（确认函数名）→ accepted
  - StepResources：resources 列表接口（内部资源+外部救援，确认现有 service/接口）→ accepted
  - StepSurrounding：surrounding GET（周边单位/敏感目标，确认现有 service/接口）→ accepted
- 加载期间给 loading 态；加载失败静默降级（不影响使用，可 toast 提示一次）；
- 已采纳区数据结构与现有 renderItem/accepted 消费一致（不要破坏采纳/删除逻辑）；
- StepOrg（enterprise.org_structure）与 StepEnterprise 已有回显，不需要改。

### 需求 3：候选区「全部采纳」+ 已采纳区「全部取消采纳」

`CandidatesReview.tsx`（StepRiskChemical/StepResources/StepSurrounding 共用）扩展：
- 新增候选区顶部「全部采纳」按钮：遍历 candidates 全部采纳（复用各步骤现有单条采纳逻辑或批量保存接口——优先批量接口如 batchCreateChemicals/batchCreateResources，若语义不一致则逐个 await 采纳，按钮 loading 态）；
- 已采纳区顶部「全部取消采纳」按钮：遍历 accepted 逐个取消。**取消采纳语义 = 删除已保存数据 + 移回候选区**（可重新编辑再采纳），需要各步骤传入「取消采纳」回调（删除接口：化学品/资源 DELETE 对应 id，周边按现有删除/清空语义）；
- 组织架构步骤（StepOrg 自定义候选渲染，不走 CandidatesReview）如能低成本复用同样加「全部采纳/全部取消采纳」，否则在任务报告说明取舍；
- 按钮在操作中 loading、防重复提交；操作失败提示并保持原状态。

### 需求 4：生成预案步骤加「跳过生成预案，完成引导」

`StepGenerate.tsx` 底部按钮区增加「跳过生成预案，完成引导」按钮（次级样式），点击调用 `onDone` 完成引导；`OnboardingPage` 需处理：第 6 步 onDone 时标记 generate 步骤完成 + 结束引导跳转（navigate 到 `/dashboard` 或企业详情页，选更合理的），而不是 current+1 越界。现有「现在生成预案」按钮保持不动。StepGenerate 现有 onDone prop 未使用，接上即可。

### 质量门禁（必须全部通过）

1. `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
2. `npx eslint` 改动文件不得新增 error（与 HEAD 69f97da 逐项对比）
3. `git diff --check` 干净；改动文件不得新增 `any`；新增代码无 >100 字符行
4. 按需求拆 1-4 个逻辑提交均可（信息清晰），只含相关文件

### 提交

完成后 `git add` + `git commit`，运行 complete 脚本（`python complete.py --workspace .`，任务目录 `C:\Users\55061\Documents\数字化预案自动生成 2\.codex-custom-subagents`），报告：改动文件清单 + 提交 SHA、每项实现要点（含批量接口/删除接口的选择与依据）、门禁验证输出摘要。

