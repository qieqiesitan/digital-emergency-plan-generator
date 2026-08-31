# 第三方接口统一配置与增量升级机制实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** ①企查查 KEY 报错根治并统一第三方 API Key 为管理员单点配置（LLM/QCC/高德/PROTEGO 全系统通用）；②建立「只更新系统不动数据」的增量升级机制（schema_migrations 自动迁移 + 安装包/升级包拆分 + upgrade.sh），并通过公司形态端到端演练。

**架构：** 新增独立 `third_party_config` 表存储加密第三方 key（DB 优先、环境变量兜底、启动 seed 导入），管理员页面统一配置；新增 `schema_migrations` 表与启动迁移运行器（pg_advisory_lock 串行、首次基线、新增自动应用、失败 fail-fast）；发布物拆安装包/升级包。

**技术栈：** FastAPI / SQLAlchemy async / PostgreSQL / React 19 / Vite / docker compose / bash。

**执行环境：** worktree `.worktrees/third-party-config-upgrade`（分支 `codex/third-party-config-upgrade`，基于 master bd10003）。前端命令在 `frontend/` 子目录执行。

**规格依据：** `docs/superpowers/specs/2026-08-31-third-party-config-and-upgrade-design.md`（commit 80fc1fc，含第二轮核查修正）。

**注意（并行工作区）**：主工作区有未提交的「紧急联系电话」修复（generation.py/plan_diagram_service/prompt_cache/risk_context_builder/seed_prompts_full.json/PlanEditorPage 等），与本计划改动文件**不重叠**；合并回 master 时主工作区未提交改动保持不动。打包 0.3.0 前需确认这些改动已提交或有意包含（全量包复制工作区）。

---

## 文件结构

### 后端新增

| 文件 | 职责 |
| --- | --- |
| `backend/app/models/third_party_config.py` | `ThirdPartyConfig` 模型（独立表） |
| `backend/app/models/schema_migration.py` | `SchemaMigration` 模型 |
| `backend/app/services/secret_utils.py` | 加密/解密/掩码工具（从 llm_client 收敛） |
| `backend/app/services/third_party_config.py` | 统一读取（DB→env）、写入、seed 导入 |
| `backend/app/services/migration_runner.py` | 启动迁移运行器（advisory lock + baseline + fail-fast） |
| `backend/app/routers/third_party_config.py` | 管理员 GET/PUT 接口 |

### 后端修改

| 文件 | 变更 |
| --- | --- |
| `backend/app/services/qcc_client.py` | key 改读统一配置 |
| `backend/app/routers/surrounding_ai.py` | 删除硬编码 AMAP_KEY，改读配置 |
| `backend/app/middleware/hmac_auth.py` | HMAC secret 改读配置（env 兜底） |
| `backend/app/config.py` | 新增 `AMAP_KEY` 字段（兜底）；保留 QCC/PROTEGO 字段 |
| `backend/app/main.py` | 启动接迁移运行器 + seed 导入 |
| `backend/app/services/llm_client.py` | 加密工具改用 `secret_utils`（行为不变） |
| `backend/app/models/system.py` | （可选）权限点注册入口不动，见任务 5 说明 |

### 前端

| 文件 | 变更 |
| --- | --- |
| `frontend/src/pages/Settings/ThirdPartyConfigPage.tsx` | 新增页面 |
| `frontend/src/routes/index.tsx` | 新增路由 |
| `frontend/src/layouts/MainLayout.tsx` | 设置菜单组新增入口 |
| `frontend/src/services/thirdPartyConfigService.ts` | API 封装 |

### 脚本/文档/配置

| 文件 | 变更 |
| --- | --- |
| `scripts/upgrade.sh` | 新增升级脚本 |
| `scripts/package-release.sh` | 支持 `--upgrade` 模式 |
| `.env.example` | 新增 `AMAP_KEY`（现值） |
| `deploy/docker-compose.prod.yml` | 透传 `AMAP_KEY` 等 env |
| `docs/deploy/README-DEPLOY.md` | 升级章节 + 迁移规范 |
| 包根 `VERSION` / `CHANGELOG.md` | 版本记录（打包时生成） |
| `backend/db_migration_20260831_third_party_config.sql` | 幂等建表迁移（双轨制规范示例） |

---

## 任务 1：后端模型与加密工具收敛

**文件：** 新增 `backend/app/models/third_party_config.py`、`backend/app/models/schema_migration.py`、`backend/app/services/secret_utils.py`；修改 `backend/app/services/llm_client.py`

- [ ] **步骤 1：写失败测试**——新建 `backend/tests/test_secret_utils.py`：

```python
import pytest
from app.services.secret_utils import encrypt_secret, decrypt_secret, mask_secret

def test_encrypt_decrypt_roundtrip():
    enc = encrypt_secret("Bearer abc-123")
    assert enc != "Bearer abc-123"
    assert decrypt_secret(enc) == "Bearer abc-123"

def test_mask_secret_keeps_head_tail():
    assert mask_secret("M6cf4mymxeKxHtSlXSXr7EfrA5IwHahRZXSNqVfqxtgv2slL") == "M6cf****slL"

def test_mask_short_secret():
    assert mask_secret("ab") == "****"
```

（先确认 `llm_client.py` 现有加密函数签名与密钥派生方式，`secret_utils` 复用同一 `ENCRYPTION_KEY` AES 方案，保证既有 ai_configs 密文仍可解密。）

- [ ] **步骤 2：跑测试确认失败**（`pytest tests/test_secret_utils.py -q`，模块不存在）
- [ ] **步骤 3：实现 secret_utils.py**——`encrypt_secret(plain)->hex`、`decrypt_secret(hex)->str`（与 llm_client 同款：`ENCRYPTION_KEY.encode()[:32].ljust(32)` 派生 AES）、`mask_secret(value)`（>8 字符保留前 4 尾 3，否则全 `****`）。
- [ ] **步骤 4：llm_client 改用 secret_utils**——`decrypt_api_key` 改为调用 `decrypt_secret`（保留别名兼容），新增导出 `encrypt_api_key = encrypt_secret`；跑既有 `pytest tests/ -q` 相关用例确认无回归。
- [ ] **步骤 5：建模型**——`ThirdPartyConfig`（`config_key` String(128) 唯一主键、`config_value` Text、`config_type` String(16) 默认 secret、`description` String(512) 可空、`updated_by` String(64) 可空、时间戳）；`SchemaMigration`（`script_name` String(255) 主键、`applied_at`）。
- [ ] **步骤 6：门禁 + Commit**

```bash
pytest tests/test_secret_utils.py -q && npx tsc -b
git add backend/app/services/secret_utils.py backend/app/models/third_party_config.py backend/app/models/schema_migration.py backend/app/services/llm_client.py backend/tests/test_secret_utils.py
git commit -m "feat(config): add secret utils and third-party config models"
```

## 任务 2：third_party_config 服务（读取/写入/导入）

**文件：** 新增 `backend/app/services/third_party_config.py`

- [ ] **步骤 1：写失败测试**——新建 `backend/tests/test_third_party_config.py`：读取优先级（DB 有值优先于 env）、env 兜底（monkeypatch `os.environ`）、空 env 不覆盖、掩码调用、`import_seed_configs` 空值跳过。
- [ ] **步骤 2：跑测试确认失败**
- [ ] **步骤 3：实现服务**：

```python
ENV_MAP = {
  "third_party.qcc.api_key": "QCC_API_KEY",
  "third_party.qcc.api_key_fallback": "QCC_API_KEY_FALLBACK",
  "third_party.qcc.endpoint": "QCC_ENDPOINT",
  "third_party.amap.api_key": "AMAP_KEY",
  "third_party.protego.hmac_secret": "EXTERNAL_API_HMAC_SECRET",
  "third_party.protego.callback_url": "PROTEGO_CALLBACK_URL",
}
KEY_TYPES = {...}  # secret/string

async def get_third_party_config(config_key: str) -> str | None:
    """DB → env（非空）→ None；secret 解密；内部独立短会话（async_sessionmaker）"""

async def set_third_party_config(config_key, value, updated_by, *, db=None) -> None:
    """upsert，secret 加密；记录 updated_by"""

async def import_seed_configs() -> None:
    """启动时：DB 缺失且 env 非空 → 写入；AMAP_KEY 缺失且 env 非空 → 写入"""
```

（使用独立短会话，避免低层 service 改动调用链；会话工厂从 `app.database` 取。）

- [ ] **步骤 4：门禁 + Commit** `feat(config): third-party config service with env fallback and seed import`

## 任务 3：接入点改造（QCC / 高德 / PROTEGO）

**文件：** 修改 `backend/app/services/qcc_client.py`、`backend/app/routers/surrounding_ai.py`、`backend/app/middleware/hmac_auth.py`、`backend/app/config.py`、`.env.example`、`deploy/docker-compose.prod.yml`

- [ ] **步骤 1：写失败测试**——`backend/tests/test_qcc_client.py`：`get_company_info` 在配置缺失时返回 `not_configured`（monkeypatch `get_third_party_config` 返回 None）；配置存在时发起请求并带 Authorization。`surrounding_ai` 的 geocode/poi 在无 key 时返回未配置错误（不抛异常）。
- [ ] **步骤 2：跑测试确认失败**
- [ ] **步骤 3：改实现**
  - `qcc_client.py`：`api_key = await get_third_party_config("third_party.qcc.api_key")`；None → `not_configured`；轮换逻辑保留（fallback 同理）；
  - `surrounding_ai.py`：删除 `AMAP_KEY = "7855..."` 字面量；各调用处 `key = await get_third_party_config("third_party.amap.api_key")`，空 → 返回「未配置高德 Key」错误；`config.py` 新增 `AMAP_KEY: str = ""`；
  - `hmac_auth.py`：`secret = await get_third_party_config("third_party.protego.hmac_secret") or settings.EXTERNAL_API_HMAC_SECRET`（确认中间件为 async 实现，否则按 `asyncio` 适配）；
  - `.env.example` 与生产 compose 增加 `AMAP_KEY=`（compose 传 `${AMAP_KEY:-}`；**本地 root compose 不加**，本地经 seed 从环境或页面配置——本地开发如需高德可临时设环境变量）；
  - **全仓扫描确认无残留**：`rg -n "78556e6e7d683bbda1b7d25e24cb412a|AMAP_KEY\s*=" backend` 仅剩 env/兜底定义。
- [ ] **步骤 4：门禁 + Commit** `feat(config): read QCC/AMap/PROTEGO keys from unified config`

## 任务 4：管理员接口 GET/PUT

**文件：** 新增 `backend/app/routers/third_party_config.py`；修改 `backend/app/main.py`（挂路由）

- [ ] **步骤 1：写失败测试**——`backend/tests/test_third_party_config_routes.py`：非管理员 403；GET 返回掩码（不含明文）；PUT 后 GET 掩码变化且 `get_third_party_config` 读到新值；PUT 空值校验 422。
- [ ] **步骤 2：跑测试确认失败**
- [ ] **步骤 3：实现路由**——`GET /api/v1/system/third-party-config`（`require_admin`）：返回 `[{key, label, configured, masked_value, type, description}]`；`PUT`：接受 `[{key, value}]`，secret 加密写入、记录 `updated_by`；**日志不打印 value**。
- [ ] **步骤 4：权限点注册**——检索 `menu:system_config` 的注册机制（角色权限表/菜单权限 seed），以同机制注册 `menu:third_party_config` 并授予管理员角色（写幂等迁移 `db_migration_20260831_third_party_config.sql`：建表 `third_party_config` + 权限点 + 授权，全部 `IF NOT EXISTS`/幂等）。
- [ ] **步骤 5：main.py 挂载路由 + 门禁 + Commit** `feat(config): admin third-party config API with masked responses`

## 任务 5：前端页面与入口

**文件：** 新增 `frontend/src/pages/Settings/ThirdPartyConfigPage.tsx`、`frontend/src/services/thirdPartyConfigService.ts`；修改 `frontend/src/routes/index.tsx`、`frontend/src/layouts/MainLayout.tsx`

- [ ] **步骤 1：写失败测试**——`frontend/src/services/thirdPartyConfigService.test.ts`：getConfig/updateConfig 请求路径与参数正确。
- [ ] **步骤 2：跑测试确认失败**
- [ ] **步骤 3：实现 service + 页面**——页面表单：企查查主/备用 key + endpoint、高德 key、PROTEGO HMAC secret + 回调 URL；已配置值显示掩码；保存调 PUT；成功后 message.success。
- [ ] **步骤 4：路由与菜单**——`routes/index.tsx` 懒加载 `/settings/third-party-config`；`MainLayout.tsx` 设置组新增菜单项 `hasMenu("menu:third_party_config")`，图标与「AI 配置」同款区段。
- [ ] **步骤 5：门禁 + Commit** `feat(config): admin third-party config page`

## 任务 6：启动接线与 seed 导入

**文件：** 修改 `backend/app/main.py`

- [ ] **步骤 1：改实现**——启动流程：`create_all` → `run_migrations()` → `import_seed_configs()`；迁移失败 `logging.critical` + `sys.exit(1)`。
- [ ] **步骤 2：本地启动冒烟**——`uvicorn app.main:app`（或容器）启动成功、日志含「migrations baseline」「third-party seed imported」、`/api/health` 200。
- [ ] **步骤 3：Commit** `feat(config): wire migration runner and seed import into startup`

## 任务 7：迁移运行器

**文件：** 新增 `backend/app/services/migration_runner.py`；修改 `backend/app/main.py`

- [ ] **步骤 1：写失败测试**——`backend/tests/test_migration_runner.py`（纯逻辑）：脚本排序、首次 baseline 不执行、新增脚本执行并记录、已记录跳过、advisory lock 获取失败不执行。
- [ ] **步骤 2：跑测试确认失败**
- [ ] **步骤 3：实现运行器**

```python
async def run_migrations() -> None:
    """1) SELECT pg_advisory_lock(<固定key>)；2) 确保 schema_migrations 存在；
    3) 无记录→全量 baseline（MIGRATE_FRESH=1 则全部执行）；
    4) 有记录→按文件名排序应用未记录脚本，每脚本一个事务，成功插入记录；
    5) 异常→回滚→释放锁→raise（main.py 捕获后 sys.exit(1)）"""
```

- [ ] **步骤 4：门禁 + Commit** `feat(migrate): startup migration runner with advisory lock and baseline`

## 任务 8：升级工具（upgrade.sh + --upgrade 打包）

**文件：** 新增 `scripts/upgrade.sh`；修改 `scripts/package-release.sh`、`docs/deploy/README-DEPLOY.md`

- [ ] **步骤 1：package-release.sh 增加 --upgrade 模式**——组装升级包：backend（git 跟踪）+ frontend/dist + deploy + docs + scripts + `.env.example` + `backend/db_migration_*.sql`（全量，运行器基线处理）+ `VERSION` + `CHANGELOG.md`；**排除 db-init/model-cache/uploads/exports**。
- [ ] **步骤 2：新增 scripts/upgrade.sh**

```bash
用法: ./scripts/upgrade.sh <版本号> [网关静态目录]
1) 校验 VERSION；2) ./scripts/backup.sh 强制备份；
3) 替换 backend 代码（保留 .env/数据卷/uploads/exports/model-cache/backups）；
4) [网关静态目录] cp -r frontend/dist/* 到网关目录（缺省则提示人工执行）；
5) docker compose -f deploy/docker-compose.prod.yml --project-directory . up -d --build；
6) ./scripts/deploy-check.sh <站点> <API>；失败提示用 backups 回滚。
```

- [ ] **步骤 3：README-DEPLOY.md 新增「升级」章节**——安装包 vs 升级包、upgrade.sh 用法、迁移自动应用与失败处理、迁移编写规范（U-3 双轨制约定）。
- [ ] **步骤 4：bash -n + Commit** `feat(deploy): upgrade package mode and upgrade script`

## 任务 9：迁移规范与文档收尾

**文件：** `docs/deploy/README-DEPLOY.md`、`docs/reference/migration-guide.md`（新增）

- [ ] **步骤 1：写迁移指南**——命名、幂等要求、双轨制约定（新列必须迁移 SQL）、失败处理、验证方法。
- [ ] **步骤 2：README 交叉引用 + Commit** `docs(deploy): migration guide and upgrade notes`

## 任务 10：全量门禁

**文件：** 无

- [ ] **步骤 1：后端**——`cd backend && pytest tests/ -q` 全绿（基线 1082+ 新增）。
- [ ] **步骤 2：前端**——`npx tsc -b` 0；`npx vitest run` 全绿；`npx eslint` 改动文件零新增。
- [ ] **步骤 3：脚本**——`bash -n scripts/upgrade.sh scripts/package-release.sh scripts/deploy-check.sh`；`docker compose -f deploy/docker-compose.prod.yml --project-directory . --env-file .env.example config -q`。
- [ ] **步骤 4：硬编码 key 扫描**——`rg -n "78556e6e7d683bbda1b7d25e24cb412a" backend frontend` 零命中（`.env.example` 中 AMAP_KEY 为现值属预期）。
- [ ] **步骤 5：Commit（如有修正）**

## 任务 11：公司形态端到端演练（U-6 验收门槛）

**文件：** 无（验证）

- [ ] **步骤 1：恢复库基线**——全新 postgres 卷 + `db-init/01_restore.sql` 恢复 → 启动 → `schema_migrations` 建表且含全部基线、无错误日志、数据完好（抽样查询 enterprises 计数）。
- [ ] **步骤 2：新增迁移自动应用**——放置测试迁移 `db_migration_20260831_test_only.sql`（建无害表）→ 重启 → 断言仅应用该脚本、表存在。
- [ ] **步骤 3：失败迁移阻断**——放置失败迁移（非法 SQL）→ 重启 → 断言服务不启动、日志含脚本名与错误 → 移除后恢复。
- [ ] **步骤 4：并发验证**——`--workers 4` 启动 → schema_migrations 无重复记录、无 DDL 冲突日志。
- [ ] **步骤 5：升级包演练**——在「0.2.0 数据卷」副本上按 upgrade.sh 升级 → 数据完好（企业/预案计数一致）、迁移自动应用、deploy-check 全绿。
- [ ] **步骤 6：第三方配置功能验证**——管理员页面配置 QCC key → 新建企业自动填充调用真实/桩 QCC 成功；AMap 周边搜索可用。
- [ ] **步骤 7：记录结果到 TASKS.md**

## 任务 12：收尾与交付

**文件：** 无

- [ ] **步骤 1：最终审查**——对照规格逐项核验（T-1~T-6、U-1~U-6），门禁复跑。
- [ ] **步骤 2：按 finishing-a-development-branch 收尾**——用户选合并方式。
- [ ] **步骤 3：出包**——0.3.0 安装包（全量）+ 升级包（--upgrade），放 `C:\Users\55061\Desktop\shuzihuayuan0820\`；包内含 VERSION/CHANGELOG/升级说明；提醒公司升级用 upgrade.sh、全新部署用安装包。

---

## 自检记录（执行前已做）

1. **规格覆盖度**：T-1~T-6 → 任务 1-5 + 任务 4 步骤 4；U-1~U-6 → 任务 1（模型）+ 任务 7-11；#1 立即修复 → 交付说明（不改代码）；第二轮核查修正（独立表/无内置默认/并发锁/隔离/解密容错）→ 任务 1-4 对应落实。
2. **占位符扫描**：无 TODO/待定；所有脚本与关键代码有明确内容。
3. **类型/契约一致性**：`get_third_party_config(config_key)` 签名在任务 2 定义、任务 3/4/6 引用一致；`run_migrations()` 任务 7 定义、任务 6 接线；`ThirdPartyConfig`/`SchemaMigration` 模型任务 1 定义、任务 4 迁移 SQL 与任务 7 运行器一致。
