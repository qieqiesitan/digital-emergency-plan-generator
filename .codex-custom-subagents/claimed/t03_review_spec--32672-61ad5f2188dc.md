# Codex Custom Subagents task handoff v1

Task: t03_review_spec

## 任务：规格合规审查 —— 任务 3（路由 basename）

你是一个规格合规审查子智能体。验证实现者是否构建了所要求的内容（不多不少）。**不要信任实现者的报告**，必须独立阅读实际代码逐项核对。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。相关提交：`3c1dca4`（`feat(deploy): add router basename for desktop and mobile`），父提交 `b77ad77`。

### 要求的内容（任务 3 规格）

1. `frontend/src/routes/index.tsx`：import 区新增 `import { APP_BASE } from "@/utils/platform";`；`createBrowserRouter([...])` 收尾改为 `], { basename: APP_BASE || undefined });`；`MobileRedirect`（`window.location.replace(pathname + search)`）保持不动；
2. `frontend/src/mobile/routes.tsx`：同样新增 import；文件末尾 `]);` 改为 `], { basename: APP_BASE || undefined });`；
3. 提交只含上述 2 个文件，提交消息精确匹配；
4. 门禁：`npx tsc -b` 0、`npx vitest run` 52 passed、eslint 无新增 error。

### 实现者声称

两文件按规格修改；mobile/routes.tsx 带 UTF-8 BOM，import 插在第 2 行（第 1 行后）；提交 3c1dca4 仅 2 文件（4+/2-）；tsc 0、vitest 52、eslint 23 个 error 均为基线既有（react-refresh/only-export-components），无新增。

### 你的工作

1. `git show 3c1dca4 --stat` 确认提交范围；
2. 通读 `git show 3c1dca4` 全量 diff，逐项对照上述要求（含 BOM 处理是否保留原文件编码、import 位置是否有效）；
3. 运行 `cd frontend && npx tsc -b`、`npx vitest run` 确认门禁；
4. 检查是否有规格外改动。

### 汇报格式

- ✅ 符合规格（经代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失/多余/理解偏差，附带 file:line 引用]
