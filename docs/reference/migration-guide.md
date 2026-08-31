# 数据库迁移指南

本文档定义本项目数据库迁移（`db_migration_*.sql`）的编写与维护规范，
与 `docs/deploy/README-DEPLOY.md`「升级」章节配套使用。

## 1. 迁移文件命名

- 命名格式：`db_migration_YYYYMMDD_desc.sql`；
- `YYYYMMDD` 为 8 位日期前缀，保证文件名按字典序可排序；同日多个迁移用不同
  `desc` 区分（必要时追加序号），如 `db_migration_20260831_third_party_config.sql`；
- `desc` 用简短英文小写下划线分词，概括迁移内容；脚本一旦提交并应用，
  禁止改名或删除。

## 2. 幂等要求

所有迁移语句必须幂等，可安全重复执行：

- 建表：`CREATE TABLE IF NOT EXISTS ...`；
- 加列：`ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...`；
- 删除：`DROP TABLE IF EXISTS ...` / `DROP COLUMN IF EXISTS ...` /
  `DROP INDEX IF EXISTS ...`；
- 插入数据：`INSERT ... ON CONFLICT (...) DO NOTHING`；
- 避免使用不带 `IF EXISTS` 的 `DROP` 及其他重复执行会报错的语句。

说明：迁移运行器通过 `schema_migrations` 保证每个脚本通常只执行一次，
但幂等仍是硬性要求——脚本可能被手动回放、随 db-init 恢复，或在 baseline
场景下与既有库共存，必须保证重复执行无副作用、无报错。

## 3. 双轨制约定：create_all 与迁移

- `create_all`（启动时 `Base.metadata.create_all`）只负责**全新空库**建表，
  即仅覆盖当前模型定义出的新表；
- 已有表的**新列 / 新表 / 新索引 / 权限 / 种子数据**一律走迁移 SQL；
- **模型新增字段必须同步编写对应幂等迁移**（如 `ADD COLUMN IF NOT EXISTS`），
  否则已有部署升级后模型与库结构不一致；
- 职责划分：新建表由 create_all 自动创建；已有结构的变更走迁移。两者互不替代。

## 4. 自动应用机制

backend 启动时迁移运行器自动处理（`backend/app/services/migration_runner.py`）：

- 启动时确保 `schema_migrations` 表存在，以 `script_name` 记录已应用脚本；
- 首次基线：空库且无任何记录时，默认将全部捆绑脚本记为 baseline
  （只记录不执行，适配由 db-init 建表的新库）；
- 增量应用：已有记录时，按文件名排序仅应用未记录脚本；每个脚本一个事务，
  语句与记录同事务提交，失败整体回滚且不记录；
- 串行化：固定 key 的 `pg_advisory_lock`，多实例并发启动不会重复执行；
- 逃生口：空库需执行全部捆绑迁移时，设置 backend 环境变量 `MIGRATE_FRESH=1`
  （compose 已从 `.env` 透传，见 `.env.example` 说明）；
- 迁移脚本目录：`backend/` 下全部 `db_migration_*.sql`。

## 5. 失败处理

- **fail-fast**：迁移失败 → 事务回滚不记录 → backend 进程以非 0 退出
  （容器重启循环、日志可见、数据安全），服务不会带病启动；
- **升级前强制备份**：升级脚本 `scripts/upgrade.sh` 在替换代码前强制执行
  `./scripts/backup.sh`，备份失败立即中止；
- **回滚方法**：
  - 数据库：使用 `backups/` 最新备份恢复（`pg_dump` 产物）；
  - 代码：解压旧版本包覆盖部署目录，重新执行部署步骤
    （见 `docs/deploy/README-DEPLOY.md` 第 4-6 节）。

## 6. 编写与验证步骤

1. 本地起库：启动本地 postgres（`docker compose ... up -d postgres`）；
2. 编写迁移 SQL：按第 1、2 节的命名与幂等要求编写；
3. 重启观察日志：重启 backend，确认迁移运行器执行新脚本并写入
   `schema_migrations`，启动日志无报错；
4. 抽样验证：用 psql 抽查表结构、列与数据，确认与迁移意图一致；
5. （可选）重复执行验证幂等：清空对应记录后重放脚本，确认无报错、无重复数据。
