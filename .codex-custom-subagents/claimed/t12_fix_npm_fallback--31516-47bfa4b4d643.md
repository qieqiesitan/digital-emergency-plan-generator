# Codex Custom Subagents task handoff v1

Task: t12_fix_npm_fallback

## 任务：npm ci 兜底修复 —— package-release.sh 与部署手册构建命令

你是一个修复子智能体。任务 12 验证发现：仓库 `package-lock.json` 与 `package.json` 不同步（`Missing: @floating-ui/dom@1.8.0 from lock file`，已提交的既有状态），干净环境下 `npm ci` 必然失败；而 `scripts/package-release.sh` 和部署手册 §3 的构建命令都用 `npm ci`，会让公司开发在干净机器上构建失败。按本文件修复。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。当前 HEAD `0bf7e05`（任务 12 无代码改动）。启动时 `cd` 到该目录，`git status` 确认工作区干净（TASKS.md 未提交改动属正常）。

### 背景

仓库 `docs/reference/build-consistency-checklist.md` 明确允许兜底模式：「`npm ci 2>/dev/null || npm install`」。lockfile 同步修复（重新生成 lock）会产生大范围 churn 且超出本任务范围；采用兜底模式保证干净环境可构建。

### 步骤 1：scripts/package-release.sh

将构建命令：

```bash
docker run --rm -v "$ROOT/frontend:/app" -w /app -e VITE_BASE_PATH="$BASE_PATH" \
  node:20 sh -c "npm config set registry https://registry.npmmirror.com && npm ci && npm run build"
```

改为：

```bash
docker run --rm -v "$ROOT/frontend:/app" -w /app -e VITE_BASE_PATH="$BASE_PATH" \
  node:20 sh -c "npm config set registry https://registry.npmmirror.com && (npm ci 2>/dev/null || npm install) && npm run build"
```

### 步骤 2：docs/deploy/README-DEPLOY.md §3 构建命令

将：

```bash
  node:20 sh -c "npm config set registry https://registry.npmmirror.com && npm ci && npm run build"
```

改为：

```bash
  node:20 sh -c "npm config set registry https://registry.npmmirror.com && (npm ci 2>/dev/null || npm install) && npm run build"
```

并在该代码块后追加一句说明：

```markdown
> 说明：`npm ci` 失败（lockfile 与 package.json 不同步等）时自动回退 `npm install`，保证干净环境可构建；lockfile 同步问题见项目技术债待办。
```

### 步骤 3：验证 + Commit

```bash
bash -n scripts/package-release.sh
rg -n "npm ci" scripts/package-release.sh docs/deploy/README-DEPLOY.md
```

预期：bash -n 通过；rg 命中处均带 `2>/dev/null || npm install` 兜底（无裸 `npm ci` 作为构建命令）。然后：

```bash
git add scripts/package-release.sh docs/deploy/README-DEPLOY.md
git commit -m "fix(deploy): fall back to npm install when npm ci fails"
```

### 门禁

1. `bash -n scripts/package-release.sh` 通过；
2. 两处构建命令均含兜底；README 有说明句；
3. `git diff --check` 干净；
4. 提交只含上述 2 个文件，提交消息精确匹配步骤 3。

### 汇报格式

完成后汇报：**状态：** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT；修改内容；验证输出；修改的文件；任何疑虑。
