# Codex Custom Subagents task handoff v1

Task: task_onboarding_v2_review_quality

## 任务：代码质量审查——task_onboarding_v2_features（规格审查通过后）

你是代码质量审查子智能体。请审查引导页 4 项功能增强的代码质量。只读 + 验证，不要修改任何文件。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2`（master 分支，HEAD 390726c）。

审查命令：`git log 69f97da..HEAD --oneline` + 逐提交 `git show`，逐文件阅读实际代码。

### 审查重点

1. **StepOrg 成员编辑**：memberEdits 状态管理（group_key 稳定性、组件重挂载丢失？）、采纳时编辑值合并正确性、已采纳只读区渲染、与 adoptAll 交互、无副作用泄漏。
2. **回显**：listChemicals/listResources 挂载加载（queryKey/竞态/卸载 setState）、accepted 初始化与后续采纳合并（重复 id？）、取消采纳删除 id 正确性、Spin 态、失败降级。
3. **批量按钮**：CandidatesReview API 设计（回调返回 Promise）、loading 状态（全部采纳/取消各自独立）、失败不移动状态、全部采纳用批量接口后 id 重建 _key 的一致性、surrounding 清空语义（traffic_info 保留）。
4. **跳过完成**：OnboardingPage generate 步骤 onDone 分支、navigate 时机、localDone 标记、其他步骤行为无回归。
5. 类型/样式：无 any、无 >100 字符行、无未使用导入、组件使用与既有惯例一致、无死代码。

### 门禁

- `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
- `npx eslint src/pages/Onboarding` 不得新增 error（与 HEAD 69f97da 逐项对比）
- `git diff --check` 干净；diff 无 any

### 汇报格式

- 优点
- 问题（关键/重要/次要，带 file:line）
- 评估结论：✅ 通过 或 ❌ 需修复

