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
  node:20 sh -c "npm config set registry https://registry.npmmirror.com && (npm ci 2>/dev/null || npm install) && npm run build"
```

> 说明：`npm ci` 失败（lockfile 与 package.json 不同步等）时自动回退 `npm install`，保证干净环境可构建；lockfile 同步问题见项目技术债待办。

> 注意：生产构建必须用 node:20 —— Node ≥ 24 会禁用 PWA，导致 `manifest.webmanifest` 缺失、deploy-check 第 4 项失败。

产物在 `frontend/dist/`。npm 报 ECONNRESET 时先确认 registry 已切到 npmmirror。

## 4. 后端部署

```bash
cp .env.example .env          # 按预检表修改 SECRET_KEY / POSTGRES_PASSWORD 等
docker compose -f deploy/docker-compose.prod.yml --project-directory . up -d --build
```

- 一键方式：`./scripts/deploy.sh`（自动创建 .env、构建并启动、等待 `/api/health` 就绪后提示剩余步骤）。
- 包根快捷方式：发布包根目录已附带 `docker-compose.yml`（与 `deploy/docker-compose.prod.yml` 同内容），
  也可直接在包根执行 `docker compose up -d --build`，效果相同。
- 注意：`--project-directory .` 必须带，否则 compose 的相对路径会按 `deploy/` 目录解析，构建必然失败。
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
# 静态自检（2026-09-19 新增）：缺哪条直接列出来
./scripts/check-gateway-config.sh /home/sxby/nginx/conf/root_domain.conf
docker restart proxy
```

三条铁律：文件无 BOM；`alias` 写容器内路径；`proxy_pass` 写宿主机 IP（不用 127.0.0.1）。

**新增两条易漏项（2026-09-19 实测踩坑）**：

1. `client_max_body_size 25m;` —— nginx 默认 **1MB**，应用侧上限是 **20MB**；不改的话
   通过网关上传 >1MB 的 Excel / PDF / 计划图会被网关**直接 413**，后端日志里毫无记录，
   用户只看到"上传失败"。
2. `/api/` 段必须 **`proxy_buffering off` + `proxy_http_version 1.1` + `proxy_read_timeout ≥ 300s`**——
   否则 SSE（流式生成 / AI 对话）会被攒满缓冲才下发，前端表现为"一直转圈到结束才出现内容"，
   长生成还会被默认 60s 读超时掐成 502/504。
   后端所有 SSE 响应已带 `X-Accel-Buffering: no`（见 `backend/app/services/sse_utils.py`），
   nginx 原生识别该头，属于第二道保险。
3. 真实 IP：`X-Real-IP` / `X-Forwarded-For` 必须透传，否则审计日志与登录限流会把
   所有用户按网关 IP 计数（真实用户会互相顶掉限流额度）。

## 7. 部署验证

```bash
./scripts/deploy-check.sh https://deom2025.sxbych.com/emergency-plan-migration/ https://deom2025.sxbych.com
```

全部 PASS 才算部署完成。浏览器冒烟清单：

- [ ] 桌面端：https://域名/子路径/ 登录成功，侧边菜单高亮正常
- [ ] 移动端：/子路径/m/dashboard 打开，底部 Tab 正常
- [ ] 生成预案 / 导出 / 上传图片 无 404
- [ ] PWA 可安装（manifest 正常）

### 7.1 聊天助手工具层自检（零模型额度）

聊天助手的 37 个工具由模型按需调用，坏掉时只表现为"助手答不出来"，很难定位。
这个脚本**绕过 LLM 直接调用工具层**，把"工具层"与"模型层"分开验证：

```bash
# 只读工具（默认；不写任何业务数据）
docker cp backend/scripts/check_chat_tools.py emergency-plan-backend:/tmp/
docker exec emergency-plan-backend sh -c \
  'cd /app && PYTHONPATH=/app python /tmp/check_chat_tools.py --email <管理员邮箱>'

# 追加写入闭环（资源/预案/企业 建→查→改→删，自建自删）
docker exec emergency-plan-backend sh -c \
  'cd /app && PYTHONPATH=/app python /tmp/check_chat_tools.py --include-write'
```

期望输出 `合计 18/18 PASS` 与 `写入闭环全部通过`。
**2026-09-18 实测**：修复前 8/18 —— 一个工具读了不存在的字段，且失败后的一律回滚会让
随后 9 个工具连锁报 `greenlet_spawn has not been called`（详见 `docs/系统诊断报告-v6-2026-09-18.md` N-23）。

> 为什么必须在容器里跑：脚本要用容器的 `DATABASE_URL` 与本地向量库/图谱文件。

### 7.2 没装 APScheduler / 调度器降级时的手动扫描

后端默认用 APScheduler 每 5 分钟跑一轮周期任务（隐患到期建任务、超期提醒、作业票过期）。
若镜像里没有 APScheduler（`main.py` 会打印"APScheduler 启动失败，隐患定时扫描已降级跳过"），
用外部 cron 调用管理员端点替代：

```bash
curl -s -X POST https://<域名>/api/v1/admin/maintenance/run-scans \
  -H "Authorization: Bearer <管理员 token>"
# → {"data":{"hazard_scans":{...},"expired_tickets":1,"skipped_by_lock":false}}
```

该端点是幂等的（扫描内部都有防重），可安全地每 5 分钟触发一次；
`skipped_by_lock=true` 表示本轮被其他 worker 抢到，属正常。

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

## 10. 升级（增量升级包）

### 10.1 安装包 vs 升级包

| 维度 | 安装包（全量） | 升级包（`--upgrade`） |
| --- | --- | --- |
| 适用场景 | 全新部署 / 整站恢复 | 已有部署只更新系统、不触碰数据 |
| 内容 | backend + frontend/dist + deploy/ + 手册 + db-init/（如提供）+ model-cache/（如提供）+ .env.example | backend（git 跟踪内容，含全部 `db_migration_*.sql`）+ frontend/dist + deploy/ + docs/ + scripts/（白名单）+ .env.example + 包根 `VERSION` + `CHANGELOG.md` |
| 不含 | — | db-init/、model-cache/、backend/uploads、backend/exports |
| 产物命名 | `emergency-plan-migration-<版本>.tar.gz` | `emergency-plan-migration-<版本>-upgrade.tar.gz` |

原则：**升级包只更新代码与配置，不覆盖公司服务器数据**。`backend/uploads`、`backend/exports`
（compose 挂载的运行时数据）、`backups/`、`model-cache/`、`.env` 与 postgres 数据卷 `pgdata`
均不在升级包内，解压覆盖部署目录后原样保留。

### 10.2 upgrade.sh 用法

```bash
用法: ./scripts/upgrade.sh <版本号> [网关静态目录] [站点URL] [API URL]
```

步骤：

```bash
# 1) 在服务器部署目录解压升级包覆盖旧代码（strip 顶层包目录名）
cd <部署根目录>                       # 例如 /home/sxby/emergency-plan-migration
tar xzf emergency-plan-migration-<版本>-upgrade.tar.gz -C . --strip-components=1

# 2) 执行升级脚本
./scripts/upgrade.sh <版本号> [网关静态目录] [站点URL] [API URL]
```

脚本行为：

1. 校验包根 `VERSION` 文件存在且与参数一致；
2. `./scripts/backup.sh` 强制备份数据库（失败即中止，不进入替换阶段）；
3. 确认 backend 代码已替换（解压时完成），保留 `.env`、数据卷、`backups/`、`uploads/`、`exports/`、`model-cache/`；
4. 传入网关静态目录则自动 `cp -r frontend/dist/*` 到该目录；缺省则打印「请人工更新网关静态目录」；
5. `docker compose -f deploy/docker-compose.prod.yml --project-directory . up -d --build`；
6. 传入站点/API URL 则自动执行 `./scripts/deploy-check.sh`；缺省交互式询问，仍缺失则跳过并提示手动验证。

### 10.3 迁移自动应用与失败处理

- backend 启动时迁移运行器基于 `schema_migrations` 表自动应用增量迁移：
  已有记录跳过、新增 `db_migration_*.sql` 逐脚本单事务执行（失败整体回滚且不记录）、
  无记录时（如从旧版本升级上来的既有库）仅将升级前版本已含的基线脚本记为
  baseline（只记录不执行——其变更在既有库中已存在），**本版本新增迁移自动按序应用**。
- 0.2.0 → 0.3.0 升级：首次启动会自动应用本版本新增迁移（含权限点与数据清理），
  无需手工执行 SQL。
- 逃生口：**空库**需执行全部捆绑迁移时，设置 backend 进程环境变量 `MIGRATE_FRESH=1`
  （compose 已从 `.env` 透传，见 `.env.example` 说明）。
- 失败处理（fail-fast）：迁移失败 → 事务回滚不记录 → backend 进程以非 0 退出
  （容器重启循环、日志可见、数据安全）；升级脚本在替换前强制 `backup.sh`，
  若部署验证失败，用 `backups/` 最新备份回滚数据库。

### 10.4 升级前检查清单

- [ ] 已确认目标版本号，且与升级包内 `VERSION` 文件一致；
- [ ] 已确认网关静态目录路径（`frontend/dist` 需复制到网关挂载的 html 目录）；
- [ ] 已确认站点 URL / API URL（用于第 6 步自动验证）；
- [ ] 升级脚本会强制备份，但建议提前自行 `./scripts/backup.sh` 再确认一次；
- [ ] 旧栈需保持运行中：backup.sh 依赖 compose postgres 容器在线执行 pg_dump；
      若已停止需先 `docker compose -f deploy/docker-compose.prod.yml --project-directory . up -d postgres` 再升级；
- [ ] 服务器磁盘空间：需容纳新后端镜像构建与 `backups/` 增量。

迁移规范详见 `docs/reference/migration-guide.md`。

## 11. 加密密钥轮换（W2 起支持不停机轮换）

背景：新密文使用 **AES-GCM**（`gcm$` 前缀）；历史 **AES-ECB** 密文在轮换完成前仍可解密，
因此可以先上新密钥、再批量重加密、最后移除旧密钥，全程无需停机（重启一次即可）。

覆盖范围：`ai_configs.api_key_encrypted`、`third_party_config`（secret 类型）。

```bash
# 0) 先备份
./scripts/backup.sh

# 1) 生成新密钥，编辑 .env：
#    ENCRYPTION_KEY=<新随机值>
#    ENCRYPTION_KEY_LEGACY=<旧的 ENCRYPTION_KEY 值>
#    （旧值原样保留在 LEGACY 中，逗号分隔可填多把）
python -c "import secrets; print(secrets.token_hex(32))"

# 2) 重启后端使新密钥生效（此时新旧密文都能读）
docker compose -f deploy/docker-compose.prod.yml --project-directory . up -d backend

# 3) 先 dry-run 看要重加密多少行，再执行
docker exec -e PYTHONPATH=/app -w /app emergency-plan-backend \
  python /app/scripts/rotate_encryption_key.py --dry-run
docker exec -e PYTHONPATH=/app -w /app emergency-plan-backend \
  python /app/scripts/rotate_encryption_key.py --apply

# 4) 复核：脚本再次 --dry-run 应显示 0 行待处理；抽查聊天/AI 生成与第三方接口可用

# 5) 确认无遗留后清空 .env 的 ENCRYPTION_KEY_LEGACY 并重启

# 6) 加密健康巡检（2026-09-19 新增，只读）：列出"任何密钥都解不开"的行 + 打印生效密钥指纹
docker exec -e PYTHONPATH=/app -w /app emergency-plan-backend \
  python /app/scripts/check_encryption_health.py
```

失败处理：脚本对解密失败的行**保持原值**并返回非 0 退出码，逐行列出；
通常是该行密文与所有已知密钥都不匹配（例如更早的密钥未填进 LEGACY），
此时把对应密钥补进 `ENCRYPTION_KEY_LEGACY` 后重跑即可；仍失败需在「AI 配置/第三方接口」页重新保存该 Key。

`check_encryption_health.py` 输出示例（本机实测）：

```
==> 生效 ENCRYPTION_KEY 指纹=f6d527e6，ENCRYPTION_KEY_LEGACY 把数=0
  ai_configs         511639fd-…  api_key_encrypted  undecryptable
==> 密文格式分布： gcm=9, undecryptable=1
!! 以下密文所有可用密钥都解不开（需人工重新保存）：
   - ai_configs 511639fd-… .api_key_encrypted  →  设置 → AI 配置（重新保存该条 API Key）
```

指纹（生效密钥 SHA-256 前 8 位）用于快速区分两类问题：**真的坏密文** vs **脚本跑在了密钥环境不对的机器上**
（例如在宿主机跑、而 `.env` 里的密钥与容器不同，会表现为"全表 undecryptable"）。

回滚：清空 `ENCRYPTION_KEY_LEGACY` 前，任何时刻把 `ENCRYPTION_KEY` 换回旧值即可恢复；
`--apply` 之后则必须保留新密钥（或同时保留新旧两把在 LEGACY 中）。

## 12. 常见问题

- 页面白屏/资源 404 → 检查 `VITE_BASE_PATH` 与网关 location 是否一致，dist 是否复制到正确子目录
- 登录后跳转 404 → 检查路由 basename（代码已支持，无需改）
- 上传/接口 502 → 检查网关 proxy_pass 的宿主机 IP 与 backend 端口
- **上传 >1MB 直接失败（无后端日志）** → 网关缺 `client_max_body_size`（默认 1MB），用
  `./scripts/check-gateway-config.sh <nginx 配置>` 确认
- **生成/对话没有流式效果、长任务 502/504** → 网关 `/api/` 缺 `proxy_buffering off` 与长超时，同上脚本检查
- **限流误伤（多人共用一个来源）、审计日志全是网关 IP** → 网关未透传 `X-Real-IP` / `X-Forwarded-For`
- 首次生成预案卡住 → 检查 chroma ONNX 模型缓存是否存在（见第 4 节）

## 13. 升级演练（不出门先彩排）

`scripts/rehearsal.sh`（2026-09-19 新增）用 `deploy/docker-compose.rehearsal.yml` 起一套
**独立 project（ep-rehearsal）** 的空库栈：端口 18000/15432、独立命名卷，与生产栈互不影响。

```bash
# 仓库根目录执行；需要 docker compose v2
./scripts/rehearsal.sh            # 完整彩排：构建镜像 → 空库跑全部迁移 → 健康检查 → 账本/关键表核对 → 清理
./scripts/rehearsal.sh --keep     # 保留现场（docker compose -p ep-rehearsal -f deploy/docker-compose.rehearsal.yml down -v 清理）
```

它专门覆盖历史上最容易翻车的三件事：

1. 升级包里的 backend 镜像能否**从零构建**；
2. **空库**能否跑完 50 个 `db_migration_*.sql`（`MIGRATE_FRESH=1`）并把账本写全
   （早期发生过"容器内 41 条 vs 仓库 46 条"的账本不一致）；
3. 关键表（users/enterprises/plan_projects/ai_configs/app_runtime_state）是否齐全、
   登录端点鉴权是否正常、空库加密健康是否通过。

建议流程：**先在能联网的机器跑 `./scripts/rehearsal.sh` 全绿，再在公司服务器执行 `upgrade.sh`**。

演练从 2026-09-19 起还包含**备份/回滚全链路**（DR）：

```text
写入 sys_config.rehearsal_canary → backup.sh（应产出非空 dump）→ 删除标记行（模拟数据损坏）
→ rollback.sh → 标记行恢复 + 后端健康 200          ← 全部在独立 project（ep-rehearsal）内完成
```

对应的脚本参数（生产可不用，演练/多环境部署时才用）：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DB_CONTAINER` | `emergency-plan-db` | `backup.sh` / `rollback.sh` 使用的 postgres 容器名 |
| `BACKEND_CONTAINER` | `emergency-plan-backend` | `rollback.sh` 停/起的后端容器名 |
| `BACKUP_DIR` | `backups` | 备份与回滚前快照的存放目录 |
| `ROLLBACK_CONFIRM` | 空（交互输入 ROLLBACK） | 设为 `ROLLBACK` 可非交互确认（CI/演练用，**生产建议保持交互**） |

> 回滚务必在**原部署目录**执行（文件资产按 `backend/uploads`、`backend/exports` 相对路径还原）。

演练还会核对**基线种子**（2026-09-19 起）——空库"能启动"不等于"能用"：

| 项目 | 期望（实测通过） | 来源 |
|---|---|---|
| roles / permissions / role_permissions | 3 / 20 / 41 | `db_migration_20260919_seed_roles_permissions.sql`（原 `app/seed_roles.sql` 从未被执行，已纳入迁移） |
| prompt_templates | 61 | `db_migration_20260919_prompt_templates_seed.sql`（由 `seed_prompts_full.json` 生成，仅插入缺失项） |
| ai_capabilities | 8 | `db_migration_20260917_ai_capability.sql` |
| work_ticket_templates | 15 | `db_migration_20260917_work_ticket_seed*.sql` |
| data_dicts / hazard_checklist_templates | 33 / 5 | `db_migration_data_dicts.sql`、`db_migration_hazard_management.sql` |
| 权限口径 | user 无 `menu:ai_config`；admin+super_admin 有 `menu:regulations` | W2 收口决策 + v1 P1-4 |

> 提示词模板的**刷新**（覆盖语义）仍走人工脚本 `python seed_prompts_full.py`；
> 迁移只负责"缺失即补"，不会覆盖页面上的人工编辑。
