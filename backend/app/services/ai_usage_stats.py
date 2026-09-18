"""AI 调用统计：把 llm_call_logs 聚合成运营能看懂的数字。

只做聚合查询，不新增采集——采集在 llm_client 的埋点里做（计划 2）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_call_log import LlmCallLog


def summarize_rows(rows: Sequence) -> dict:
    """把调用日志行聚合成统计。纯函数，便于单测与复用。"""
    if not rows:
        return {"total_calls": 0, "total_tokens": 0, "total_truncated": 0, "by_capability": []}

    buckets: dict[str, dict] = {}
    total_tokens = 0
    total_truncated = 0

    for r in rows:
        cap = getattr(r, "capability", None) or "unknown"
        b = buckets.setdefault(
            cap,
            {"capability": cap, "calls": 0, "failures": 0, "truncated": 0,
             "tokens": 0, "duration_sum": 0, "duration_n": 0},
        )
        b["calls"] += 1
        if not getattr(r, "success", True):
            b["failures"] += 1
        if getattr(r, "truncated", False):
            b["truncated"] += 1
            total_truncated += 1
        tokens = getattr(r, "total_tokens", None)
        if tokens:
            b["tokens"] += int(tokens)
            total_tokens += int(tokens)
        duration = getattr(r, "duration_ms", None)
        if duration is not None:
            b["duration_sum"] += int(duration)
            b["duration_n"] += 1

    by_capability = []
    for b in buckets.values():
        calls = b["calls"]
        by_capability.append(
            {
                "capability": b["capability"],
                "calls": calls,
                "failures": b["failures"],
                "failure_rate": round(b["failures"] / calls, 4) if calls else 0.0,
                "truncated": b["truncated"],
                "tokens": b["tokens"],
                "avg_duration_ms": round(b["duration_sum"] / b["duration_n"]) if b["duration_n"] else None,
            }
        )
    by_capability.sort(key=lambda x: x["calls"], reverse=True)
    return {
        "total_calls": len(rows),
        "total_tokens": total_tokens,
        "total_truncated": total_truncated,
        "by_capability": by_capability,
    }


async def usage_stats(
    db: AsyncSession,
    *,
    days: int = 30,
    module: Optional[str] = None,
    now: Optional[datetime] = None,
) -> dict:
    """取最近 N 天的调用日志并聚合。"""
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    stmt = select(LlmCallLog).where(LlmCallLog.created_at >= since)
    if module:
        stmt = stmt.where(LlmCallLog.module == module)
    res = await db.execute(stmt)
    rows = list(res.scalars().all())
    out = summarize_rows(rows)
    out["since"] = since.isoformat()
    out["days"] = days
    return out
