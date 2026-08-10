# Codex Custom Subagents task handoff v1

Task: task_final_fix_frontend2

## 任务：修复批次 2 前端质量审查 2 项重要问题

你是实现子智能体。批次 2 前端收敛修复的质量审查发现 2 项重要问题，请修复并提交。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul，HEAD 52e4c15）。必须 cd 到该目录操作，不要动主工作区。

### 审查发现（必须修复）

**重要 1：包导入同模块多结果 `_key` 碰撞（OnboardingPage.tsx 约 :71）**
- 后端 batch 按「每文件×每模块」返回多个 ImportResult，同一模块出现多个结果（如两份企业信息文档）时，`imp-${stepKey}-${Date.now()}-${i}` 中 `i` 每 result 重新计数、Date.now() 一次调用内恒定 → 两文件的首条候选 `_key` 完全相同。后果：React 重复 key 告警，且采纳/删除按 `_key` 过滤会一次性移除两条（未保存那条静默消失）。
- 修法：key 生成加入全局递增计数或 result 序号（如模块内遍历序号 + 每个 ImportResult 的 index），保证跨 result 唯一。修后核对各步骤候选采纳/删除按 _key 过滤逻辑不再误删。

**重要 2：batch skipped 统计错误（ImportDrawer.tsx 约 :51）**
- `skipped = files.length - results.length` 假设 1 文件=1 结果，但单文件可识别出多模块（skipped 变负数，显示「-1 个文件未识别模块已跳过」），或文件被跳过时漏报。
- 修法：按 `Set(source)`（结果中的来源文件名集合）计算实际识别文件数，skipped = 上传文件数 - 识别文件数；文案保证非负且准确。

**顺手（低成本，可一并修）**
- ImportDrawer warning（0 候选/未识别）路径也 `onClose()` 导致需重开抽屉换文件重试 → warning 时保持抽屉打开（或提供「重试」而非直接关闭）。
- ImportDrawer fileList 抽屉重开残留上次文件 → 打开抽屉时清空受控 fileList。

### 质量门禁（必须全部通过）

1. `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
2. `npx eslint` 改动文件不得新增 error（与 BASE 52e4c15 逐项对比）
3. `git diff --check` 干净；改动文件不得新增 `any`；新增代码无 >100 字符行
4. 单提交、提交信息如 `fix(onboarding): unique import candidate keys and accurate skip stats`，只含相关文件

### 提交

完成后 `git add` + `git commit`，运行 complete 脚本，报告：改动文件清单 + 提交 SHA、修法简述、门禁验证输出摘要。

