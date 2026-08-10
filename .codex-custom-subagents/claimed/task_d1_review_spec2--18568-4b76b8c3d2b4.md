# Codex Custom Subagents task handoff v1

Task: task_d1_review_spec2

## 任务：规格合规复审——task_d1_fix

你是代码审查子智能体。上一轮 D-1 完成度卡片质量审查发现 2 项重要 + 次要问题，实现者已修复（提交 `65126c6`）。请复审修复是否到位、有无回归。只读 + 验证，不要修改任何文件。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。

审查命令：cd 到 worktree 后 `git diff 812fa9f..65126c6`，逐文件阅读实际代码。

### 复审重点（对照修复任务 task_d1_fix 的要求）

1. **完成度缓存失效**：移动端保存点是否都补了 `invalidateQueries(["completion", id])`？至少核对：EnterpriseEditScreen（更新/删除）、EnterpriseCreateScreen（创建后）、EnterpriseListScreen（删除后）、RiskAssessmentScreen/RiskSourceListScreen、ResourceInvestigationScreen/ResourceListScreen。key 是否正确（新建企业用新 id，删除用被删 id）？RiskManagementListScreen 纯只读不 invalidate 是否合理？
2. **组件一致性**：Dashboard 完成度卡片是否改用 ProgressBar/Chip/Button？色值是否统一走 `var(--color-primary-*)`/移动端 token 类，无 #1677ff/#d9d9d9/#fff7e6 等 antd 硬编码色？Chip 新增 warning 变体是否不破坏其他调用方？
3. **次要项**：loading 骨架屏、error 态（失败提示 + 重试）、切换企业防旧数据闪现是否实现？
4. **功能保持**：跳转逻辑不变（未完成→/m/enterprises/:id，完成→/m/plans/new?enterprise_id=）？staleTime 60s 未改？

### 门禁

- `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
- `npx eslint` 改动文件不得新增 error（与 BASE 812fa9f 逐项对比）
- `git diff --check` 干净；diff 无 any；提交仅相关文件、单提交

### 汇报格式

```
结论：PASS / FAIL（✅ 符合规格 / ❌ 需修复）
逐项核验：...
参考建议（非阻塞）：...
```

