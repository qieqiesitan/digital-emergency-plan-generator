# Codex Custom Subagents task handoff v1

Task: task_d3_remove_ai_config

## 任务：D-3 移除用户级 AI 模型配置

你是实现子智能体。请移除移动端用户级 AI 模型配置并提交。规格出处：`docs/superpowers/plans/2026-08-09-usability-mobile.md` 任务 D-3。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。必须 cd 到该目录操作，不要动主工作区。

### 交付内容

1. **修改 `frontend/src/mobile/routes.tsx`**
   - 删除 `{ path: "settings/ai-config", element: <AIModelConfigScreen /> }` 路由。
   - 删除 `const AIModelConfigScreen = lazy(() => import("@/mobile/screens/AIModelConfigScreen"));` 导入。
2. **删除文件 `frontend/src/mobile/screens/AIModelConfigScreen.tsx`**
3. **全仓确认无残留引用**：`rg -n "AIModelConfigScreen|ai-config|AI 模型配置" frontend/src` 应无相关残留（注意：后端 AI 配置接口与系统配置页不属于本任务范围，不要删；桌面端如有 AI 配置属 B1 已处理，不要动）。

### 质量门禁（必须全部通过）

1. `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
2. `npx eslint frontend/src/mobile/routes.tsx` 不得新增 error
3. `git diff --check` 干净
4. 单提交、提交信息 `chore(mobile): remove user-level AI model config screen`，只含上述 2 个文件的变更

### 提交

完成后 `git add -A frontend/src/mobile/routes.tsx frontend/src/mobile/screens/AIModelConfigScreen.tsx` + `git commit`，运行 complete 脚本，报告：改动文件清单 + 提交 SHA、rg 残留检查结果、门禁验证输出摘要。

