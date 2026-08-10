# Codex Custom Subagents task handoff v1

Task: task_final_fix_frontend_review_spec

## 任务：规格合规审查——task_final_fix_frontend

你是代码审查子智能体。请核验前端收敛修复是否符合规格要求。只读 + 验证，不要修改任何文件。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul，HEAD 52e4c15）。

审查命令：cd 到 worktree 后 `git log c721578..HEAD --oneline` + 逐提交 `git show`，逐文件阅读实际代码。

### 规格要求（对照 docs/superpowers/specs/2026-08-08-usability-enhancement-design.md 6.1/6.3/6.4/10 节）

1. **6.3/6.4 导入 + 手动填写**：
   - 引导页步骤列表上方「📦 导入企业资料包」入口 → ImportDrawer 资料包模式（多文件一次 batch、分流到各步骤候选、不落库、步骤列表显示资料包标记）
   - 每数据步骤（1-5）右上角「✍️ 手动填写」常驻入口（复用现有录入表单，关闭后数据刷新 + completion invalidate）
   - 每数据步骤生成按钮旁「📄 导入现有数据」（单文件导入 → 候选区、来源标注、逐条核对）
   - ImportDrawer 质量：单文件走单文件接口（明确反馈，不假成功）、多文件一次 batch、module/source 归属保留
2. **10 危化品关联**：风险事件表单「关联危化品」下拉（可空、选项为企业危化品、payload 传 chemical_id、编辑回填、schema 同步）
3. **6.1 首企业自动引导**：创建前企业数为 0 时创建后跳 /onboarding?enterprise_id=，否则详情页；查询失败安全回退
4. **报告徽标刷新**：merge 后 invalidate 徽标查询 + completion

### 门禁

- `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
- `npx eslint` 改动文件不得新增 error（与 BASE 逐项对比）
- `git diff --check` 干净；diff 无 any

### 汇报格式

```
结论：PASS / FAIL（✅ 符合规格 / ❌ 需修复）
逐项核验：...
参考建议（非阻塞）：...
```

