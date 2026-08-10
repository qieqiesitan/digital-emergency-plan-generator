# Codex Custom Subagents task handoff v1

Task: task_final_fix_frontend_review_quality

## 任务：代码质量审查——task_final_fix_frontend（规格审查通过后）

你是代码质量审查子智能体。请审查前端收敛修复的代码质量。只读 + 验证，不要修改任何文件。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul，HEAD 52e4c15）。

审查命令：cd 到 worktree 后 `git log c721578..HEAD --oneline` + 逐提交 `git show`，逐文件阅读实际代码（重点 ImportDrawer/OnboardingPage/各步骤组件/RiskEventForm）。

### 审查重点

1. **ImportDrawer**：package/single 两模式逻辑正确性（batch 一次请求、单文件反馈、错误处理收敛、module/source 归属、_key 稳定性）；上传状态/loading/清空交互；无假成功提示。
2. **候选分流**：importedByStep 状态设计（父级持有 → 各步骤渲染期合并），采纳/删除回传一致性（_key 匹配、全部消费后标记消失）；与 AI 候选、已采纳区三者关系无冲突；无 setState-in-render/effect 循环。
3. **手动填写抽屉**：5 步骤复用表单的正确性（表单是否真实复用、保存后 invalidate 是否齐全、抽屉打开/关闭状态管理）；Org/Surrounding 复用 Modal 是否合理。
4. **危化品关联**：Select 数据源（listChemicals 查询）、payload chemical_id 传参（create/update）、编辑回填、清空（allowClear → null）语义；后端 schema 同步（chemical_id 可空）与既有校验兼容。
5. **首企业自动引导**：企业数判断（page_size=1 查询）、竞态（创建后列表刷新）、失败回退；无重复跳转。
6. **徽标刷新**：invalidate key 正确、与 completion invalidate 协调。
7. 类型/样式/回归：无 any、无 >100 字符行、组件使用与既有惯例一致、无死代码/未使用导入。

### 门禁

- `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
- `npx eslint` 改动文件不得新增 error（与 BASE 逐项对比）
- `git diff --check` 干净；diff 无 any

### 汇报格式

- 优点
- 问题（关键/重要/次要，带 file:line）
- 评估结论：✅ 通过 或 ❌ 需修复

