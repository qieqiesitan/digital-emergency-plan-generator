# Codex Custom Subagents task handoff v1

Task: t02_review_spec

## 任务：规格合规审查 —— 任务 2（vite.config.ts 参数化 base 与 PWA manifest）

你是一个规格合规审查子智能体。验证实现者是否构建了所要求的内容（不多不少）。**不要信任实现者的报告**，必须独立阅读实际代码逐项核对。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。相关提交：`b77ad77`（`feat(deploy): parameterize vite base and PWA manifest via VITE_BASE_PATH`），父提交 `23cf567`。

### 要求的内容（任务 2 规格）

只改 `frontend/vite.config.ts` 一个文件：
1. 在 `const API_TARGET = ...` 之后新增 `const BASE_PATH = (process.env.VITE_BASE_PATH || "").replace(/\/+$/, "");`；
2. PWA manifest：`start_url` 改为 `BASE_PATH ? \`${BASE_PATH}/m/dashboard\` : "/m/dashboard"`，并新增 `scope: BASE_PATH ? \`${BASE_PATH}/\` : "/"`；
3. `defineConfig` 内 `plugins` 之前新增 `base: BASE_PATH ? \`${BASE_PATH}/\` : "/"`；
4. 提交只含 `frontend/vite.config.ts`，提交消息精确匹配；不设 `VITE_BASE_PATH` 时构建产物资源引用无前缀（base 仍为 `/`）。

### 实现者声称

按三步完成（6+/1-），tsc 0、eslint 无新增 error、默认构建产物 `/assets/...` 无前缀、vitest 52 passed、提交 b77ad77 仅 1 文件。疑虑：本机 Node v24.13.0 下设置 VITE_BASE_PATH 构建会原生崩溃（exit 0xC0000409），已用基线配置 + `--base` 复现同样崩溃 → 属既有工具链问题，非本次改动引入。

### 你的工作

1. `git show b77ad77 --stat` 确认提交范围；
2. 通读 `git show b77ad77` 全量 diff，逐项对照上述 4 项要求（注意 `${...}` 模板字符串与引号正确性）；
3. 运行 `cd frontend && npx tsc -b` 与 `npx vitest run` 确认门禁；
4. 可选复验默认构建：`npx vite build`（若本机 Node 24 构建正常）后检查 `dist/index.html` 资源无前缀；若复现 Node 24 崩溃，记录崩溃现象但按实现者所述判定为既有环境问题，不因此判失败；
5. 检查是否有规格外改动。

### 汇报格式

- ✅ 符合规格（经代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失/多余/理解偏差，附带 file:line 引用]
