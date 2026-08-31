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

- `create_all`（启动时 `Base.metadata.create_all`）负责建表：每次启动都会
  幂等执行，**新表**无论全新库还是已有部署都会自动创建（含补建缺失表）；
- **已有表**的**新列 / 新索引 / 权限 / 种子数据**等结构变更走迁移 SQL
  （`create_all` 不会修改已有表）；
- **模型新增字段必须同步编写对应幂等迁移**（如 `ADD COLUMN IF NOT EXISTS`），
  否则已有部署升级后模型与库结构不一致；
- 职责划分：新表由 create_all 自动创建；已有表的结构变更走迁移 SQL。两者互不替代。

## 4. 自动应用机制

backend 启动时迁移运行器自动处理（`backend/app/services/migration_runner.py`）：

- 启动时确保 `schema_migrations` 表存在，以 `script_name` 记录已应用脚本；
- 首次基线：`schema_migrations` 无任何记录时（无论库中是否有业务数据），
  默认将全部捆绑脚本记为 baseline（只记录不执行，适配由 db-init 建表的新库）；
- 增量应用：已有记录时，按文件名排序仅应用未记录脚本；每个脚本一个事务，
  语句与记录同事务提交，失败整体回滚且不记录；
- 串行化：固定 key 的 `pg_advisory_lock`，多实例并发启动不会重复执行；
- 逃生口：空库需执行全部捆绑迁移时，设置 backend 环境变量 `MIGRATE_FRESH=1`
  （compose 已从 `.env` 透传，见 `.env.example` 说明）；
- 注意：若 baseline 已记录但对应表缺失（例如 db-init 未挂载/未执行），
  启动后会是空 schema——需确认 db-init 已应用，或改用 `MIGRATE_FRESH=1`
  重新执行全部捆绑迁移（先清空 `schema_migrations` 记录，见第 6 节）；
- 迁移脚本目录：`backend/` 下全部 `db_migration_*.sql`。

## 5. 失败处理

- **fail-fast**：迁移失败 → 事务回滚不记录 → backend 进程以非 0 退出
  （容器重启循环、日志可见、数据安全），服务不会带病启动；
- **升级前强制备份**：升级脚本 `scripts/upgrade.sh` 在替换代码前强制执行
  `./scripts/backup.sh`，备份失败立即中止；
- **回滚方法**：
  - 数据库：使用 `backups/` 最新备份恢复（`backup.sh` 产出 `-Fc` 格式），
    按顺序执行：停 backend → 恢复数据库 → 回退旧代码 → 重启：

    ```bash
    docker stop emergency-plan-backend
    docker exec -i emergency-plan-db pg_restore -U postgres -d emergency_plan \
      --clean --if-exists < backups/emergency_plan_<stamp>.dump
    # 回退旧代码：解压旧版本包覆盖部署目录，重新执行部署步骤
    docker compose -f deploy/docker-compose.prod.yml --project-directory . up -d
    ```

    注：upgrade.sh 的备份发生在代码替换之前，因此「最新备份」即失败升级
    前的数据库状态，可直接用于回滚；
  - 代码：解压旧版本包覆盖部署目录，重新执行部署步骤
    （见 `docs/deploy/README-DEPLOY.md` 第 4-6 节）。

## 6. 编写与验证步骤

1. 本地起库：启动本地 postgres：

   ```bash
   docker compose -f deploy/docker-compose.prod.yml --project-directory . up -d postgres
   ```

2. 编写迁移 SQL：按第 1、2 节的命名与幂等要求编写；
3. 重启观察日志：重启 backend，确认迁移运行器执行新脚本并写入
   `schema_migrations`，启动日志无报错；
4. 抽样验证：用 psql 抽查表结构、列与数据，确认与迁移意图一致；
5. （可选）重复执行验证幂等：清空对应记录后重放脚本，确认无报错、无重复数据：

   ```bash
   docker exec emergency-plan-db psql -U postgres -d emergency_plan \
     -c "SELECT * FROM schema_migrations;"
   docker exec emergency-plan-db psql -U postgres -d emergency_plan \
     -c "DELETE FROM schema_migrations WHERE script_name='db_migration_20260831_xxx.sql';"
   ```

## 7. 编写约定

- 迁移脚本不要自带顶层 `BEGIN;` / `COMMIT;`：运行器会剥离顶层事务语句，
  统一按「每个脚本一个事务」包裹执行（见 `backend/app/services/migration_runner.py`）；
- 同日多个脚本按文件名排序执行（`YYYYMMDD` 前缀相同），依赖顺序靠
  `desc`/序号控制，如 `db_migration_20260831_01_...sql`、`db_migration_20260831_02_...sql`。
