# Codex Custom Subagents task handoff v1

Task: t10_review_quality

## 任务：代码质量审查 —— 任务 10（package-release.sh + backup.sh）

你是一个代码质量审查子智能体。验证脚本质量（健壮性、可移植性、安全）。规格合规性已通过，本次只审代码质量。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。范围：BASE `49e0d39` → HEAD `38a22d4`，新增 `scripts/package-release.sh`（58 行）、`scripts/backup.sh`（12 行）、`.gitignore`（+3）。

### 审查要点

- 脚本健壮性：`set -euo pipefail`、路径引用（`"$ROOT"` 等）、STAGE 清理的目标是否限定在 `$OUT_ROOT` 内（防误删）、空变量保护；
- 可移植性：bash 语法（Git Bash/WSL/Linux）、`docker run` 参数、`tar`/`sha256sum` 可用性；
- 与部署手册/生产 compose 一致性：backup.sh 使用 `--project-directory .` 与生产 compose；package-release.sh 产物结构与手册 §5/§9 对应；
- 潜在问题：node:20 容器构建时 `npm ci` 可能因 lockfile 不同步失败（已知技术债）——脚本是否需要兜底 `npm install`（若任务文本未要求，可备注不阻塞）；
- 是否有规格外改动。不要修改代码，只审查。

### 汇报格式

返回：优点、问题（关键/重要/次要，附 file:line）、评估结论（✅ 通过 / ❌ 需修复）。
