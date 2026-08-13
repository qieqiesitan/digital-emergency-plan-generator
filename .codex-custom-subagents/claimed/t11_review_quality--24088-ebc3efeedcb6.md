# Codex Custom Subagents task handoff v1

Task: t11_review_quality

## 任务：代码质量审查 —— 任务 11（deploy-check.sh）

你是一个代码质量审查子智能体。验证脚本质量。规格合规性已通过，本次只审代码质量。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。范围：BASE `01dd148` → HEAD `ec9b1ea`，仅 `scripts/deploy-check.sh`（88 行新增）。

### 审查要点

- 脚本健壮性：`set -euo pipefail` 下 `grep -q`/`curl -f` 失败分支是否会被提前终止（注意 `|| true`、`if` 条件内的非零退出是否安全）；
- 断言质量：#2/#7 的 body 判定是否可能误报（中文标题匹配、「移动端」子串）、#3 资源提取正则是否覆盖 Vite 产物、#8 的 301 判定逻辑；
- 可移植性：`grep -oE`、`sed -E`、`awk` 在 Git Bash/WSL/Linux 的可用性；
- 与部署手册 §7 用法一致；API 检查用 `/api/health`；
- 是否有规格外改动。不要修改代码，只审查。

### 汇报格式

返回：优点、问题（关键/重要/次要，附 file:line）、评估结论（✅ 通过 / ❌ 需修复）。
