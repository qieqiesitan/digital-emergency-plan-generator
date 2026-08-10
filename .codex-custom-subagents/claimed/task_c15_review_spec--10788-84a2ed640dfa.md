# Codex Custom Subagents task handoff v1

Task: task_c15_review_spec

## 任务：规格合规审查——task_c15_steps_3_6

你是一个规格合规审查子智能体。目的：验证实现者是否构建了所要求的内容（不多不少）。关键：不要信任实现者的报告，必须独立阅读实际代码验证。

### 实现位置

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。审查提交 `fdc93b8`：

git show fdc93b8 --stat 与 git show fdc93b8

### 要求的内容（任务 C1-5 原文摘要）

1. StepRiskChemical：generateChemicalsAI 生成候选 → CandidatesReview → createChemical 采纳写入 + completion 刷新。
2. StepResources：generateResourcesAI 生成 → batchCreateResources 写入。
3. StepSurrounding：高德 searchAmapSurrounding（预览勾选直接导入 updateSurrounding）+ AI generateSurroundingAI 候选核对。
4. StepGenerate：类型选择 → 跳转 /plans/new?type=&enterprise_id=。
5. tsc + eslint 通过（无 any）。
6. Commit：feat(onboarding): steps 3-6 (risk/chemical, resources, surrounding, generate)。

### 实现者声称构建了什么

- 4 文件 +414/-28（第 3-6 步替换占位）
- 第 5 步复用 AmapSearchResultModal / SurroundingAIGenerateModal（现有组件）
- tsc + eslint 通过，无 any
- 自审：采纳写入可用；高德无坐标时透出 400 提示；第 6 步参数与 PlanCreatePage 一致

### 你的工作

阅读实际代码验证：四步与要求一致？第 5 步双路径正确（高德直接导入 + AI 候选）？候选写入调用正确（createChemical/batchCreateResources/updateSurrounding）？completion 刷新？无 any？只改 Onboarding 4 文件？

### 汇报格式

- ✅ 符合规格（如果经过代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失或多余的内容，附带 file:line 引用]
