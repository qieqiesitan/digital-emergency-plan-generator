# Codex Custom Subagents task handoff v1

Task: t08_review_spec

## 任务：规格合规审查 —— 任务 8（生产 compose + .env.example + 网关 nginx 模板）

你是一个规格合规审查子智能体。验证实现者是否构建了所要求的内容（不多不少）。**不要信任实现者的报告**，独立核对。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。相关提交：`a87b0a8`（`feat(deploy): add production compose, env template and gateway nginx template`），父提交 `ea96f51`。

### 要求的内容（任务 8 规格）

1. 新建 `deploy/docker-compose.prod.yml`：postgres:16（Debian）+ backend（build ./backend、env 用 `${VAR:-default}`、exports/uploads/model-cache 挂载、`uvicorn ... --workers 4`、depends_on healthcheck、pgdata 命名卷非 external、db-init 只读挂载、注释说明网关拓扑）；
2. 新建 `.env.example`：SECRET_KEY / ENCRYPTION_KEY / POSTGRES_PASSWORD / QCC_* 模板；
3. 新建 `deploy/gateway-nginx.conf.example`：无尾斜杠 301 + **拆分两个静态 location**（`^~ /emergency-plan-migration/m/` 回退 m.html、`^~ /emergency-plan-migration/` 回退 index.html）+ `/api/`、`/uploads/` 反代 + 三条铁律注释；
4. 提交只含上述 3 个文件，提交消息精确匹配；`docker compose -f deploy/docker-compose.prod.yml config -q` 退出码 0。

### 实现者声称

三文件逐字一致（脚本比对 ALL MATCH）；config -q 通过；.env.example 因 `.gitignore` 的 `.env.*` 被忽略，用 `git add -f` 强制纳入并 amend；提交 a87b0a8 含全部 3 文件。

### 你的工作

1. `git show a87b0a8 --stat` 确认 3 个文件在提交内（重点确认 `.env.example` 已入库）；
2. 通读三个文件内容，对照规格逐项核对（尤其网关模板必须是拆分 location 的修正版，**不是**变更说明的旧模式）；
3. 运行 `docker compose -f deploy/docker-compose.prod.yml config -q`；
4. 检查规格外改动。

### 汇报格式

- ✅ 符合规格（经代码检查后一切匹配）
- ❌ 发现问题：[具体列出，附带 file:line]
