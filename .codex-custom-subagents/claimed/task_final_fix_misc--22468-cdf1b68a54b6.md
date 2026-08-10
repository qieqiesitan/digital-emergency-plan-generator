# Codex Custom Subagents task handoff v1

Task: task_final_fix_misc

## 任务：最终收敛·批次 3（移动端死导航 + 杂项文案 + 仓库卫生 + 计划勾选）

你是实现子智能体。最终整体审查发现 5 项移动端/杂项/卫生问题，请修复并提交。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul，HEAD 52e4c15）。必须 cd 到该目录操作，不要动主工作区。

### 修复项

**1. 移动端 SettingsScreen 死导航（修复）**
- `frontend/src/mobile/screens/SettingsScreen.tsx`：菜单与账户卡片指向 `/m/profile`、`/m/change-password`，但实际路由是 `/m/settings/profile`、`/m/settings/password`（mobile/routes.tsx），点击落入兜底跳回工作台。改为正确路径（MENU_ITEMS 两处 + 账户卡片 navigate 一处）。

**2. 桌面端 AIGenerateButton「去配置」文案（修复）**
- `frontend/src/components/plan/AIGenerateButton.tsx`：AI 未配置时的 Modal okText「去配置」+ 跳转 `/settings/ai-config` 已是死分支（AI 配置已全局化为管理员配置，普通用户无该页权限）。改为「联系管理员」提示（okText 或文案改为请管理员配置，移除跳转或改为提示弹窗），与规格 15「AI 未配置 → 禁用 + 联系管理员提示」一致。改动前后确认无其他引用依赖旧行为。

**3. chroma.sqlite3 分支卫生（修复）**
- `backend/app/regulations/data/chroma_db/` 下二进制（chroma.sqlite3、*.bin/*.pickle 等）被 git 误跟踪。处理：`git rm --cached` 这些文件（保留本地文件）、`.gitignore` 增加 `backend/app/regulations/data/chroma_db/` 规则（注意保留目录占位或说明）。提交信息如 `chore: untrack chroma db binaries`。不要删除任何实际数据文件。
- 注意：chroma.sqlite3 当前有未暂存改动（本地数据库），`git rm --cached` 后工作区该文件保持原样即可。

**4. PlanCardsPage 列表视图搜索防抖（顺手修复）**
- `frontend/src/pages/Plan/PlanCardsPage.tsx` 列表视图 listSearch 每击键发请求。加轻量防抖（300ms，可用 useDeferredValue 或简单 setTimeout ref），避免每击键请求；卡片视图过滤逻辑不受影响。

**5. 计划文档 checkbox 勾选（流程卫生）**
- 6 份计划文件（docs/superpowers/plans/2026-08-09-usability-*.md）中已落地任务的 `- [ ]` 勾为 `- [x]`。只勾选确实已实现的项，未实现的（如「后端模糊去重兜底」）保持不勾。

### 质量门禁（必须全部通过）

1. `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
2. `npx eslint` 改动文件不得新增 error（与 BASE 52e4c15 逐项对比）
3. `git diff --check` 干净；改动文件不得新增 `any`；新增代码无 >100 字符行
4. 按修复项拆 1-5 个逻辑提交均可（信息清晰），只含相关文件；chroma 卫生提交不得包含 chroma.sqlite3 内容变更

### 提交

完成后 `git add` + `git commit`，运行 complete 脚本，报告：改动文件清单 + 提交 SHA、每项修法简述、门禁验证输出摘要。

