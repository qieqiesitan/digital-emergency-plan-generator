# Codex Custom Subagents task handoff v1

Task: t12_build_regression

## 任务：部署可交付性计划任务 12 —— 根路径回归 + 子路径构建验证

你是一个实现子智能体（验证型任务，预期不改代码，只跑构建与断言并汇报）。不要读计划文件——本任务文件已包含完整任务文本。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness` 的隔离 worktree。启动时 `cd` 到该目录，`git status` 确认工作区干净（TASKS.md 若有未提交改动属正常，不要动它）。

### 背景与重要约束

本机 Node v24.13.0 下 `vite build` 已知会原生崩溃（exit 0xC0000409，既有工具链问题，任务 2 双审已确认与本次改动无关）。因此**所有构建一律用 node:20 容器**执行，不走本机 npm run build。容器构建命令：

```bash
docker run --rm -v "${PWD}/frontend:/app" -w /app node:20 sh -c "npm config set registry https://registry.npmmirror.com && npm ci && npm run build"
```

（加 `-e VITE_BASE_PATH=...` 即为子路径构建。容器内 `npm ci` 依赖 node_modules 缓存，首次较慢属正常。）

### 步骤 1：根路径构建回归

在 worktree 根目录执行容器构建（不设 VITE_BASE_PATH），然后断言产物无前缀：

```bash
docker run --rm -v "${PWD}/frontend:/app" -w /app node:20 sh -c "npm config set registry https://registry.npmmirror.com && npm ci && npm run build"
Select-String -LiteralPath frontend\dist\index.html -Pattern 'src="[^"]*\.js"' | Select-Object -First 3
```

预期：构建成功；`src` 引用以 `/assets/` 或 `./assets/` 开头，**不包含** `/emergency-plan-migration/`。

### 步骤 2：子路径构建

```bash
docker run --rm -v "${PWD}/frontend:/app" -w /app -e VITE_BASE_PATH="/emergency-plan-migration/" node:20 sh -c "npm config set registry https://registry.npmmirror.com && npm ci && npm run build"
Select-String -LiteralPath frontend\dist\index.html -Pattern 'src="[^"]*\.js"' | Select-Object -First 3
Get-Content -LiteralPath frontend\dist\manifest.webmanifest -Encoding UTF8
```

预期：`src="/emergency-plan-migration/assets/...` 带前缀；`manifest.webmanifest` 的 `start_url` 为 `/emergency-plan-migration/m/dashboard`、`scope` 为 `/emergency-plan-migration/`。

### 步骤 3：恢复默认构建产物

```bash
docker run --rm -v "${PWD}/frontend:/app" -w /app node:20 sh -c "npm config set registry https://registry.npmmirror.com && npm ci && npm run build"
```

预期：构建成功，回到根路径产物（保证后续本地使用正常）。

### 门禁

1. 步骤 1/2/3 全部执行并给出断言结果（含实际输出摘录）；
2. 子路径产物断言全部满足；
3. 不改任何代码；工作区最终干净（dist 是 gitignored 产物，不影响 git status）。

### 汇报格式

完成后汇报：**状态：** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT；三个步骤的实际输出摘录；断言是否全部满足；任何疑虑。
