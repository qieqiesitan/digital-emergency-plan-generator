"""跨 worker 共享运行时状态（Postgres 表 app_runtime_state）。

替代模块级 dict/set：生成进度、生成防重、停止信号、报告生成租约等
以前都存在进程内存里，而生产是 4 worker，导致"防重失效/信号丢失/状态查不到"。

设计要点：
- 统一 TTL（expires_at），过期即失效，不需要清理任务；
- 租约（lease）带 owner，释放时校验 owner，避免旧持有者释放新租约；
- 所有函数接受可选 session 供测试注入；未传时自建短事务。
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _session_scope(session: AsyncSession | None):
    if session is not None:
        yield session
        return
    from app.database import async_session

    async with async_session() as own:
        async with own.begin():
            yield own


def _loads(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


async def set_state(key: str, value: dict, ttl_seconds: int | None = None,
                    session: AsyncSession | None = None) -> None:
    sql = text(
        "INSERT INTO app_runtime_state (key, value, expires_at, updated_at) "
        "VALUES (:key, CAST(:value AS jsonb), "
        "        CASE WHEN CAST(:ttl AS bigint) IS NULL THEN NULL "
        "             ELSE now() + CAST(:ttl AS bigint) * interval '1 second' END, now()) "
        "ON CONFLICT (key) DO UPDATE "
        "SET value = EXCLUDED.value, expires_at = EXCLUDED.expires_at, updated_at = now()"
    )
    async with _session_scope(session) as db:
        await db.execute(sql, {"key": key, "value": json.dumps(value, ensure_ascii=False),
                               "ttl": ttl_seconds})


async def get_state(key: str, session: AsyncSession | None = None) -> dict | None:
    sql = text(
        "SELECT value FROM app_runtime_state "
        "WHERE key = :key AND (expires_at IS NULL OR expires_at > now())"
    )
    async with _session_scope(session) as db:
        row = (await db.execute(sql, {"key": key})).fetchone()
    if not row:
        return None
    return _loads(row[0])


async def delete_state(key: str, session: AsyncSession | None = None) -> None:
    async with _session_scope(session) as db:
        await db.execute(text("DELETE FROM app_runtime_state WHERE key = :key"), {"key": key})


async def try_acquire_lease(key: str, ttl_seconds: int, owner: str,
                            session: AsyncSession | None = None) -> bool:
    """抢占租约：未过期则拿不到；过期/不存在则可抢占。"""
    sql = text(
        "INSERT INTO app_runtime_state (key, value, expires_at, updated_at) "
        "VALUES (:key, CAST(:value AS jsonb), "
        "        now() + CAST(:ttl AS bigint) * interval '1 second', now()) "
        "ON CONFLICT (key) DO UPDATE "
        "SET value = EXCLUDED.value, expires_at = EXCLUDED.expires_at, updated_at = now() "
        "WHERE app_runtime_state.expires_at IS NULL OR app_runtime_state.expires_at < now() "
        "RETURNING key"
    )
    async with _session_scope(session) as db:
        row = (await db.execute(sql, {
            "key": key, "value": json.dumps({"owner": owner}, ensure_ascii=False),
            "ttl": ttl_seconds,
        })).fetchone()
    return row is not None


async def release_lease(key: str, owner: str, session: AsyncSession | None = None) -> None:
    """仅持有者可释放（避免旧持有者误删新租约）。"""
    sql = text(
        "DELETE FROM app_runtime_state "
        "WHERE key = :key AND value->>'owner' = :owner"
    )
    async with _session_scope(session) as db:
        await db.execute(sql, {"key": key, "owner": owner})


async def incr_counter(key: str, ttl_seconds: int,
                       session: AsyncSession | None = None) -> int:
    """固定窗口计数器：过期后自动从 1 重新计数，返回当前窗口计数。"""
    sql = text(
        "INSERT INTO app_runtime_state (key, value, expires_at, updated_at) "
        "VALUES (:key, jsonb_build_object('count', 1), "
        "        now() + CAST(:ttl AS bigint) * interval '1 second', now()) "
        "ON CONFLICT (key) DO UPDATE SET "
        "  value = CASE WHEN app_runtime_state.expires_at IS NOT NULL "
        "                AND app_runtime_state.expires_at <= now() "
        "              THEN jsonb_build_object('count', 1) "
        "              ELSE jsonb_build_object('count', "
        "                   COALESCE((app_runtime_state.value->>'count')::int, 0) + 1) END, "
        "  expires_at = CASE WHEN app_runtime_state.expires_at IS NOT NULL "
        "                     AND app_runtime_state.expires_at <= now() "
        "                   THEN EXCLUDED.expires_at ELSE app_runtime_state.expires_at END, "
        "  updated_at = now() "
        "RETURNING (value->>'count')::int"
    )
    async with _session_scope(session) as db:
        row = (await db.execute(sql, {"key": key, "ttl": ttl_seconds})).fetchone()
    return int(row[0]) if row else 0


async def consume_once(key: str, ttl_seconds: int,
                       session: AsyncSession | None = None) -> bool:
    """一次性消费（nonce 防重放）：首次返回 True，TTL 内重复返回 False。"""
    sql = text(
        "INSERT INTO app_runtime_state (key, value, expires_at, updated_at) "
        "VALUES (:key, '{}'::jsonb, "
        "        now() + CAST(:ttl AS bigint) * interval '1 second', now()) "
        "ON CONFLICT (key) DO UPDATE "
        "SET value = EXCLUDED.value, expires_at = EXCLUDED.expires_at, updated_at = now() "
        "WHERE app_runtime_state.expires_at IS NOT NULL AND app_runtime_state.expires_at < now() "
        "RETURNING key"
    )
    async with _session_scope(session) as db:
        row = (await db.execute(sql, {"key": key, "ttl": ttl_seconds})).fetchone()
    return row is not None
