# Codex Custom Subagents task handoff v1

Task: t08_fix2_healthcheck

## 任务：修复任务 8（二次）—— backend healthcheck 端点改真实路由 /api/health

你是一个修复子智能体。复审发现：`deploy/docker-compose.prod.yml` 的 backend healthcheck 探测 `http://127.0.0.1:8000/api/v1/health`，但后端真实健康路由是 `backend/app/main.py:79` 的 `@app.get("/api/health")`。`/api/v1/health` 在生产容器内（无 frontend dist）会落入 SPA fallback 返回 404，healthcheck 永久失败。修复为真实路由。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。当前 HEAD `59c1bf4`。启动时 `cd` 到该目录，`git status` 确认工作区干净（TASKS.md 未提交改动属正常）。

### 步骤 1：修改 healthcheck URL

在 `deploy/docker-compose.prod.yml` 中找到 backend 的 healthcheck 行，将：

```yaml
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)\""]
```

改为：

```yaml
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)\""]
```

### 步骤 2：复验

```bash
docker compose -f deploy/docker-compose.prod.yml --project-directory . config | Select-String -Pattern "health"
rg -n "api/health" backend/app/main.py
```

预期：config 输出中 healthcheck 含 `/api/health`；main.py 存在 `@app.get("/api/health")`。

### 步骤 3：Commit

```bash
git add deploy/docker-compose.prod.yml
git commit -m "fix(deploy): point backend healthcheck at real /api/health route"
```

### 门禁

1. 步骤 2 两项验证通过；
2. `git diff --check` 干净；
3. 提交只含 `deploy/docker-compose.prod.yml`，提交消息精确匹配步骤 3。

### 汇报格式

完成后汇报：**状态：** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT；修改内容；验证输出摘录；修改的文件；任何疑虑。
