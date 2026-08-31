"""启动迁移运行器：advisory lock 串行化 + schema_migrations 版本跟踪 + baseline 语义。

流程（与计划任务 7 一致）：
1) 同一连接上先 SELECT pg_advisory_lock(<固定整数 key>)，获取失败直接抛出（不执行任何脚本）；
2) 在锁内执行 Base.metadata.create_all（幂等，补建缺失表，避免并发启动竞态）；
3) 确保 schema_migrations 表存在（CREATE TABLE IF NOT EXISTS）；
4) 读取已记录 script_name 集合；
5) 无任何记录且 MIGRATE_FRESH != 1 → 全部捆绑脚本写为 baseline（只记录不执行）；
   MIGRATE_FRESH = 1 → 全部执行后记录；
6) 已有记录 → 按文件名排序仅应用未记录脚本：每个脚本一个事务，成功才插入记录，
   失败时日志含 script_name 并包装异常上抛（main.py 捕获后 sys.exit(1) fail-fast）；
7) finally 释放 advisory lock。

脚本目录 = backend/（相对 worktree backend 目录），匹配 db_migration_*.sql。
历史脚本允许自带 BEGIN;/COMMIT; 包裹（如 db_migration_accident_types_2025.sql），
执行时剥离顶层 BEGIN/COMMIT，统一由本运行器按「每个脚本一个事务」包裹，
保证脚本与其记录要么一起提交、要么一起回滚。
"""

import logging
import os
import re
from pathlib import Path

from sqlalchemy import text

from app.database import Base, engine

logger = logging.getLogger(__name__)

# 固定整数 advisory lock key（"MIGR" 的 ASCII 十六进制，落在 int4 范围内）。
MIGRATION_LOCK_KEY = 0x4D494752
MIGRATE_FRESH_ENV = "MIGRATE_FRESH"
SCRIPT_GLOB = "db_migration_*.sql"


def migration_script_dir() -> Path:
    """返回 backend/ 目录（迁移脚本所在目录）。"""
    return Path(__file__).resolve().parents[2]


def list_migration_scripts() -> list[Path]:
    """按文件名排序返回捆绑的 db_migration_*.sql 脚本。"""
    return sorted(migration_script_dir().glob(SCRIPT_GLOB))


def _split_sql_statements(sql: str) -> list[str]:
    """按顶层分号拆分 SQL 语句。

    兼容 `--` 行注释、`/* */` 块注释、单引号字符串（含 '' 转义）以及
    `$tag$...$tag$` 美元引用（DO 块 / CREATE FUNCTION 正文内的分号不参与拆分）。
    """
    statements: list[str] = []
    current: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""
        if ch == "'":
            # 单引号字符串（'' 转义）
            current.append(ch)
            i += 1
            while i < n:
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        current.append("''")
                        i += 2
                        continue
                    current.append("'")
                    i += 1
                    break
                current.append(sql[i])
                i += 1
            continue
        if ch == "$":
            # 美元引用：$$ 或 $tag$
            match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", sql[i:])
            if match is not None:
                tag = match.group(0)
                end = sql.find(tag, i + len(tag))
                if end == -1:
                    current.append(sql[i:])
                    i = n
                    continue
                end += len(tag)
                current.append(sql[i:end])
                i = end
                continue
            current.append(ch)
            i += 1
            continue
        if ch == "-" and nxt == "-":
            # 行注释：跳到行尾
            end = sql.find("\n", i)
            i = n if end == -1 else end
            continue
        if ch == "/" and nxt == "*":
            # 块注释；未闭合直接抛错，拒绝静默截断剩余 SQL。
            end = sql.find("*/", i + 2)
            if end == -1:
                raise ValueError("SQL 块注释未闭合（缺少 */）")
            i = end + 2
            continue
        if ch == ";":
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def _is_transaction_wrapper(stmt: str) -> bool:
    """顶层 BEGIN;/COMMIT; 由运行器统一管理事务，剥离不执行。"""
    return stmt.lower() in ("begin", "commit")


async def _ensure_schema_migrations(conn) -> None:
    await conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " script_name VARCHAR(255) PRIMARY KEY,"
            " applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
    )


async def _load_applied_scripts(conn) -> set[str]:
    result = await conn.execute(text("SELECT script_name FROM schema_migrations"))
    return set(result.scalars().all())


async def _record_script(conn, script_name: str) -> None:
    await conn.execute(
        text("INSERT INTO schema_migrations (script_name) VALUES (:script_name)"),
        {"script_name": script_name},
    )


async def _apply_script(conn, script: Path) -> None:
    sql = script.read_text(encoding="utf-8")
    for statement in _split_sql_statements(sql):
        if _is_transaction_wrapper(statement):
            continue
        await conn.execute(text(statement))


async def run_migrations() -> None:
    """应用未记录的 db_migration_*.sql 脚本，成功/失败都在 finally 释放 advisory lock。"""
    conn = await engine.connect()
    lock_acquired = False
    try:
        await conn.execute(
            text("SELECT pg_advisory_lock(:lock_key)"),
            {"lock_key": MIGRATION_LOCK_KEY},
        )
        lock_acquired = True
        # 结束隐式事务：advisory lock 是会话级，跨事务保持，后续 conn.begin() 才可用。
        await conn.commit()
        # 在锁内补建缺失表（checkfirst 幂等）：并发启动时只有一个实例执行 create_all。
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_schema_migrations(conn)
        await conn.commit()
        applied = await _load_applied_scripts(conn)
        await conn.commit()
        scripts = list_migration_scripts()
        if not applied and os.environ.get(MIGRATE_FRESH_ENV, "").strip() != "1":
            # 首次部署（无任何记录）：全部捆绑脚本写为 baseline（不执行），一次事务记录。
            async with conn.begin():
                for script in scripts:
                    await _record_script(conn, script.name)
            return
        for script in scripts:
            if script.name in applied:
                continue
            # 每个脚本一个事务：脚本语句与记录同事务提交；失败整体回滚。
            try:
                async with conn.begin():
                    await _apply_script(conn, script)
                    await _record_script(conn, script.name)
            except Exception as exc:
                logger.error("迁移脚本执行失败: %s", script.name)
                raise RuntimeError(f"迁移脚本执行失败: {script.name}") from exc
    finally:
        try:
            if lock_acquired:
                await conn.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": MIGRATION_LOCK_KEY},
                )
                await conn.commit()
        except Exception:
            logger.warning("释放数据库迁移 advisory lock 失败", exc_info=True)
        finally:
            await conn.close()
