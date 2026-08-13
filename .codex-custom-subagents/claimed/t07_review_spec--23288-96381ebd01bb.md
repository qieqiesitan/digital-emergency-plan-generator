# Codex Custom Subagents task handoff v1

Task: t07_review_spec

## 任务：规格合规审查 —— 任务 7（docker-compose.yml postgres 镜像换 Debian 版）

你是一个规格合规审查子智能体。验证实现者是否构建了所要求的内容（不多不少）。**不要信任实现者的报告**，独立核对。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。相关提交：`ea96f51`（`fix(docker): use postgres:16 Debian image to avoid CentOS 7 volume mount failure`），父提交 `63dae2a`。

### 要求的内容（任务 7 规格）

1. `docker-compose.yml` 中 `image: postgres:16-alpine` → `image: postgres:16`（仅这一处，postgres 服务）；
2. 提交只含 `docker-compose.yml`，提交消息精确匹配；
3. `docker compose config -q` 退出码 0。

### 实现者声称

镜像已替换并提交；`docker compose config -q` 通过（external 卷不影响 config 解析）；提交 ea96f51 仅 1 文件 1 行变更。

### 你的工作

1. `git show ea96f51 --stat` 与全量 diff 确认范围与内容；
2. 运行 `docker compose config -q` 复验（在 worktree 根目录）；
3. 确认没有顺带改动其他服务/卷/端口（规格外改动检查）。

### 汇报格式

- ✅ 符合规格（经代码检查后一切匹配）
- ❌ 发现问题：[具体列出，附带 file:line]
