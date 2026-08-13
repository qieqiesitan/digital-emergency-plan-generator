# Codex Custom Subagents task handoff v1

Task: t08_review_quality2

## 任务：代码质量复审 —— 任务 8 修复（59c1bf4）

你是一个代码质量审查子智能体。任务 8 原实现因「compose 相对路径按 deploy/ 解析导致构建必然失败」关键缺陷被打回，实现者已提交修复 59c1bf4。本次复审确认修复有效且无新问题。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。复审范围：BASE `a87b0a8` → HEAD `59c1bf4`，仅 `deploy/docker-compose.prod.yml`（+11/-2）、`deploy/gateway-nginx.conf.example`（+8/-1）。

### 修复内容

1. 用法注释改为 `docker compose -f deploy/docker-compose.prod.yml --project-directory . up -d --build`，头注补充 db-init/model-cache 由部署者提供；
2. postgres 端口 `127.0.0.1:5432:5432`；
3. backend 增加 healthcheck（`/api/v1/health`，interval 10s / timeout 5s / retries 5）；
4. 网关模板新增 `^~ /emergency-plan-migration/assets/` 长缓存 location。

### 复审要点

1. `git show 59c1bf4` diff 与上述内容一致，提交只含 2 文件；
2. 复跑对比验证：不带 `--project-directory` 时 context/卷路径解析到 `deploy/...`（错误），带时解析到仓库根（正确），`config -q` 退出码 0；
3. backend healthcheck 命令在容器内可用（`python -c urllib...`，镜像基于 python:3.12-slim）；
4. 检查是否引入新问题（端口绑定是否影响 backup.sh 的宿主 pg_dump、assets location 是否与 /m/ 和主 location 冲突）。

### 汇报格式

返回：✅ 通过 / ❌ 需修复（附实测证据与 file:line）。不要修改代码。
