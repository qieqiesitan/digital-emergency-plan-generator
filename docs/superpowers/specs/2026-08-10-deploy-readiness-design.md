# 部署可交付性增强设计（方案 A）

日期：2026-08-10
状态：已获用户批准（设计稿口头确认），本文件为正式规格
范围：前端子路径参数化回灌 + 部署配置修正 + 部署手册 + 打包/验证脚本

## 一、背景

2026-08-06 交付的 docker-compose 迁移包（`emergency-plan-migration.tar.gz`，126MB）在公司服务器
`deom2025.sxbych.com` 部署时大量报错。公司开发现场修改了 11 个文件后成功，并将改动整理为
`变更说明.md`。

根因有三层：

1. **架构假设冲突**：交付物按「独立 docker-compose 栈 + 根路径 `/`」设计，公司服务器是「网关
   nginx（proxy 容器，宿主机端口 15000）+ 子路径 `/emergency-plan-migration/` 托管静态 +
   `/api/`、`/uploads/` 反代」拓扑。前端代码里写死根路径假设（vite base、react-router basename、
   pathname 判断、菜单 key、硬编码跳转），子路径下全部失效，且只能改代码解决。
2. **环境差异**：CentOS 7（glibc 2.17）+ 网关 nginx 引发的 6 条踩坑（见本文档 §7），全部是现场
   试出来的，此前无任何文档沉淀。
3. **经验未回灌**：11 处改动零回灌仓库；`docker-compose.yml` 仍是 `postgres:16-alpine`（踩坑记录
   明确该镜像在客户 CentOS 7 上必挂）；无生产部署手册、网关 nginx 模板、预检/验证脚本。

## 二、目标与非目标

### 目标

1. 前端支持任意部署子路径，且**默认行为与现状完全一致**（本地开发/构建零影响）。
2. 把本次踩坑固化为仓库内的部署配置、手册与脚本，公司开发拿到包后「填参数 → 跑脚本 → 按手册
   核对」，不再改代码。
3. 提供可复用的打包脚本与部署后验证脚本，让「部署完成」有客观判据。

### 非目标

- 不做运行时 base 注入（方案 C 特性）：同一份 dist 支持任意路径需要运行时改造，成本高，本次不做。
- 不做 CI/CD 发布流水线。
- 不改后端业务代码。
- 不迁移公司服务器现状（其当前已部署版本以变更说明为基准，仅文档记录）。
- 不处理 `.env.example` 中已有的明文 QCC API key（现状遗留，仅在手册中提示生产环境注意）。

## 三、设计决策

### D1 子路径参数化方式：环境变量 `VITE_BASE_PATH`

- `vite.config.ts` 读取 `process.env.VITE_BASE_PATH`，去掉尾部 `/` 后：
  - `base` = `VITE_BASE_PATH` 非空 ? `VITE_BASE_PATH + "/"` : `"/"`；
  - PWA manifest `start_url` = `VITE_BASE_PATH + "/m/dashboard"`（空时即 `/m/dashboard`，与现状
    一致）；
  - PWA manifest `scope` = `VITE_BASE_PATH` 非空 ? `VITE_BASE_PATH + "/"` : `"/"`。
- 不用 `vite build --base` CLI 参数，因为它只改 `base`、不联动 PWA manifest，子路径下 PWA 会退化。
- 前端代码统一从 `import.meta.env.BASE_URL` 派生 `APP_BASE`，不读环境变量（构建期注入，运行时一致）。

### D2 部署产物形态

- 生产部署 = 后端 compose（postgres + backend）+ 网关 nginx 托管静态 dist + `/api/`、`/uploads/`
  反代。前端容器（vite dev / shuzihuayuan）仅开发用，生产 compose 不含（注释说明可选启用）。
- 打包产物包含 `backend/` 源码，服务器上 `docker compose build`，不引入镜像仓库依赖（与上次一致）。

## 四、任务分解

### D-1 前端子路径参数化（回灌 11 处改动）

1. `frontend/vite.config.ts`
   - 新增 `const BASE_PATH = (process.env.VITE_BASE_PATH || "").replace(/\/+$/, "");`
   - `base` 按 §D1 规则派生；PWA manifest `start_url`/`scope` 同步派生。
   - 保留现有 `skipPWA`（Node 24 workbox 兼容）逻辑与 `qiankun("emergency-plan", ...)` 配置不变。
2. `frontend/src/utils/platform.ts`
   - 新增：
     ```ts
     /** 应用部署子路径前缀（生产为 /emergency-plan-migration，开发为 ""） */
     export const APP_BASE = import.meta.env.BASE_URL.replace(/\/+$/, "");

     /** 从 pathname 中剥离应用子路径前缀，如 /emergency-plan-migration/m/login -> /m/login */
     export function stripAppBase(pathname: string): string {
       if (!APP_BASE) return pathname;
       return pathname.startsWith(APP_BASE) ? pathname.slice(APP_BASE.length) : pathname;
     }
     ```
3. `frontend/src/routes/index.tsx`、`frontend/src/mobile/routes.tsx`
   - `createBrowserRouter(..., { basename: APP_BASE || undefined })`。
   - `MobileRedirect`（`window.location.replace(pathname + search)`）不改：其行为不依赖前缀，路由
     basename 接管后行为不变。
4. `frontend/src/entry.tsx`、`frontend/src/main.tsx`
   - `isMobilePath()` 改为 `const p = stripAppBase(window.location.pathname);` 再判断 `/m`。
5. `frontend/src/layouts/MainLayout.tsx`
   - `selectedKeys={[stripAppBase(location.pathname)]}`（当前第 155 行）。
6. `frontend/src/mobile/layouts/MainTabsLayout.tsx`
   - 统一 `const pathname = stripAppBase(location.pathname);`，`shouldHideTabBar(pathname)`、
     activeTab 匹配、`key={pathname}` 均用剥离后的值。
7. `frontend/src/components/plan/AIGenerateButton.tsx`
   - 核对：当前无 `location.href`/`settings/ai-config` 硬编码（2026-08-10 核实），如实现时确认无
     根路径跳转则不改；若存在 `navigate("/settings/ai-config")` 由 basename 自动处理，也不改；仅当
     存在 `location.href` 等原生跳转才拼接 `APP_BASE`。
8. `frontend/nginx.conf`
   - 增加子路径 location，与变更说明 §四 完全一致（已上线验证）：
     ```nginx
     location /emergency-plan-migration/ {
         alias /usr/share/nginx/html/;
         try_files $uri $uri/ /emergency-plan-migration/index.html /emergency-plan-migration/m.html;
     }
     ```
   - 附注释：此形态下 dist 位于容器 html 根目录；网关侧形态见 `deploy/gateway-nginx.conf.example`。
9. 全仓扫描确认无遗漏：`rg "location\.href = \"/|window\.location\.(href|replace|assign)\(\"/|navigate\(\"/" frontend/src`，
   逐一判断是否需剥前缀/拼 APP_BASE。

### D-2 部署配置修正

1. 根 `docker-compose.yml`：`postgres:16-alpine` → `postgres:16`（Debian）。数据在命名卷
   `shuzihuayuan_pgdata`（external）中，PG 主版本不变，重建容器数据不丢。
2. 新增 `deploy/docker-compose.prod.yml`（基于迁移包 compose 收敛）：
   - `postgres:16`（Debian）+ `pgdata` 命名卷（非 external）+ `./db-init:/docker-entrypoint-initdb.d:ro`
     自动恢复 + healthcheck；
   - backend：`build: ./backend`、密钥走 `${VAR:-default}`、`./model-cache/chroma:/root/.cache/chroma`
     挂载、exports/uploads 持久化、`uvicorn ... --workers 4`；
   - frontend/shuzihuayuan 服务以注释给出（公司拓扑由网关托管静态，不启用）。
3. 新增 `deploy/gateway-nginx.conf.example`（基于变更说明 §五）：
   - 无尾斜杠 301、`^~ /emergency-plan-migration/` 静态 location（alias 容器内路径 + try_files 兜底
     index/m.html）、`/api/`、`/uploads/` 反代；
   - 域名、宿主机 IP、静态目录以占位符 `{{...}}` 标注，并附三条关键注释：alias 必须容器内路径、
     proxy_pass 必须宿主机 IP（不可 127.0.0.1）、文件勿带 UTF-8 BOM。

### D-3 部署手册 `docs/deploy/README-DEPLOY.md`

章节：
1. 适用拓扑（网关 nginx 子路径 + 后端容器，文字描述 + 请求链路示意）。
2. 部署前环境预检表（表格，逐项确认）：OS/glibc、docker 版本、域名、子路径、宿主机 IP、端口、
   静态目录路径与权限、镜像源可达性、全新库 vs 已有数据、`ENCRYPTION_KEY` 一致性、`SECRET_KEY`
   生产化。
3. 前端构建：node:20 容器 + npmmirror + `VITE_BASE_PATH`（含 CentOS 7 无法直接跑 Node 官方二进制
   的原因）。
4. 后端部署：`docker compose -f deploy/docker-compose.prod.yml up -d --build`；db-init 自动恢复；
   增量迁移 SQL 需手动应用（记录路径约定）。
5. 静态发布：`cp -r dist/* <网关静态目录>/`；父目录权限 `chmod o+x`。
6. 网关 nginx：配置片段 + `docker restart proxy`。
7. 验证：`scripts/deploy-check.sh` + 浏览器冒烟清单（登录/桌面菜单/移动端/生成预案/导出）。
8. 踩坑记录 6 条（变更说明 §七 迁移并扩充说明）。
9. 回滚：dist 与 nginx conf 备份恢复、`pg_dump` 备份命令、旧版本包回退。
10. 常见问题（BOM、alias、proxy_pass、权限、镜像源、EBADENGINE）。

### D-4 打包脚本 `scripts/package-release.sh`

- 用法：`VITE_BASE_PATH=/emergency-plan-migration/ ./scripts/package-release.sh <版本号>`
  （`VITE_BASE_PATH` 默认 `/emergency-plan-migration/`）。
- 流程（`set -euo pipefail`）：
  1. 校验版本号非空、仓库根目录可识别；
  2. 用 node:20 容器构建前端（npmmirror + `VITE_BASE_PATH`），失败即中止；
  3. 组装暂存目录 `release/emergency-plan-migration-<版本>/`：`backend/`（排除 `__pycache__`、
     `.venv`、`uploads` 数据）、`frontend/dist/`、`deploy/`（prod compose + 网关模板 + 手册）、
     `scripts/`（deploy/backup/deploy-check）、`.env.example`；
  4. `db-init/`、`model-cache/chroma/`：目录存在则收录，不存在则打印提示（数据/模型由使用者提供），
     不中断；
  5. 产出 `release/emergency-plan-migration-<版本>.tar.gz` + `.sha256`，打印产物清单。
- 说明：脚本用 bash（服务器/Git Bash/WSL 运行）；Windows 原生 PowerShell 用户走 Git Bash。

### D-5 验证脚本 `scripts/deploy-check.sh`

- 用法：`./scripts/deploy-check.sh <站点URL> [API URL]`
  - 例：`./scripts/deploy-check.sh https://deom2025.sxbych.com/emergency-plan-migration/ https://deom2025.sxbych.com`
- 检查项（任一失败打印 FAIL 并以非零退出）：
  1. 站点 URL 返回 200（index.html 命中）；
  2. `/m/dashboard` 返回 200（m.html 命中）；
  3. 从 index.html 提取全部 `assets/*.js|css` 引用逐个 200；
  4. `manifest.webmanifest` 200 且 `start_url`/`scope` 含子路径；
  5. `API_URL/api/v1/health` 200；
  6. `API_URL/uploads/` 非 5xx（403/404 可接受）；
  7. 深链接（子路径 + `/enterprises`）返回 index.html（SPA fallback）；
  8. 无尾斜杠 URL 返回 301 → 带尾斜杠。
- 输出 PASS/FAIL 汇总表，全部通过打印「部署验证通过」。

### D-6 端到端演练

- 本地以 nginx（或 python http.server）模拟网关子路径托管 dist + 反代本地后端 8000；
- 跑 `deploy-check.sh` 全绿；
- 跑 `package-release.sh` 产出真实包，抽查目录结构与 `tar tzf` 清单。

## 五、门禁与验证

1. `npx tsc -p tsconfig.app.json --noEmit` 退出码 0；
2. `npx eslint` 改动文件零新增（与 HEAD 基线逐项对比）；
3. `npx vitest run` 全量通过（基线 48）；
4. 根路径回归：默认构建产物 index.html 资源引用无子路径前缀，dev 冒烟通过；
5. 子路径验证：`VITE_BASE_PATH=/emergency-plan-migration/` 构建产物资源引用带前缀，静态托管下
   首页/m.html/深链接/PWA manifest 均正确；
6. `bash -n scripts/package-release.sh scripts/deploy-check.sh` 通过；
7. `git diff --check` 干净；新增行不超 100 字符（沿用仓库软约定）；
8. 不改动后端业务代码（仅新增部署配置/文档/脚本）。

## 六、风险与回滚

| 风险 | 缓解 |
| --- | --- |
| basename 改动引入路由回归 | 根路径回归 + 子路径演练双重验证；仓库既有 tsc/eslint/vitest 门禁 |
| 本地 docker compose 换镜像 | PG16 主版本不变、数据卷兼容；首次拉取 Debian 镜像耗时 |
| 隐藏硬编码根路径跳转 | D-1.9 全仓 `rg` 扫描逐一判断 |
| 打包脚本在 Windows 环境不可用 | 明确要求 bash 环境（Git Bash/WSL），文档注明 |
| 公司开发仍按旧习惯改代码 | 手册「原则」段注明：改路径只需改构建参数，改代码需回灌仓库 |
| 密钥泄露风险（QCC key 明文） | 非本次范围；手册提示生产替换 SECRET_KEY、注意 .env 权限 |

回滚：本次改动全部可逆——前端改动 `git undo` 或 `git checkout --` 单文件恢复；镜像改动
`docker compose up -d` 重建即可；新增文件删除即消失，不影响运行。

## 七、变更文件清单

### 修改

| 文件 | 内容 |
| --- | --- |
| `frontend/vite.config.ts` | base + PWA manifest 参数化 |
| `frontend/src/utils/platform.ts` | 新增 `APP_BASE`、`stripAppBase` |
| `frontend/src/routes/index.tsx` | basename |
| `frontend/src/mobile/routes.tsx` | basename |
| `frontend/src/entry.tsx` | isMobilePath 剥前缀 |
| `frontend/src/main.tsx` | isMobilePath 剥前缀 |
| `frontend/src/layouts/MainLayout.tsx` | selectedKeys 剥前缀 |
| `frontend/src/mobile/layouts/MainTabsLayout.tsx` | Tab 判断剥前缀 |
| `frontend/src/components/plan/AIGenerateButton.tsx` | 视核对结果（预期不改） |
| `frontend/nginx.conf` | 子路径 location |
| `docker-compose.yml` | postgres 镜像换 Debian 版 |

### 新增

| 文件 | 内容 |
| --- | --- |
| `deploy/docker-compose.prod.yml` | 生产后端栈 |
| `deploy/gateway-nginx.conf.example` | 网关侧 nginx 模板 |
| `docs/deploy/README-DEPLOY.md` | 部署手册 |
| `scripts/package-release.sh` | 打包脚本 |
| `scripts/deploy-check.sh` | 部署验证脚本 |

## 八、落地顺序

1. D-1 前端参数化（门禁 1-5 全绿）；
2. D-2/D-3 配置与手册；
3. D-4/D-5 脚本（门禁 6）；
4. D-6 端到端演练（门禁 7-8），完成后交付说明。
