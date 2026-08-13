# Codex Custom Subagents task handoff v1

Task: t08_fix_prod_compose

## 任务：修复任务 8 —— 生产 compose 相对路径解析 + 质量审查建议项

你是一个修复子智能体。任务 8 质量审查发现关键缺陷：`docker compose -f deploy/docker-compose.prod.yml` 会把 compose 内的相对路径（`./backend`、`./db-init` 等）解析到 **compose 文件所在目录 `deploy/`** 而非仓库根，导致 `up --build` 必然失败、数据/模型落到错误位置。按本文件修复并复验。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。当前 HEAD `a87b0a8`。启动时 `cd` 到该目录，`git status` 确认工作区干净（TASKS.md 未提交改动属正常）。

### 步骤 1：修复 deploy/docker-compose.prod.yml

将头部注释的用法行改为（`--project-directory .` 让相对路径按仓库根解析）：

```yaml
# 用法：cp .env.example .env && docker compose -f deploy/docker-compose.prod.yml --project-directory . up -d --build
```

同时做以下小修（与审查建议一致）：

1. 在头注补一句：「`db-init/`（数据库恢复 SQL）与 `model-cache/chroma/`（ONNX 模型缓存）由部署者提供，缺目录时 docker 会静默创建空目录，必须放置真实数据」；
2. postgres 端口改为宿主机回环绑定：`"127.0.0.1:5432:5432"`（网关拓扑无需对外暴露，backup.sh 在本机执行不受影响）；
3. backend 增加 healthcheck（复用应用已有 `/api/v1/health`）：

```yaml
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)\""]
      interval: 10s
      timeout: 5s
      retries: 5
```

4. 在 `deploy/gateway-nginx.conf.example` 的 `^~ /emergency-plan-migration/` 块内，把被注释的 include 行替换为显式 assets 长缓存 location（与 frontend/nginx.conf 任务 6 修复对齐）：

```nginx
location ^~ /emergency-plan-migration/assets/ {
    alias {{静态目录容器内路径}}/emergency-plan-migration/assets/;
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

（若网关已用 `static_expire.conf` 统一处理缓存，可保留注释说明二选一。）

### 步骤 2：复验

```bash
docker compose -f deploy/docker-compose.prod.yml --project-directory . config
```

预期：输出中 `build.context` 解析为仓库根的 `backend` 目录、卷路径解析为仓库根的 `backend/exports` 等（不再是 `deploy/...`）；`config -q` 退出码 0。同时确认默认用法（不带 `--project-directory`）确实解析错误、修复后的命令解析正确，两者对比写入报告。

### 步骤 3：Commit

```bash
git add deploy/docker-compose.prod.yml deploy/gateway-nginx.conf.example
git commit -m "fix(deploy): resolve prod compose paths from repo root and align gateway asset cache"
```

### 门禁

1. 步骤 2 对比验证通过（修复前错 / 修复后对）；
2. `git diff --check` 干净；
3. 提交只含上述 2 个文件，提交消息精确匹配步骤 3。

### 汇报格式

完成后汇报：**状态：** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT；修复内容；对比验证输出摘录；修改的文件；任何疑虑。
