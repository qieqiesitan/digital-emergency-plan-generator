# 部署可交付性增强实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 把「公司服务器子路径部署」从现场改代码变成仓库默认支持的参数化能力 + 部署手册 + 打包/验证脚本，使下次交付「填参数 → 跑脚本 → 按手册核对」即可无痛部署。

**架构：** 前端 base 与 PWA manifest 由构建期环境变量 `VITE_BASE_PATH` 驱动，代码统一从 `import.meta.env.BASE_URL` 派生 `APP_BASE`（默认根路径，本地开发零影响）；新增生产后端 compose、网关 nginx 模板、部署手册、打包脚本与部署后验证脚本；根 `docker-compose.yml` postgres 镜像换 Debian 版消除 CentOS 7 必挂坑。

**技术栈：** Vite 7 / React Router 7 / TypeScript / docker compose / nginx / bash。

**执行环境：** 在专用 worktree `.worktrees/deploy-readiness`（分支 `codex/deploy-readiness`，从 master 拉出）中执行，避免与并行会话（引导页方案 A，master HEAD 已到 ca66d22）冲突。全部命令默认在该 worktree 根目录执行，前端命令在 `frontend/` 子目录执行。

**规格依据：** `docs/superpowers/specs/2026-08-10-deploy-readiness-design.md`（commit 639c882）。本计划任务编号与规格 D-1~D-6 对应。

---

## 文件结构

### 修改

| 文件 | 职责 |
| --- | --- |
| `frontend/src/utils/platform.ts` | 新增 `APP_BASE`（BASE_URL 派生）与 `stripAppBase`（剥离子路径前缀，含可注入参数便于单测） |
| `frontend/src/utils/platform.test.ts` | 新建：`stripAppBase`/`APP_BASE` 单元测试 |
| `frontend/vite.config.ts` | `base` + PWA `start_url`/`scope` 由 `VITE_BASE_PATH` 派生 |
| `frontend/src/routes/index.tsx` | 桌面端 router 加 `basename` |
| `frontend/src/mobile/routes.tsx` | 移动端 router 加 `basename` |
| `frontend/src/entry.tsx` | `isMobilePath` 剥前缀 |
| `frontend/src/main.tsx` | `isMobilePath` 剥前缀 |
| `frontend/src/layouts/MainLayout.tsx` | 菜单 `selectedKeys` 剥前缀 |
| `frontend/src/mobile/layouts/MainTabsLayout.tsx` | Tab 隐藏/高亮/key 剥前缀 |
| `frontend/nginx.conf` | 增加子路径 location（alias 容器内路径 + try_files 兜底） |
| `docker-compose.yml` | `postgres:16-alpine` → `postgres:16` |
| `.gitignore` | 追加 `release/`（打包产物目录） |

### 新增

| 文件 | 职责 |
| --- | --- |
| `.env.example` | 生产部署环境变量模板 |
| `deploy/docker-compose.prod.yml` | 生产后端栈（postgres + backend，网关托管静态） |
| `deploy/gateway-nginx.conf.example` | 网关 nginx 子路径模板（含 BOM/alias/proxy_pass 注释） |
| `docs/deploy/README-DEPLOY.md` | 部署手册（预检表/构建/部署/验证/踩坑/回滚） |
| `scripts/package-release.sh` | 一键打包 release 包 |
| `scripts/deploy-check.sh` | 部署后一键验证 |

**AIGenerateButton 预期不改**（2026-08-10 核实无 `location.href`/`navigate` 硬编码）；仅在任务 5 扫描发现新增硬编码时才改。

---

## 任务 0：创建 worktree 并记录基线

**文件：** 无（环境准备）

- [ ] **步骤 1：创建 worktree**

```bash
cd "C:\Users\55061\Documents\数字化预案自动生成 2"
git worktree add .worktrees/deploy-readiness -b codex/deploy-readiness master
cd .worktrees/deploy-readiness
```

预期：worktree 创建成功，`git branch --show-current` 输出 `codex/deploy-readiness`。

- [ ] **步骤 2：安装前端依赖（worktree 无 node_modules）**

```bash
cd frontend
npm ci
```

预期：`npm ci` 成功（无 EBADENGINE；本地 Node 需 >= 20，react-router-dom@7.17 要求）。

- [ ] **步骤 3：记录基线门禁**

```bash
npx tsc -b
npx vitest run
```

预期：`tsc` 退出码 0；`vitest run` 全绿（基线 48 项通过）。记录实际数字供任务 12 对照。

---

## 任务 1：platform.ts 新增 APP_BASE / stripAppBase（TDD）

**文件：**
- 创建：`frontend/src/utils/platform.test.ts`
- 修改：`frontend/src/utils/platform.ts`

- [ ] **步骤 1：编写失败的测试**

创建 `frontend/src/utils/platform.test.ts`：

```ts
import { describe, expect, it } from "vitest";
import { APP_BASE, stripAppBase } from "./platform";

describe("stripAppBase", () => {
  it("appBase 为空时原样返回 pathname", () => {
    expect(stripAppBase("/m/login", "")).toBe("/m/login");
  });

  it("剥离子路径前缀", () => {
    expect(
      stripAppBase("/emergency-plan-migration/m/login", "/emergency-plan-migration"),
    ).toBe("/m/login");
  });

  it("前缀不匹配时原样返回", () => {
    expect(stripAppBase("/other/m/login", "/emergency-plan-migration")).toBe(
      "/other/m/login",
    );
  });
});

describe("APP_BASE", () => {
  it("始终为字符串（根路径构建时为空串）", () => {
    expect(typeof APP_BASE).toBe("string");
  });
});
```

- [ ] **步骤 2：运行测试验证失败**

```bash
npx vitest run src/utils/platform.test.ts
```

预期：FAIL，报错 `does not provide an export named 'stripAppBase'`（platform.ts 尚无该导出）。

- [ ] **步骤 3：实现 platform.ts**

在 `frontend/src/utils/platform.ts` 末尾追加：

```ts
/** 应用部署子路径前缀（生产为 /emergency-plan-migration，开发为 ""） */
export const APP_BASE = import.meta.env.BASE_URL.replace(/\/+$/, "");

/** 从 pathname 中剥离应用子路径前缀，如 /emergency-plan-migration/m/login -> /m/login */
export function stripAppBase(pathname: string, appBase: string = APP_BASE): string {
  if (!appBase) return pathname;
  return pathname.startsWith(appBase) ? pathname.slice(appBase.length) : pathname;
}
```

- [ ] **步骤 4：运行测试验证通过**

```bash
npx vitest run src/utils/platform.test.ts
```

预期：PASS（3 + 1 项全过）。

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/utils/platform.ts frontend/src/utils/platform.test.ts
git commit -m "feat(deploy): add APP_BASE and stripAppBase for subpath deployment"
```

---

## 任务 2：vite.config.ts 参数化 base 与 PWA manifest

**文件：** 修改 `frontend/vite.config.ts`

- [ ] **步骤 1：新增 BASE_PATH 常量**

在 `frontend/vite.config.ts` 第 11 行 `const API_TARGET = ...` 之后追加：

```ts
// 部署子路径（生产如 /emergency-plan-migration，开发为空 → 根路径）
const BASE_PATH = (process.env.VITE_BASE_PATH || "").replace(/\/+$/, "");
```

- [ ] **步骤 2：PWA manifest start_url / scope 参数化**

将 manifest 中 `start_url: "/m/dashboard",` 改为：

```ts
        start_url: BASE_PATH ? `${BASE_PATH}/m/dashboard` : "/m/dashboard",
        scope: BASE_PATH ? `${BASE_PATH}/` : "/",
```

- [ ] **步骤 3：defineConfig 增加 base**

在 `export default defineConfig(async () => ({` 后的 `plugins:` 之前插入：

```ts
  base: BASE_PATH ? `${BASE_PATH}/` : "/",
```

- [ ] **步骤 4：类型检查**

```bash
npx tsc -b
```

预期：退出码 0。

- [ ] **步骤 5：Commit**

```bash
git add frontend/vite.config.ts
git commit -m "feat(deploy): parameterize vite base and PWA manifest via VITE_BASE_PATH"
```

---

## 任务 3：路由 basename（桌面端 + 移动端）

**文件：**
- 修改：`frontend/src/routes/index.tsx:1,70-74`
- 修改：`frontend/src/mobile/routes.tsx:1,30,末尾`

- [ ] **步骤 1：桌面端 routes/index.tsx**

第 1 行 `import { createBrowserRouter, Navigate } from "react-router-dom";` 之后追加：

```tsx
import { APP_BASE } from "@/utils/platform";
```

将文件末尾 `return createBrowserRouter([ ... ]);` 的结束改为（第 74 行附近 `]);` → `], { basename: APP_BASE || undefined });`）：

```tsx
    { path: "/m/*", element: <MobileRedirect /> },
    { path: "*", element: <Navigate to="/dashboard" replace /> },
  ], { basename: APP_BASE || undefined });
}
```

`MobileRedirect`（第 35 行 `window.location.replace(pathname + search)`）保持不动：其行为不依赖前缀，basename 接管后语义不变。

- [ ] **步骤 2：移动端 mobile/routes.tsx**

第 1 行 `import { createBrowserRouter, Navigate } from "react-router-dom";` 之后追加：

```tsx
import { APP_BASE } from "@/utils/platform";
```

将文件末尾 `]);` 改为：

```tsx
], { basename: APP_BASE || undefined });
```

- [ ] **步骤 3：类型检查**

```bash
npx tsc -b
```

预期：退出码 0。

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/routes/index.tsx frontend/src/mobile/routes.tsx
git commit -m "feat(deploy): add router basename for desktop and mobile"
```

---

## 任务 4：入口与布局剥前缀

**文件：**
- 修改：`frontend/src/entry.tsx:1,5-8`
- 修改：`frontend/src/main.tsx:1,6-9`
- 修改：`frontend/src/layouts/MainLayout.tsx:1,155`
- 修改：`frontend/src/mobile/layouts/MainTabsLayout.tsx:1,60-90`

- [ ] **步骤 1：entry.tsx**

第 1 行 `import { isMobile } from "@/mobile/utils/platform";` 之后追加：

```tsx
import { stripAppBase } from "@/utils/platform";
```

将 `isMobilePath` 改为：

```tsx
function isMobilePath(): boolean {
  const p = stripAppBase(window.location.pathname);
  return p === "/m" || p.startsWith("/m/");
}
```

- [ ] **步骤 2：main.tsx**

同上，第 1 行后追加 `import { stripAppBase } from "@/utils/platform";`，`isMobilePath` 改为与 entry.tsx 相同实现。

- [ ] **步骤 3：MainLayout.tsx**

在文件顶部 import 区追加：

```tsx
import { stripAppBase } from "@/utils/platform";
```

将第 155 行 `selectedKeys={[location.pathname]}` 改为：

```tsx
          selectedKeys={[stripAppBase(location.pathname)]}
```

- [ ] **步骤 4：MainTabsLayout.tsx**

在文件顶部 import 区追加：

```tsx
import { stripAppBase } from "@/utils/platform";
```

将第 60 行改为：

```tsx
  const pathname = stripAppBase(location.pathname);
  const hideTabBar = shouldHideTabBar(pathname);
```

将第 65 行 `if (pattern.test(location.pathname)) {` 改为 `if (pattern.test(pathname)) {`；第 72 行依赖数组 `[location.pathname, setActiveTab, activeTab]` 改为 `[pathname, setActiveTab, activeTab]`；第 90 行 `key={location.pathname}` 改为 `key={pathname}`。

- [ ] **步骤 5：类型检查 + lint**

```bash
npx tsc -b
npx eslint src/entry.tsx src/main.tsx src/layouts/MainLayout.tsx src/mobile/layouts/MainTabsLayout.tsx
```

预期：tsc 退出码 0；eslint 无新增 error（与基线对比，允许既有 warning）。

- [ ] **步骤 6：Commit**

```bash
git add frontend/src/entry.tsx frontend/src/main.tsx frontend/src/layouts/MainLayout.tsx frontend/src/mobile/layouts/MainTabsLayout.tsx
git commit -m "feat(deploy): strip app base in entry, menu and mobile tab paths"
```

---

## 任务 5：硬编码跳转核对（预期无代码改动）

**文件：** 无（仅核对；若发现新增硬编码则按规则修复）

- [ ] **步骤 1：全仓扫描根路径硬编码**

```bash
rg -n 'location\.href = "|window\.location\.(href|replace|assign)\(|href="/' frontend/src --glob "*.tsx" --glob "*.ts"
rg -n 'AIGenerateButton' frontend/src/components/plan/AIGenerateButton.tsx
rg -n 'settings/ai-config|location\.href|window\.location|navigate\(' frontend/src/components/plan/AIGenerateButton.tsx
```

预期（2026-08-10 实测基线）：仅 `frontend/src/routes/index.tsx:35`（MobileRedirect，保持不动）；AIGenerateButton 无任何硬编码跳转。若出现其他命中，逐一判断：`navigate()`/router 内跳转由 basename 自动处理不改；`location.href`/`window.location.*` 原生跳转需拼 `APP_BASE` 后改（复用任务 1 导出的 `APP_BASE`），并追加进任务 4 的提交。

- [ ] **步骤 2：记录核对结论**

将结论写入 commit message 或任务报告：扫描命令、命中清单、处置结果。预期无需 commit；若产生代码改动则单独提交 `fix(deploy): prefix hardcoded jumps with APP_BASE`。

---

## 任务 6：frontend/nginx.conf 增加子路径 location

**文件：** 修改 `frontend/nginx.conf`

- [ ] **步骤 1：加入子路径 location**

在 `location /m/ { ... }` 之后、`location / { ... }` 之前插入：

```nginx
    # 应用子路径部署：dist 位于容器 html 根目录（alias 指向容器内路径，勿写宿主机路径）
    location /emergency-plan-migration/ {
        alias /usr/share/nginx/html/;
        try_files $uri $uri/ /emergency-plan-migration/index.html /emergency-plan-migration/m.html;
    }
```

- [ ] **步骤 2：nginx 配置语法校验（docker 容器）**

```bash
docker run --rm -v "${PWD}/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" nginx:stable-alpine nginx -t
```

预期：`syntax is ok` / `test is successful`。

- [ ] **步骤 3：Commit**

```bash
git add frontend/nginx.conf
git commit -m "feat(deploy): add subpath location to frontend nginx config"
```

---

## 任务 7：docker-compose.yml postgres 镜像换 Debian 版

**文件：** 修改 `docker-compose.yml:3`

- [ ] **步骤 1：替换镜像**

将第 3 行 `image: postgres:16-alpine` 改为：

```yaml
    image: postgres:16
```

数据在命名卷 `shuzihuayuan_pgdata`（external）中，PG16 主版本不变，重建容器数据不丢。

- [ ] **步骤 2：compose 配置校验**

```bash
docker compose config -q
```

预期：退出码 0（无输出）。

- [ ] **步骤 3：Commit**

```bash
git add docker-compose.yml
git commit -m "fix(docker): use postgres:16 Debian image to avoid CentOS 7 volume mount failure"
```

---

## 任务 8：生产 compose + .env.example + 网关 nginx 模板

**文件：**
- 创建：`deploy/docker-compose.prod.yml`
- 创建：`.env.example`
- 创建：`deploy/gateway-nginx.conf.example`

- [ ] **步骤 1：创建 deploy/docker-compose.prod.yml**

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

说明：生产镜像内嵌代码（不挂载 `./backend/app` 热更卷，避免依赖宿主机源码）；`model-cache/chroma` 目录缺失时 docker 会创建空目录，README 会说明从现有部署复制 ONNX 模型。

- [ ] **步骤 2：创建 .env.example**

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

- [ ] **步骤 3：创建 deploy/gateway-nginx.conf.example**

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
location ^~ /emergency-plan-migration/ {
    alias {{静态目录容器内路径}}/emergency-plan-migration/;   # 例如 /etc/nginx/html/emergency-plan-migration/
    index index.html;
    try_files $uri $uri/ /emergency-plan-migration/index.html /emergency-plan-migration/m.html;
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

- [ ] **步骤 4：compose 模板校验**

```bash
docker compose -f deploy/docker-compose.prod.yml config -q
```

预期：退出码 0。若本地 5432/8000 被占用不影响 `config` 校验（只解析不启动）。

- [ ] **步骤 5：Commit**

```bash
git add deploy/docker-compose.prod.yml .env.example deploy/gateway-nginx.conf.example
git commit -m "feat(deploy): add production compose, env template and gateway nginx template"
```

---

## 任务 9：部署手册 docs/deploy/README-DEPLOY.md

**文件：** 创建 `docs/deploy/README-DEPLOY.md`

- [ ] **步骤 1：创建部署手册**

完整内容如下（一次性写入）：

````markdown
# 数字化应急预案生成系统 部署手册

> 适用：公司网关 nginx 子路径部署（参考服务器 `deom2025.sxbych.com`）。
> 原则：**改部署路径只改构建参数，不改代码**。发现需要改代码才能部署的问题，请把改动回灌仓库。

## 1. 部署拓扑

```text
浏览器
  │
  ▼
网关 nginx（proxy 容器，宿主机端口 15000）
  ├── /emergency-plan-migration/  → 静态 dist（alias 容器内路径）
  ├── /api/                       → 反代宿主机 backend 容器 :8000
  └── /uploads/                   → 反代宿主机 backend 容器 :8000
                                        │
                                        ▼
                              backend（uvicorn :8000）+ postgres:16（Debian）
```

## 2. 部署前环境预检表

| 项 | 需要确认 | 说明 |
| --- | --- | --- |
| 服务器 OS | CentOS 7 及更老？ | glibc 2.17 无法直接运行 Node 18+ 官方二进制，必须用 node:20 容器构建 |
| Docker | 版本、卷挂载是否正常 | CentOS 7 XFS+overlay2 下 postgres 必须用 Debian 版镜像（非 alpine） |
| 域名 | 例如 deom2025.sxbych.com | 网关 server_name / 证书 |
| 子路径 | 例如 /emergency-plan-migration/ | 构建参数 `VITE_BASE_PATH` 必须与网关 location 一致 |
| 宿主机 IP | backend 容器所在宿主机 IP | 网关容器内 proxy_pass 不能用 127.0.0.1 |
| 端口 | backend 8000、网关 15000 | 防火墙放行 |
| 静态目录 | 网关挂载的 html 目录 | 权限需让 nginx worker 可进入（`chmod o+x` 父目录链） |
| 镜像源 | 外网可达性 | npm 用 registry.npmmirror.com；pip 已内置清华源 |
| 数据 | 全新库还是已有数据 | 全新库走 db-init 自动恢复；已有库跳过 db-init 并手动迁移 |
| ENCRYPTION_KEY | 与数据来源一致 | 改了就解不开数据库里的 AI Key |
| SECRET_KEY | 生产化 | 建议随机长字符串；改动后所有登录态失效 |

## 3. 前端构建

CentOS 7 无法直接跑 Node 官方二进制，统一用 node:20 容器构建（react-router-dom@7.17 要求 Node >= 20）：

```bash
docker run --rm -v $PWD/frontend:/app -w /app \
  -e VITE_BASE_PATH=/emergency-plan-migration/ \
  node:20 sh -c "npm config set registry https://registry.npmmirror.com && npm ci && npm run build"
```

产物在 `frontend/dist/`。npm 报 ECONNRESET 时先确认 registry 已切到 npmmirror。

## 4. 后端部署

```bash
cp .env.example .env          # 按预检表修改 SECRET_KEY / POSTGRES_PASSWORD 等
docker compose -f deploy/docker-compose.prod.yml up -d --build
```

- 全新库：首次启动 postgres 自动执行 `db-init/` 下 SQL（01_restore.sql 为全量恢复）。
- 已有库：**不要**挂 db-init 目录（或确保文件名不与已有执行冲突），增量迁移 SQL 需手动应用。
- 首次启动后确认 chroma ONNX 模型缓存：`model-cache/chroma/onnx_models/all-MiniLM-L6-v2/` 需存在，
  否则首次向量化会尝试从外网下载（海外 S3 极慢）。从现有部署复制：
  `docker cp <旧backend容器>:/root/.cache/chroma/. model-cache/chroma/` 或直接拷贝模型目录。

## 5. 静态文件发布

```bash
mkdir -p <网关静态目录>/emergency-plan-migration
cp -r frontend/dist/* <网关静态目录>/emergency-plan-migration/
chmod o+x <网关静态目录> <网关静态目录>/emergency-plan-migration   # 父目录链都要可进入
```

## 6. 网关 nginx 配置

参照 `deploy/gateway-nginx.conf.example` 修改网关 `root_domain.conf`：

```bash
# 若从 Windows 复制过配置文件，先去掉 BOM：
sed -i '1s/^\xEF\xBB\xBF//' /home/sxby/nginx/conf/root_domain.conf
docker restart proxy
```

三条铁律：文件无 BOM；`alias` 写容器内路径；`proxy_pass` 写宿主机 IP（不用 127.0.0.1）。

## 7. 部署验证

```bash
./scripts/deploy-check.sh https://deom2025.sxbych.com/emergency-plan-migration/ https://deom2025.sxbych.com
```

全部 PASS 才算部署完成。浏览器冒烟清单：

- [ ] 桌面端：https://域名/子路径/ 登录成功，侧边菜单高亮正常
- [ ] 移动端：/子路径/m/dashboard 打开，底部 Tab 正常
- [ ] 生成预案 / 导出 / 上传图片 无 404
- [ ] PWA 可安装（manifest 正常）

## 8. 踩坑记录

| # | 坑 | 原因 | 解决 |
| --- | --- | --- | --- |
| 1 | postgres:16-alpine 启动失败 | CentOS 7 XFS+overlay2 卷挂载 initdb 写 postmaster.pid 报 Operation not permitted | 改用 postgres:16（Debian 版） |
| 2 | nginx 启动 unknown directive server | Windows 编辑的配置带 UTF-8 BOM | `sed -i '1s/^\xEF\xBB\xBF//' 文件` |
| 3 | 静态资源 404 | 父目录权限 750，nginx worker 进不去 | `chmod o+x` 父目录链 |
| 4 | 500 rewrite 重定向循环 | alias 写了宿主机路径 | alias 必须写容器内路径 |
| 5 | 构建报 EBADENGINE | react-router-dom@7.17 要求 Node >= 20，node:18 不行 | 用 node:20 容器构建 |
| 6 | npm install ECONNRESET | 外网 npm 不稳 | 切 registry.npmmirror.com |
| 7 | 网关反代 502 | proxy_pass 用 127.0.0.1 指向容器自身 | 用宿主机 IP |

## 9. 回滚

```bash
# 前端/配置：先备份再替换
cp -r <网关静态目录>/emergency-plan-migration ~/backups/emergency-plan-migration-dist-$(date +%Y%m%d)
cp /home/sxby/nginx/conf/root_domain.conf ~/backups/root_domain.conf.$(date +%Y%m%d)

# 数据库
./scripts/backup.sh    # pg_dump 到 backups/

# 旧版本包回退：解压旧 tar.gz，重新执行 4-6 节
```

## 10. 常见问题

- 页面白屏/资源 404 → 检查 `VITE_BASE_PATH` 与网关 location 是否一致，dist 是否复制到正确子目录
- 登录后跳转 404 → 检查路由 basename（代码已支持，无需改）
- 上传/接口 502 → 检查网关 proxy_pass 的宿主机 IP 与 backend 端口
- 首次生成预案卡住 → 检查 chroma ONNX 模型缓存是否存在（见第 4 节）
````

- [ ] **步骤 2：Commit**

```bash
git add docs/deploy/README-DEPLOY.md
git commit -m "docs(deploy): add deployment manual with preflight checklist and pitfalls"
```

---

## 任务 10：打包脚本 package-release.sh

**文件：** 创建 `scripts/package-release.sh`

- [ ] **步骤 1：创建脚本**

```bash
#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  echo "用法: VITE_BASE_PATH=/子路径/ ./scripts/package-release.sh <版本号>"
  exit 1
fi
if [[ ! "$VERSION" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "版本号只允许字母/数字/._-"
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE_PATH="${VITE_BASE_PATH:-/emergency-plan-migration/}"
OUT_ROOT="$ROOT/release"
STAGE="$OUT_ROOT/emergency-plan-migration-$VERSION"

echo "==> 1/4 构建前端（node:20 容器，VITE_BASE_PATH=$BASE_PATH）"
docker run --rm -v "$ROOT/frontend:/app" -w /app -e VITE_BASE_PATH="$BASE_PATH" \
  node:20 sh -c "npm config set registry https://registry.npmmirror.com && npm ci && npm run build"

echo "==> 2/4 组装暂存目录"
mkdir -p "$OUT_ROOT"
if [[ -e "$STAGE" ]]; then
  rm -rf -- "$STAGE"
fi
mkdir -p "$STAGE"

cp -r "$ROOT/backend" "$STAGE/backend"
find "$STAGE/backend" -type d \( -name __pycache__ -o -name .venv \) -prune -exec rm -rf {} +
rm -rf "$STAGE/backend/uploads" "$STAGE/backend/exports"

mkdir -p "$STAGE/frontend"
cp -r "$ROOT/frontend/dist" "$STAGE/frontend/dist"
cp -r "$ROOT/deploy" "$STAGE/deploy"
cp -r "$ROOT/scripts" "$STAGE/scripts"
cp "$ROOT/.env.example" "$STAGE/.env.example"

if [[ -d "$ROOT/db-init" ]]; then
  cp -r "$ROOT/db-init" "$STAGE/db-init"
else
  echo "[提示] 未找到 db-init/，请自行放入数据库恢复 SQL（db-init/01_restore.sql）"
fi
if [[ -d "$ROOT/model-cache/chroma" ]]; then
  cp -r "$ROOT/model-cache" "$STAGE/model-cache"
else
  echo "[提示] 未找到 model-cache/chroma/，请从现有部署复制 ONNX 模型缓存"
fi

echo "==> 3/4 打包"
cd "$OUT_ROOT"
tar czf "emergency-plan-migration-$VERSION.tar.gz" "emergency-plan-migration-$VERSION"
sha256sum "emergency-plan-migration-$VERSION.tar.gz" > "emergency-plan-migration-$VERSION.tar.gz.sha256"

echo "==> 4/4 产物"
ls -lh "$OUT_ROOT/emergency-plan-migration-$VERSION.tar.gz" \
      "$OUT_ROOT/emergency-plan-migration-$VERSION.tar.gz.sha256"
```

- [ ] **步骤 2：bash 语法校验 + 可执行权限**

```bash
bash -n scripts/package-release.sh
chmod +x scripts/package-release.sh
```

预期：`bash -n` 无输出（退出码 0）。

- [ ] **步骤 3：.gitignore 追加 release/**

在根 `.gitignore` 末尾追加：

```gitignore
# 打包产物
release/
```

- [ ] **步骤 4：Commit**

```bash
git add scripts/package-release.sh .gitignore
git commit -m "feat(deploy): add release packaging script"
```

---

## 任务 11：验证脚本 deploy-check.sh

**文件：** 创建 `scripts/deploy-check.sh`

- [ ] **步骤 1：创建脚本**

```bash
#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "用法: ./scripts/deploy-check.sh <站点URL> [API URL] [--skip-api]"
  echo "示例: ./scripts/deploy-check.sh https://deom2025.sxbych.com/emergency-plan-migration/ https://deom2025.sxbych.com"
  echo "      ./scripts/deploy-check.sh http://127.0.0.1:19090/emergency-plan-migration/ http://127.0.0.1:8000"
}

SITE_URL="${1:-}"
API_URL="${2:-}"
SKIP_API=0
for arg in "$@"; do
  if [[ "$arg" == "--skip-api" ]]; then SKIP_API=1; fi
done

if [[ -z "$SITE_URL" ]]; then
  usage
  exit 1
fi

SITE="${SITE_URL%/}"
PASS=0
FAIL=0

pass() { echo "PASS  $1"; PASS=$((PASS + 1)); }
fail() { echo "FAIL  $1"; FAIL=$((FAIL + 1)); }

# 1. 首页
if curl -fs -o /dev/null "$SITE/"; then pass "首页 $SITE/"; else fail "首页 $SITE/"; fi

# 2. 移动端
if curl -fs -o /dev/null "$SITE/m/dashboard"; then pass "移动端 /m/dashboard"; else fail "移动端 /m/dashboard"; fi

# 3. 静态资源（从 index.html 提取）
assets="$(curl -fs "$SITE/" | grep -oE 'assets/[^"'"'"' ]+\.(js|css)' | sort -u || true)"
if [[ -z "$assets" ]]; then
  fail "未从 index.html 提取到静态资源"
else
  for a in $assets; do
    if curl -fs -o /dev/null "$SITE/$a"; then pass "资源 $a"; else fail "资源 $a"; fi
  done
fi

# 4. PWA manifest
if curl -fs -o /dev/null "$SITE/manifest.webmanifest"; then pass "PWA manifest"; else fail "PWA manifest"; fi

# 5-6. API
if [[ "$SKIP_API" == "1" ]]; then
  echo "SKIP  API 检查（--skip-api）"
else
  API="${API_URL:-$(echo "$SITE" | sed -E 's#(/[^/]+)?/?$##')}"
  if curl -fs -o /dev/null "$API/api/v1/health"; then pass "API /api/v1/health"; else fail "API /api/v1/health"; fi
  up_code="$(curl -s -o /dev/null -w '%{http_code}' "$API/uploads/" || true)"
  if [[ "$up_code" != 5* ]]; then pass "上传 /uploads/ 返回 $up_code（非 5xx 可接受）"; else fail "上传 /uploads/ 返回 $up_code"; fi
fi

# 7. 深链接 SPA 回退
if curl -fs "$SITE/enterprises" 2>/dev/null | grep -q 'id="root"'; then
  pass "深链接 SPA 回退"
else
  fail "深链接 SPA 回退"
fi

# 8. 无尾斜杠
no_slash="${SITE%/}"
ns_code="$(curl -s -o /dev/null -w '%{http_code}' "$no_slash" || true)"
ns_loc="$(curl -s -D - -o /dev/null "$no_slash" | grep -i '^location:' | tr -d '\r' | awk '{print $2}' || true)"
if [[ "$ns_code" == "301" || "$ns_code" == "308" ]] && [[ "$ns_loc" == */ ]]; then
  pass "无尾斜杠 301/308 → 带尾斜杠"
elif [[ "$ns_code" == "200" ]]; then
  pass "无尾斜杠直接 200（容器直连形态可接受）"
else
  fail "无尾斜杠返回 $ns_code"
fi

echo "----------------------------------------"
echo "通过 $PASS 项，失败 $FAIL 项"
if [[ "$FAIL" -gt 0 ]]; then
  echo "部署验证未通过"
  exit 1
fi
echo "部署验证通过"
```

- [ ] **步骤 2：bash 语法校验 + 可执行权限**

```bash
bash -n scripts/deploy-check.sh
chmod +x scripts/deploy-check.sh
```

预期：`bash -n` 无输出（退出码 0）。

- [ ] **步骤 3：Commit**

```bash
git add scripts/deploy-check.sh
git commit -m "feat(deploy): add post-deploy verification script"
```

---

## 任务 12：根路径回归 + 子路径构建验证

**文件：** 无（验证）

- [ ] **步骤 1：根路径构建回归**

```bash
cd frontend
npm run build
grep -o 'src="[^"]*\.js"' dist/index.html | head -3
```

预期：构建成功；`src` 引用以 `./assets/` 或 `/assets/` 开头（**无** `/emergency-plan-migration/` 前缀）。

- [ ] **步骤 2：子路径构建**

```bash
$env:VITE_BASE_PATH="/emergency-plan-migration/"
npm run build
grep -o 'src="[^"]*\.js"' dist/index.html | head -3
```

预期：`src="/emergency-plan-migration/assets/...` 带前缀；`dist/manifest.webmanifest` 的 `start_url` 为 `/emergency-plan-migration/m/dashboard`、`scope` 为 `/emergency-plan-migration/`。

（PowerShell 会话注意：用完取消变量 `Remove-Item Env:VITE_BASE_PATH`，避免污染后续本地构建。）

- [ ] **步骤 3：恢复默认构建产物**

```bash
Remove-Item Env:VITE_BASE_PATH
npm run build
```

预期：构建成功，回到根路径产物（保证本地后续使用正常）。

---

## 任务 13：端到端演练

**文件：** 无（验证 + 收尾）

- [ ] **步骤 1：启动后端栈（复用根 compose）**

```bash
cd "C:\Users\55061\Documents\数字化预案自动生成 2"
docker compose up -d postgres backend
curl -fs http://127.0.0.1:8000/api/v1/health
```

预期：health 返回 200（等待就绪，最多 90 秒）。

- [ ] **步骤 2：用 frontend/nginx.conf 模拟网关子路径托管**

```bash
docker run --rm -d --name deploy-check-nginx \
  -p 19090:8080 \
  -v "${PWD}/frontend/dist:/usr/share/nginx/html:ro" \
  -v "${PWD}/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  nginx:stable-alpine
curl -fs -o /dev/null http://127.0.0.1:19090/emergency-plan-migration/
```

预期：首页 200（此时 dist 为任务 12 步骤 3 的根路径产物，子路径下资源会 404 属预期；本步骤只验证 nginx 路由可到达）。

- [ ] **步骤 3：子路径产物 + deploy-check 全绿**

```bash
cd frontend
$env:VITE_BASE_PATH="/emergency-plan-migration/"
npm run build
Remove-Item Env:VITE_BASE_PATH
docker restart deploy-check-nginx
cd ..
bash scripts/deploy-check.sh http://127.0.0.1:19090/emergency-plan-migration/ http://127.0.0.1:8000
```

预期：全部 PASS，最后输出 `部署验证通过`，退出码 0。

- [ ] **步骤 4：打包演练**

```bash
cd "C:\Users\55061\Documents\数字化预案自动生成 2"
./scripts/package-release.sh 0.1.0-test
tar tzf release/emergency-plan-migration-0.1.0-test.tar.gz | head -20
```

预期：产物生成，结构含 backend/frontend/dist/deploy/scripts/.env.example/db-init 或对应提示；SHA256 文件存在。

- [ ] **步骤 5：清理演练容器与临时产物**

```bash
docker rm -f deploy-check-nginx
rm -rf release/emergency-plan-migration-0.1.0-test release/emergency-plan-migration-0.1.0-test.tar.gz*
```

（删除前确认路径均在 `release/` 目录内。）

- [ ] **步骤 6：收尾**

```bash
git diff --check
npx tsc -b
npx vitest run
```

预期：`git diff --check` 干净；tsc 0；vitest 全绿（含任务 1 新增 4 项）。

---

## 任务 14：合并回 master（用户确认后执行）

**文件：** 无（Git 操作）

- [ ] **步骤 1：合并**

```bash
cd "C:\Users\55061\Documents\数字化预案自动生成 2"
git merge --no-ff codex/deploy-readiness
```

预期：无冲突（并行会话改动的文件与本计划不重叠；如遇冲突由执行者解决并回归门禁）。

- [ ] **步骤 2：清理 worktree**

```bash
git worktree remove .worktrees/deploy-readiness
git branch -d codex/deploy-readiness
```

---

## 自检记录（执行前已做）

1. **规格覆盖度**：D-1→任务 1-6（含 TDD 测试、全仓扫描）；D-2→任务 7-8；D-3→任务 9；D-4→任务 10；
   D-5→任务 11；D-6→任务 13；门禁→任务 0/12/13 步骤 6；回滚→README §9 + 任务 14。无遗漏。
2. **占位符扫描**：无 TODO/待定；所有脚本、配置、文档内容均为完整可执行文本。
3. **类型一致性**：`APP_BASE`/`stripAppBase` 在任务 1 定义、任务 3-5 引用，签名一致（
   `stripAppBase(pathname, appBase = APP_BASE)`）；`BASE_PATH` 在任务 2 定义并用于 manifest 与 base；
   `deploy-check.sh` 参数顺序在脚本 usage 与任务 13 命令一致。
