# Codex Custom Subagents task handoff v1

Task: task_final_fix_misc_review

## 任务：复审——task_final_fix_misc（批次 3 杂项 5 提交）

你是代码审查子智能体。批次 3（移动端死导航 + 文案 + chroma 卫生 + 防抖 + 计划勾选）已实现（5 个提交）。请做合并复审（规格 + 质量合一，均为低风险杂项）。只读 + 验证，不要修改任何文件。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul，HEAD 4d1f273）。

审查命令：cd 到 worktree 后 `git log 893da34..HEAD --oneline` + 逐提交 `git show`，逐文件阅读实际代码。

### 复审重点

1. **移动端死导航（6360473）**：SettingsScreen 菜单 2 处 + 账户卡片 1 处路径改为 `/m/settings/profile`、`/m/settings/password`，与 routes.tsx 实际路由一致？无其他死链残留（rg "/m/profile|/m/change-password" frontend/src/mobile）？
2. **AIGenerateButton 文案（1cfc4f7）**：未配置提示改为「联系管理员」，移除 `/settings/ai-config` 跳转；无其他引用依赖旧行为；与规格 15 一致？
3. **chroma 卫生（c835d3e）**：`git rm --cached` 解除跟踪（本地文件保留）、`.gitignore` 规则正确（保留 README 说明）、提交不含二进制内容变更？`git ls-files` 确认 chroma_db 下已无跟踪二进制？
4. **搜索防抖（4b6b94e）**：PlanCardsPage 列表搜索 300ms 防抖（setTimeout ref 清理）、卡片视图过滤不受影响？
5. **计划勾选（4d1f273）**：只勾已实现项，未实现项保持未勾？
6. **门禁**：`cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0；eslint 改动文件不得新增 error；`git diff --check` 干净。

### 汇报格式

```
结论：PASS / FAIL（✅ 通过 / ❌ 需修复）
逐项核验：...
参考建议（非阻塞）：...
```

