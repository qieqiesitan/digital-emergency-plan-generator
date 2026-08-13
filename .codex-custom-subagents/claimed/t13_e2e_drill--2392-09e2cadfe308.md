# Codex Custom Subagents task handoff v1

Task: t13_e2e_drill

## 任务：部署可交付性计划任务 13 —— 端到端演练

你是一个实现子智能体（验证型任务，不改业务代码；可临时启动/停止 docker 容器与生成测试产物）。不要读计划文件——本任务文件已包含完整任务文本。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness` 的隔离 worktree。启动时 `cd` 到该目录。注意：docker 命令在 worktree 根目录执行；`frontend/` 子目录是构建产物所在。

### 背景

端到端验证「子路径产物 + frontend/nginx.conf + deploy-check.sh」全链路。前置：任务 12 已完成（dist 为子路径产物或将在本任务重新构建）。本机 Node 24 构建会崩溃，一律用 node:20 容器构建。

### 步骤 1：构建子路径产物（若任务 12 已留子路径产物可跳过）

```bash
docker run --rm -v "${PWD}/frontend:/app" -w /app -e VITE_BASE_PATH="/emergency-plan-migration/" node:20 sh -c "npm config set registry https://registry.npmmirror.com && npm ci && npm run build"
```

预期：构建成功，`frontend/dist/index.html` 资源引用带 `/emergency-plan-migration/` 前缀。

### 步骤 2：启动后端栈并确认 health

```bash
cd "C:\Users\55061\Documents\数字化预案自动生成 2"
docker compose up -d postgres backend
for ($i=0; $i -lt 30; $i++) { try { $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 3; if ($r.StatusCode -eq 200) { Write-Output "backend ready"; break } } catch {}; Start-Sleep -Seconds 3 }
```

预期：health 200（最多 90 秒）。注意：后端真实健康路由是 `/api/health`（`/api/v1/health` 会落入 SPA fallback 假阳性，不可用）。若根 compose 因 external 卷缺失等原因无法启动，如实记录并改用 `--skip-api` 方式完成静态部分演练（见步骤 3 备注）。

### 步骤 3：用 frontend/nginx.conf 模拟网关子路径托管 + deploy-check 全绿

在 worktree 根目录执行：

```bash
docker run --rm -d --name deploy-check-nginx \
  -p 19090:8080 \
  -v "${PWD}/frontend/dist:/usr/share/nginx/html:ro" \
  -v "${PWD}/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  nginx:stable-alpine
Start-Sleep -Seconds 3
bash scripts/deploy-check.sh http://127.0.0.1:19090/emergency-plan-migration/ http://127.0.0.1:8000
```

预期：deploy-check.sh 全部 PASS，最后输出 `部署验证通过`，退出码 0。若后端未就绪，可运行 `bash scripts/deploy-check.sh http://127.0.0.1:19090/emergency-plan-migration/ --skip-api` 验证静态部分，并在报告中注明 API 未验证。

### 步骤 4：打包演练

```bash
cd "C:\Users\55061\Documents\数字化预案自动生成 2"
./scripts/package-release.sh 0.1.0-test
tar tzf release/emergency-plan-migration-0.1.0-test.tar.gz | Select-Object -First 20
```

注意：`package-release.sh` 内部的 docker 构建使用 `$ROOT/frontend`，其中 `$ROOT` 是脚本所在仓库根（worktree 根）。若在 worktree 根执行，产物在 worktree 的 `release/` 下。预期：tar.gz 与 .sha256 生成，结构含 backend/frontend/dist/deploy/scripts/.env.example，db-init/model-cache 按存在性提示。

### 步骤 5：清理演练容器与临时产物

```bash
docker rm -f deploy-check-nginx
```

测试产物 `release/emergency-plan-migration-0.1.0-test*` 留在 release/ 目录（已被 .gitignore 忽略，无需删除；若想清理，确认路径在 release/ 内再删）。

### 步骤 6：收尾门禁

```bash
cd "C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness"
git diff --check
cd frontend
npx tsc -b
npx vitest run
```

预期：`git diff --check` 干净；tsc 0；vitest 全绿（52+）。

### 汇报格式

完成后汇报：**状态：** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT；每个步骤的实际结果（deploy-check 输出、tar 结构摘录、门禁输出）；任何疑虑（如后端未启动、API 检查被跳过）。
