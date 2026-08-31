# 第三方接口统一配置与增量升级机制设计

日期：2026-08-31
状态：用户已确认设计方向（新增「第三方接口配置」页与 AI 配置同设置区；高德沿用现有 key 先挪入配置；迁移启动时自动应用并须在公司服务器可完美运行）
范围：①企查查 KEY 缺失问题根治 ②第三方 API Key 统一管理员配置 ③增量升级与自动迁移机制

## 一、背景与目标

公司服务器已部署 0.2.0 全量包。部署后出现：新建企业 AI 自动填充报「未配置企查查KEY」。同时用户要求：

1. 所有第三方 API Key 统一为「管理员配置一个即全系统通用」，无需每个用户自己配置；
2. 后续升级只更新系统、不覆盖公司服务器数据；数据结构变化与迁移单独处理，不做全量更换。

## 二、非目标

- 不重写 git 历史（QCC/AMap 旧明文 key 的历史提交保留，仅从当前代码/模板移除）。
- 不改 LLM 用户级配置流程（现状已是系统级 `ai_configs.is_system`，管理员 AI 配置页可配，达标）。
- 不做多云/多环境密钥轮换平台，仅满足「管理员单点配置、全系统通用」。

## 三、现状与根因（企查查 KEY）

**根因**：企查查 key 只从环境变量读取（`backend/app/services/qcc_client.py:19` 读 `settings.QCC_API_KEY`），不走数据库；生产 `.env.example` 与 `deploy/docker-compose.prod.yml` 的 QCC 默认均为空；本地开发能用是因为根 `docker-compose.yml` 硬编码了两个 Bearer key。公司服务器 key 为空 → `get_company_info` 返回 `not_configured` → `enterprises.py:30` 映射为「未配置企查查 API Key，请联系管理员」。

**立即修复（不等本次开发）**：公司 `.env` 填入两个 QCC Bearer key（值取自本地 `docker-compose.yml:32-34`），`docker compose -f deploy/docker-compose.prod.yml --project-directory . up -d backend` 重启后自动填充恢复。

**第三方 Key 现状盘点**：

| 第三方 | 现状 | 问题 |
| --- | --- | --- |
| LLM（DeepSeek 等） | DB `ai_configs` 系统级（is_system，管理员 AI 配置页） | ✅ 已达标 |
| 企查查 QCC | 仅环境变量 | ❌ 本次报错根因 |
| 高德 AMap | `surrounding_ai.py:24` 源码硬编码明文 key | ❌ 不可配置、key 进仓库 |
| PROTEGO 外部接入 | `config.py:12-13` 环境变量（HMAC secret / 回调 URL），`hmac_auth.py` 保护 `/api/external/*` | ⚠ 也属第三方配置，需一并纳入 |

## 三之二、补充核查结论（2026-08-31 第二轮）

1. LLM 配置**无用户级残留**：`risk_ai_service._get_ai_config(user_id, db)` 实现只取系统级（`is_system`），`user_id` 仅为兼容参数；
2. 前端**无高德 JS key**：GIS 底图用高德公开瓦片 URL（`GisMapPicker.tsx:67`），仅后端 Web 服务 key 需管理；
3. 现有「系统配置」页（`SystemConfigPage.tsx`）是**通用 sys_config key-value 编辑器**，可增删改任意 `config_key`——第三方 secret 若复用 sys_config 会被该页明文暴露/删除，**必须独立表隔离**；
4. 生产 `uvicorn --workers 4`：4 个 worker 进程同时启动会**并发执行迁移运行器**，必须用数据库锁（`pg_advisory_lock`）保证只执行一次；
5. 「内置默认沿用高德现值」与「源码不留 key」矛盾：key 值应经 seed 导入数据库，**源码不保留字面量**，未配置时返回未配置提示。

## 四、第三方接口统一配置（任务 T-1 起）

### T-1 配置存储：独立 third_party_config 表

**不复用 sys_config**：现有「系统配置」页是通用 key-value 编辑器，secret 放进去会被明文暴露、可被删除。新建独立表 `third_party_config`：

| 列 | 说明 |
| --- | --- |
| `config_key` | 唯一键（见下） |
| `config_value` | secret 类为加密值，string 类为明文 |
| `config_type` | `secret` / `string` |
| `description` | 说明 |
| `updated_by` | 最后修改人（审计） |
| `created_at` / `updated_at` | 时间戳 |

约定 key 命名（`config_key`）：

| config_key | 类型 | 说明 |
| --- | --- | --- |
| `third_party.qcc.api_key` | secret | 企查查主 key（原 `QCC_API_KEY`） |
| `third_party.qcc.api_key_fallback` | secret | 企查查备用 key |
| `third_party.qcc.endpoint` | string | 企查查 endpoint（默认现有值） |
| `third_party.amap.api_key` | secret | 高德 Web 服务 key（**seed 导入现值，源码不留字面量**） |
| `third_party.protego.hmac_secret` | secret | PROTEGO 外部接入 HMAC secret（原 `EXTERNAL_API_HMAC_SECRET`） |
| `third_party.protego.callback_url` | string | PROTEGO 回调地址（原 `PROTEGO_CALLBACK_URL`） |

secret 类型的值用 `ENCRYPTION_KEY` 加密后存储（复用 `llm_client.decrypt_api_key` 同款 AES 方案），接口不回显明文（返回掩码，如 `M6cf****slL`）。

**解密失败容错**：若 `ENCRYPTION_KEY` 与写入时不一致导致解密失败，接口返回「已配置但无法解密，请重新配置」，不静默视为未配置、也不抛 500。

### T-2 读取优先级：DB → 环境变量 → 无内置敏感默认

新增统一读取函数（如 `backend/app/services/third_party_config.py::get_third_party_config(key)`）：

1. 查 `third_party_config` 对应 `config_key`（secret 解密）；
2. 未命中且存在同名环境变量（`QCC_API_KEY`、`QCC_API_KEY_FALLBACK`、`QCC_ENDPOINT`、`AMAP_KEY`、`EXTERNAL_API_HMAC_SECRET`、`PROTEGO_CALLBACK_URL`）且**非空** → 用环境变量；
3. 仍未命中 → 未配置（返回空/未配置标记），**不内置敏感默认**——AMap 也不例外，源码不保留 key 字面量。

启动 seed 时执行**导入**（在迁移运行器之后、应用就绪前）：若 `third_party_config` 无该 key 且来源值存在（环境变量非空，或 AMap 旧硬编码值），则写入；**空值一律跳过**（避免「已配置但为空」的假象）。公司现有部署升级后无需手动填。

**读取不做进程内缓存**（或最多 5s TTL）：每次调用直接查库，管理员改 key 后即时生效；查询开销可忽略（低频接口）。

### T-3 后端接入点改造

- `qcc_client.py`：`get_company_info` 改为经 `get_third_party_config` 获取 key（保留 env 兜底），删除对 `settings.QCC_API_KEY` 的直读；读取函数内部用独立短会话或由调用方传入 `AsyncSession`（实现时确定，避免长会话泄漏）；
- `surrounding_ai.py`：删除硬编码 `AMAP_KEY` 字面量，改经 `get_third_party_config` 读取（env 兜底为 `AMAP_KEY`，空则返回未配置提示）；
- `middleware/hmac_auth.py`：`EXTERNAL_API_HMAC_SECRET` 改经 `get_third_party_config` 读取（env 兜底）；PROTEGO 回调 URL 同理；
- `config.py`：保留 QCC 环境变量定义（兜底用），不再作为唯一来源。

### T-4 管理员 API 与前端页面

- 新增 `GET/PUT /api/v1/system/third-party-config`（`require_admin`）：GET 返回各 key 的掩码与是否已配置；PUT 接收明文并加密写入 `third_party_config`，记录 `updated_by`；
- 新增前端页 `frontend/src/pages/Settings/ThirdPartyConfigPage.tsx`（路由 `/settings/third-party-config`）；
- 入口：`MainLayout` 设置菜单组内新增「第三方接口配置」，与「AI 配置」「系统配置」同区（`MainLayout.tsx:81-97` 同款菜单项）；
- 需注册菜单权限点（`menu:third_party_config`，管理员角色可见，与 `menu:system_config` 同机制），无权限不显示入口；
- 页面展示 QCC 主/备用 key、endpoint、高德 key、PROTEGO HMAC secret/回调 URL；已配置值显示掩码，保存后即时生效。

### T-5 与现有「系统配置」页的隔离

现有 `SystemConfigPage` 通用 key-value 编辑（`backend/app/routers/config.py` 覆盖任意 `config_key`）**天然不涉及 `third_party.*`**（独立表）；在其页面/接口文档提示：第三方接口请到「第三方接口配置」页维护，避免管理员误以为可在通用页配置。

### T-6 测试

- 单测：读取优先级（DB→env→默认）、secret 加密存取往返、掩码不回显明文、PUT 需管理员；
- 接口冒烟：管理员 GET/PUT 第三方配置 → qcc_client/amap 读取到新值。

## 五、增量升级与自动迁移（任务 U-1 起）

### U-1 schema_migrations 表

新增模型 `SchemaMigration`：`script_name`（PK，如 `db_migration_xxx.sql`）、`applied_at`。启动 `create_all` 后自动创建。

### U-2 启动迁移运行器

`backend/app/services/migration_runner.py`，在 `main.py` 的 `create_all` 之后、应用启动前执行：

1. 扫描 `backend/db_migration_*.sql`，按文件名排序；
2. **首次启动（无 schema_migrations 记录）**：把所有捆绑脚本记为 baseline 写入表，**不执行**——恢复库/既有库的 schema 已包含这些历史迁移；
3. 后续启动：按文件名排序，逐个应用「尚未记录在 schema_migrations 中」的脚本（即首次启动后新增的迁移文件；每个脚本一个事务，成功则记录；失败回滚并**阻止服务启动**，日志给出脚本名与错误，避免半迁移状态）；
4. **并发保护**：整个「检查 + 应用」过程用 `pg_advisory_lock`（固定 key）包裹；生产 `uvicorn --workers 4` 下 4 个 worker 同时启动时仅一个能执行迁移，其余等待锁释放后读取结果跳过，避免并发 DDL 冲突；
5. **失败行为**：迁移失败 → 回滚 → 记录日志 → 进程以非 0 退出码退出（容器 restart 循环，日志可见、数据安全）；升级前强制备份（U-5）；
6. 提供逃生口：环境变量 `MIGRATE_FRESH=1` 时对空库真正执行全部脚本（替代 db-init 的全新空库场景）。

### U-3 迁移编写规范（写入手册）

- 新迁移统一命名 `db_migration_YYYYMMDD_desc.sql`（可排序）；
- 必须幂等：`CREATE TABLE IF NOT EXISTS`、`ADD COLUMN IF NOT EXISTS`、`DROP ... IF EXISTS` 等；
- 不破坏数据：禁止裸 DROP TABLE / 无保护改列；涉及数据改写须可回滚或先备份；
- **双轨制约定**：`create_all` 只负责全新空库建表；**已有表的新列/新表一律走迁移 SQL**（模型新增字段必须同步写幂等迁移），不允许依赖 create_all 改既有表。

### U-4 发布物拆分

- **安装包**：全新部署用（现状全量包：代码 + dist + db-init/01_restore.sql + 模型缓存 + 配置）；
- **升级包**：只含代码 + 前端 dist + `deploy/` 配置 + 新增 `db_migration_*.sql` + 手册；**不含 db-init 与模型缓存**（模型有变更时单独附带）；
- 包根 `VERSION` 文件（如 `0.3.0`）+ `CHANGELOG.md`（列出本版本新增迁移与配置变更）；
- `package-release.sh` 增加 `--upgrade` 模式生成升级包（复用现有组装逻辑，排除 db-init/model-cache）。

### U-5 upgrade.sh 升级脚本

1. 校验当前目录与 VERSION；
2. `./scripts/backup.sh` 备份数据库（`backups/`，upgrade 前强制）；
3. 替换 backend 代码；前端 dist 更新到**网关静态目录**（`upgrade.sh` 增加 `<网关静态目录>` 参数或交互式确认，路径由运维提供）；
4. `docker compose -f deploy/docker-compose.prod.yml --project-directory . up -d --build`（迁移在启动时自动应用）；
5. `./scripts/deploy-check.sh` 验证；失败提示用备份回滚。

### U-6 公司服务器可运行性验证（本规格的验收门槛）

用与公司一致的方式做端到端演练（本地 Docker）：

1. 全新 postgres 卷 + `db-init/01_restore.sql` 恢复 → 启动 → 断言 `schema_migrations` 已建且含全部基线脚本、服务正常、数据完好；
2. 追加一个测试迁移 SQL（如新建一张无害表）→ 重启 → 断言自动应用成功且仅应用新增脚本；
3. 构造一个失败迁移 → 重启 → 断言服务**不启动**并输出明确错误，回滚后恢复正常；
4. **并发验证**：以 `--workers 4` 启动，断言迁移只执行一次（schema_migrations 无重复记录、无 DDL 冲突日志）；
5. 全量门禁：pytest 全绿、tsc 0、vitest 全绿、deploy-check 全绿；
6. 出 0.3.0 安装包 + 升级包，升级包按 U-5 在「已有 0.2.0 数据卷」的本地副本上演练：升级后数据完好、迁移自动应用、功能可用。

## 六、风险与对策

| 风险 | 对策 |
| --- | --- |
| 迁移自动应用导致线上故障 | fail-fast 启动阻断 + 升级前强制 backup.sh + 幂等规范 + U-6 演练门槛 |
| 多 worker 并发执行迁移 | `pg_advisory_lock` 串行化 + U-6 并发验证 |
| ENCRYPTION_KEY 变更导致 secret 解不开 | 沿用 ai_configs 既有约束（README 已注明不可改），本设计不引入新密钥体系 |
| 恢复库首次启动 baseline 误判 | baseline 语义=「捆绑脚本视为已应用」仅针对恢复/既有库；空库走 MIGRATE_FRESH=1 |
| QCC/AMap key 明文残留 | 从当前代码/模板/打包产物移除；历史提交不重写（非目标） |
| 通用「系统配置」页暴露/误删第三方 secret | 独立 third_party_config 表 + T-5 隔离提示 |
| 密文解密失败被误判为未配置 | T-1 解密失败容错（提示重新配置） |

## 七、变更文件清单（草案）

### 后端

| 文件 | 变更 |
| --- | --- |
| `backend/app/models/system.py` | 新增 `SchemaMigration` 模型（或独立文件） |
| `backend/app/models/third_party_config.py` | 新增独立配置表模型 |
| `backend/app/services/migration_runner.py` | 新增迁移运行器（pg_advisory_lock 串行化） |
| `backend/app/services/third_party_config.py` | 新增统一读取/写入/加密 |
| `backend/app/services/qcc_client.py` | 改读统一配置（env 兜底） |
| `backend/app/routers/surrounding_ai.py` | 删除硬编码 AMAP_KEY，改读配置 |
| `backend/app/middleware/hmac_auth.py` | HMAC secret 改读统一配置（env 兜底） |
| `backend/app/routers/config.py` | 新增 third-party-config GET/PUT（require_admin） |
| `backend/app/main.py` | 启动挂迁移运行器 + seed 导入 |
| `backend/app/config.py` | 保留 env 字段（兜底） |

### 前端

| 文件 | 变更 |
| --- | --- |
| `frontend/src/pages/Settings/ThirdPartyConfigPage.tsx` | 新增页面 |
| `frontend/src/routes/index.tsx` | 新增路由 `/settings/third-party-config` |
| `frontend/src/layouts/MainLayout.tsx` | 设置菜单组新增入口 |
| `frontend/src/services/thirdPartyConfigService.ts` | 新增 API 封装 |

### 脚本与文档

| 文件 | 变更 |
| --- | --- |
| `scripts/upgrade.sh` | 新增升级脚本 |
| `scripts/package-release.sh` | 支持 `--upgrade` 模式 |
| `docs/deploy/README-DEPLOY.md` | 升级章节 + 迁移编写规范 |
| 包内 `VERSION` / `CHANGELOG.md` | 版本与变更记录 |

## 八、落地顺序

1. 阶段一：T-1~T-5 第三方接口统一配置（含企查查根治）；
2. 阶段二：U-1~U-5 迁移运行器 + 升级包/upgrade.sh；
3. 阶段三：U-6 公司形态端到端演练 + 全量门禁；
4. 交付：0.3.0 安装包与升级包（含本次规格的全部改动）。
