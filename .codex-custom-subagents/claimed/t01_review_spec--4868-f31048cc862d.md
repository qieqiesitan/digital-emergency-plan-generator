# Codex Custom Subagents task handoff v1

Task: t01_review_spec

## 任务：规格合规审查 —— 任务 1（platform.ts APP_BASE / stripAppBase）

你是一个规格合规审查子智能体。验证实现者是否构建了所要求的内容（不多不少）。**不要信任实现者的报告**，必须独立阅读实际代码逐项核对。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。相关提交：`23cf567`（`feat(deploy): add APP_BASE and stripAppBase for subpath deployment`），其父提交 `1fa1696`。

### 要求的内容（任务 1 规格）

1. 新建 `frontend/src/utils/platform.test.ts`，包含 4 项测试：
   - `stripAppBase("/m/login", "")` 原样返回；
   - `stripAppBase("/emergency-plan-migration/m/login", "/emergency-plan-migration")` 返回 `/m/login`；
   - `stripAppBase("/other/m/login", "/emergency-plan-migration")` 原样返回；
   - `typeof APP_BASE === "string"`。
2. `frontend/src/utils/platform.ts` 末尾追加：
   - `APP_BASE = import.meta.env.BASE_URL.replace(/\/+$/, "")`；
   - `stripAppBase(pathname, appBase = APP_BASE)`：`appBase` 为空原样返回；以 `appBase` 开头则 `slice(appBase.length)`，否则原样返回。
3. 提交只含上述 2 个文件，提交消息为 `feat(deploy): add APP_BASE and stripAppBase for subpath deployment`。
4. 门禁：`npx vitest run` 全量 52 passed（基线 48 + 新增 4）；`npx tsc -b` 退出码 0。

### 实现者声称

已完成 TDD：红灯（实现前 4 测试全失败）→ 绿灯（实现后 4 测试全过）；vitest 52 passed、tsc 0、eslint 0、`git diff --check` 干净、行宽 ≤85；提交 23cf567 仅含 2 文件，工作区干净。

### 你的工作

1. `cd` 到 worktree，`git show 23cf567 --stat` 确认提交范围；
2. 通读 `git show 23cf567` 全量 diff，逐项对照上述 4 项要求；
3. 运行 `cd frontend && npx vitest run src/utils/platform.test.ts` 确认 4 项测试真实存在且通过；
4. 检查是否有规格外的多余改动（多余功能、无关文件、过度工程化）。

### 汇报格式

- ✅ 符合规格（经代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失/多余/理解偏差，附带 file:line 引用]
