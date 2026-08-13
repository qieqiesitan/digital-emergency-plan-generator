# Codex Custom Subagents task handoff v1

Task: t08_prod_compose_env_gateway

## 任务：部署可交付性计划任务 8 —— 生产 compose + .env.example + 网关 nginx 模板

你是一个实现子智能体。严格按以下步骤在指定 worktree 内创建 3 个新文件并提交。不要修改任务范围之外的文件。不要读计划文件——本任务文件已包含完整任务文本与全部文件内容。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness` 的隔离 worktree。启动时 `cd` 到该目录，`git status` 确认工作区干净（TASKS.md 若有未提交改动属正常，不要动它）。

### 背景

公司部署拓扑为「网关 nginx 托管静态 + 反代 /api /uploads + 宿主机 backend 容器」。本任务创建生产后端栈 compose、环境变量模板、网关 nginx 模板，把踩坑固化为模板注释。

### 步骤 1：创建 deploy/docker-compose.prod.yml

完整内容（一次性写入）：

```yaml
# 生产部署 compose（后端栈）
# 用法：cp .env.example .env && docker compose -f deploy/docker-compose.prod.yml up -d --build
# 拓扑：公司网关 nginx 托管前端静态 + 反代 /api /uploads，本文件只启 postgres + backend。
# 如需自托管前端（开发/无网关形态），参考根 docker-compose.yml 的 frontend/shuzihuayuan 服务。
services:
  postgres:
    image: postgres:16
    container_name: emergency-plan-db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: emergency_plan
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db-init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 10
    restart: unless-stopped

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: emergency-plan-backend
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:${POSTGRES_PASSWORD:-postgres}@postgres:5432/emergency_plan
      SECRET_KEY: ${SECRET_KEY:-emergency-plan-docker-secret-key-2026}
      ACCESS_TOKEN_EXPIRE_MINUTES: "30"
      REFRESH_TOKEN_EXPIRE_DAYS: "7"
      ENCRYPTION_KEY: ${ENCRYPTION_KEY:-abcdefghijklmnopqrstuvwxyz123456}
      EXPORT_DIR: /app/exports
      QCC_API_KEY: ${QCC_API_KEY:-}
      QCC_ENDPOINT: ${QCC_ENDPOINT:-https://agent.qcc.com/mcp/company/stream}
      QCC_API_KEY_FALLBACK: ${QCC_API_KEY_FALLBACK:-}
    ports:
      - "8000:8000"
    volumes:
      - ./backend/exports:/app/exports
      - ./backend/uploads:/app/uploads
      - ./model-cache/chroma:/root/.cache/chroma
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

volumes:
  pgdata:
```

### 步骤 2：创建 .env.example

完整内容（一次性写入）：

```bash
# 复制为 .env 后按需修改（未设的项使用 compose 内默认值）

# JWT 签名密钥：生产环境建议改为随机长字符串（改动后所有登录态失效，需重新登录）
SECRET_KEY=emergency-plan-docker-secret-key-2026

# AI Key 加密密钥：**不要修改**，必须与数据来源一致
# （当前数据库中的 AI Key 使用 abcdefghijklmnopqrstuvwxyz123456 加密）
ENCRYPTION_KEY=abcdefghijklmnopqrstuvwxyz123456

# 数据库口令（postgres 服务使用，默认 postgres）
POSTGRES_PASSWORD=postgres

# 企查查智能体（可选，如需业务中台接入；留空表示不启用）
QCC_API_KEY=
QCC_API_KEY_FALLBACK=
QCC_ENDPOINT=https://agent.qcc.com/mcp/company/stream
```

### 步骤 3：创建 deploy/gateway-nginx.conf.example

完整内容（一次性写入）：

```nginx
# ============================================================
# 网关 nginx 子路径部署模板（公司网关 proxy 容器使用）
# 使用前替换 {{域名}}、{{宿主机IP}}、{{静态目录容器内路径}} 占位符
# 三条铁律：
#   1. 文件必须 UTF-8 无 BOM（Windows 编辑后易带 BOM → unknown directive server）
#   2. alias 必须写【容器内】路径；写宿主机路径会 500 rewrite 重定向循环
#   3. 容器内 proxy_pass 到宿主机服务必须用宿主机 IP（如 192.168.3.17），
#      不能用 127.0.0.1（会指向容器自身）
# ============================================================

# 无尾斜杠访问时 301 跳转
location = /emergency-plan-migration {
    return 301 /emergency-plan-migration/;
}

# 子路径静态资源（dist 已复制到网关静态目录的 emergency-plan-migration/ 子目录）
# 注意：try_files 的静态参数会拼到 alias 后，不能写带子路径前缀的回退文件；
# 必须按 移动端 /m/ 与 其余路径 拆分两个 location，分别回退 m.html / index.html
location ^~ /emergency-plan-migration/m/ {
    alias {{静态目录容器内路径}}/emergency-plan-migration/;
    try_files $uri $uri/ /emergency-plan-migration/m.html;
}
location ^~ /emergency-plan-migration/ {
    alias {{静态目录容器内路径}}/emergency-plan-migration/;   # 例如 /etc/nginx/html/emergency-plan-migration/
    index index.html;
    try_files $uri $uri/ /emergency-plan-migration/index.html;
    # include ./static_expire.conf;   # 网关已定义则启用，否则删除本行
    # include ./safe.conf;            # 网关已定义则启用，否则删除本行
}

# API 代理（宿主机 backend 容器端口 8000）
location /api/ {
    proxy_pass http://{{宿主机IP}}:8000/api/;
}

# 上传文件代理
location /uploads/ {
    proxy_pass http://{{宿主机IP}}:8000/uploads/;
}
```

### 步骤 4：compose 模板校验

在 worktree 根目录执行：

```bash
docker compose -f deploy/docker-compose.prod.yml config -q
```

预期：退出码 0（只解析不启动，端口占用不影响）。

### 步骤 5：Commit

```bash
git add deploy/docker-compose.prod.yml .env.example deploy/gateway-nginx.conf.example
git commit -m "feat(deploy): add production compose, env template and gateway nginx template"
```

### 门禁

1. 3 个新文件内容与任务给定文本逐字一致（可自行复核关键行）；
2. `docker compose -f deploy/docker-compose.prod.yml config -q` 通过（或如实记录阻塞原因）；
3. `git diff --check` 干净；
4. 提交只含上述 3 个文件，提交消息精确匹配步骤 5。

### 汇报格式

完成后汇报：**状态：** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT；你创建了什么；验证结果；修改的文件；自审发现；任何疑虑。
