# Codex Custom Subagents task handoff v1

Task: t10_review_spec

## 任务：规格合规审查 —— 任务 10（package-release.sh + backup.sh + .gitignore）

你是一个规格合规审查子智能体。验证实现者是否创建了所要求的内容（不多不少）。**不要信任实现者的报告**，独立核对。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。相关提交：`38a22d4`（`feat(deploy): add release packaging and database backup scripts`），父提交 `49e0d39`。

### 要求的内容（任务 10 规格）

1. `scripts/package-release.sh`：版本号参数校验（`^[A-Za-z0-9._-]+$`）、`VITE_BASE_PATH` 默认 `/emergency-plan-migration/`、node:20 容器构建（npmmirror + npm ci + npm run build）、STAGE 组装（backend 去 __pycache__/.venv/uploads/exports、frontend/dist、deploy、scripts、.env.example、可选 db-init/model-cache 提示）、tar czf + sha256sum、产物输出；
2. `scripts/backup.sh`：使用 `deploy/docker-compose.prod.yml` + `--project-directory .` + pg_dump -Fc 到 backups/；
3. `.gitignore` 末尾追加 `release/`；
4. 提交只含上述 3 个文件，提交消息精确匹配；`bash -n` 两脚本通过。

### 实现者声称

三交付物齐全；bash -n 通过；可执行位用 git update-index 固化；提交 38a22d4 仅 3 文件。

### 你的工作

1. `git show 38a22d4 --stat` 确认提交范围；
2. 通读 `git show 38a22d4` 两个脚本全文，逐项对照上述要求（重点：VERSION 正则、docker 构建、rm -rf 目标在 STAGE 内、backup.sh 的 compose 用法）；
3. 运行 `bash -n scripts/package-release.sh scripts/backup.sh`；
4. 检查规格外改动。

### 汇报格式

- ✅ 符合规格（经检查后一切匹配）
- ❌ 发现问题：[具体列出，附带 file:line]
