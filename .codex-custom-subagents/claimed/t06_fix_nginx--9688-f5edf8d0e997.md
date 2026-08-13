# Codex Custom Subagents task handoff v1

Task: t06_fix_nginx

## 任务：修复任务 6 —— frontend/nginx.conf 子路径 SPA 回退与静态资源缓存

你是一个修复子智能体。任务 6 质量审查发现关键缺陷：原 `try_files $uri $uri/ /emergency-plan-migration/index.html /emergency-plan-migration/m.html` 中，`index.html` 参数作为文件路径会拼到 alias 后产生双前缀死路径，导致桌面端深链最终回退到 `m.html`（移动端页）。审查者已给修复方案，按本文件执行。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。当前 HEAD `7abd9ee`（任务 6 原提交）。启动时 `cd` 到该目录，`git status` 确认工作区干净（TASKS.md 未提交改动属正常）。

### 步骤 1：替换 frontend/nginx.conf 的子路径 location

将当前 `location /emergency-plan-migration/ { ... }` 整个块替换为以下内容（放在 `location /m/` 块之后、`location /` 块之前）：

```nginx
    # 无尾斜杠访问时 301 跳转
    location = /emergency-plan-migration {
        return 301 /emergency-plan-migration/;
    }

    # 应用子路径部署：dist 位于容器 html 根目录（alias 指向容器内路径，勿写宿主机路径）
    # 移动端路径优先匹配并回退 m.html；其余子路径回退桌面 index.html
    location /emergency-plan-migration/m/ {
        alias /usr/share/nginx/html/;
        try_files $uri $uri/ /emergency-plan-migration/m.html;
    }
    location /emergency-plan-migration/ {
        alias /usr/share/nginx/html/;
        try_files $uri $uri/ /emergency-plan-migration/index.html;
    }

    # 子路径静态资源长缓存（与根路径 /assets/ 对齐）
    location /emergency-plan-migration/assets/ {
        alias /usr/share/nginx/html/assets/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
```

### 步骤 2：容器实测验证

先构建子路径产物（node:20 容器；本机 Node 24 构建已知崩溃）：

```bash
docker run --rm -v "${PWD}/frontend:/app" -w /app -e VITE_BASE_PATH="/emergency-plan-migration/" node:20 sh -c "npm config set registry https://registry.npmmirror.com && npm ci && npm run build"
```

然后启动 nginx 容器挂载 dist 与配置（若 `nginx:stable-alpine` 拉取超时用本地 `nginx:alpine`，并加 `--add-host backend:127.0.0.1`）：

```bash
docker run --rm -d --name t06-fix-nginx -p 19091:8080 \
  -v "${PWD}/frontend/dist:/usr/share/nginx/html:ro" \
  -v "${PWD}/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  --add-host backend:127.0.0.1 \
  nginx:alpine
Start-Sleep -Seconds 3
```

断言（每条都必须满足）：

```powershell
# 桌面首页 → 桌面 index.html
(Invoke-WebRequest -Uri "http://127.0.0.1:19091/emergency-plan-migration/" -UseBasicParsing).Content -match "数字化预案系统"
# 桌面深链 → 桌面 index.html（不得含移动端标题）
$d = (Invoke-WebRequest -Uri "http://127.0.0.1:19091/emergency-plan-migration/enterprises" -UseBasicParsing).Content
$d -match "数字化预案系统" -and $d -notmatch "移动端"
# 移动端深链 → m.html
(Invoke-WebRequest -Uri "http://127.0.0.1:19091/emergency-plan-migration/m/dashboard" -UseBasicParsing).Content -match "移动端"
# 无尾斜杠 → 301
(Invoke-WebRequest -Uri "http://127.0.0.1:19091/emergency-plan-migration" -UseBasicParsing -MaximumRedirection 0 -ErrorAction SilentlyContinue).StatusCode -eq 301
# 静态资源 200 + 长缓存头
$js = (Select-String -LiteralPath frontend\dist\index.html -Pattern 'src="[^"]*\.js"' | Select-Object -First 1).Matches[0].Value -replace 'src="|"',''
$h = Invoke-WebRequest -Uri "http://127.0.0.1:19091$js" -UseBasicParsing
$h.StatusCode -eq 200 -and $h.Headers["Cache-Control"] -match "immutable"
```

全部满足后清理容器：

```bash
docker rm -f t06-fix-nginx
```

### 步骤 3：Commit

```bash
git add frontend/nginx.conf
git commit -m "fix(deploy): correct subpath SPA fallback and asset cache in nginx"
```

### 门禁

1. 配置语法校验通过（`docker run --rm -v "${PWD}/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" --add-host backend:127.0.0.1 nginx:alpine nginx -t`）；
2. 步骤 2 的 5 条断言全部满足（如实记录每条结果）；
3. `git diff --check` 干净；
4. 提交只含 `frontend/nginx.conf`，提交消息精确匹配步骤 3。

### 汇报格式

完成后汇报：**状态：** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT；替换后的配置；5 条断言逐条结果；修改的文件；任何疑虑。
