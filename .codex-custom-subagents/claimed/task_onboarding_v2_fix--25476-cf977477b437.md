# Codex Custom Subagents task handoff v1

Task: task_onboarding_v2_fix

## 任务：修复引导页批次 A 质量审查重要问题（StepOrg 单组采纳误删候选）

你是实现子智能体。引导页 4 项功能增强的质量审查发现 1 项重要功能缺陷，请修复并提交。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2`（master 分支，HEAD 390726c）。直接在主工作区修改提交。

### 问题描述

`StepOrg.tsx` 的 `adoptGroup`（约 :139-140）单组采纳会误删其他 AI 候选组：
- 后端 `generate_org_candidates` 只返回 `group_key/group_name/responsibilities/members`，**无 `_key`**，而 `generate()`（约 :112）未做归一化；
- `setCandidates(prev => prev.filter(x => x._key !== g._key))` 中 `g._key` 为 undefined，会把所有无 `_key` 的候选组一并移出——采纳一组后其余未保存的 AI 候选组全部消失，无法再编辑/采纳。

### 修法

`generate()` 中为每个候选组补 `_key`（如 `_key: group_key || group_name || imp-org-${ts}-${i}`，与 toOrgCandidates 的 fallback 一致），或改用 `group_key` 过滤。修后验证：采纳一组后其余候选组保留；adoptAll 行为不受影响；回显/取消采纳不回归。

### 质量门禁（必须全部通过）

1. `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
2. `npx eslint src/pages/Onboarding/StepOrg.tsx` 不得新增 error
3. `git diff --check` 干净；不得新增 `any`；新增代码无 >100 字符行
4. 单提交、提交信息如 `fix(onboarding): keep other org candidates after single group adopt`，只含相关文件

### 提交

完成后 `git add` + `git commit`，运行 complete 脚本，报告：改动文件清单 + 提交 SHA、修法简述、门禁验证输出摘要。

