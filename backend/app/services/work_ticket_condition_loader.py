"""措施条件的键工具与运行时加载。

规范化规则（锚定与查找共用同一函数，见规格 §4）：去空白、全角转半角、去尾部标点。
刻意不做模糊匹配与同义词替换——把「改了字的另一条措施」错认成同一条，
正是这套设计要避免的静默错判。
"""

from __future__ import annotations

import hashlib
import re
import time
import unicodedata

from sqlalchemy import select

_TAIL_PUNCT = "。；;.，,、"

# 映射表读取缓存：重跑生成器并入库后 30 秒内自动生效（或显式 invalidate）
CACHE_TTL_SECONDS = 30.0
_CACHE: dict[str, tuple[float, object]] = {}


def normalize_measure_text(text: str) -> str:
    """规范化措施正文：去空白 + 全角转半角 + 去尾部标点。"""
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = re.sub(r"\s+", "", normalized)
    return normalized.rstrip(_TAIL_PUNCT)


def measure_ref(text: str) -> str:
    """措施正文的稳定锚点（规范化后的 sha256 前 32 位）。

    用正文而不是序号：标准修订若插入一条措施，序号整体后移，
    按序号锚定会把「不涉及」判到错误的措施上。
    """
    digest = hashlib.sha256(normalize_measure_text(text).encode("utf-8")).hexdigest()
    return digest[:32]


async def load_conditions(db) -> dict[tuple[str, str], tuple[str, ...]]:
    """{(ticket_type, measure_ref): (condition_key, ...)}，进程内缓存 30 秒。"""
    cached = _CACHE.get("conditions")
    if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]  # type: ignore[return-value]
    from app.models.work_ticket_condition import WorkTicketMeasureCondition

    rows = (
        await db.execute(
            select(WorkTicketMeasureCondition).order_by(
                WorkTicketMeasureCondition.ticket_type,
                WorkTicketMeasureCondition.sort_order,
            )
        )
    ).scalars().all()
    grouped: dict[tuple[str, str], list[str]] = {}
    for row in rows:
        grouped.setdefault((row.ticket_type, row.measure_ref), []).append(row.condition_key)
    result = {key: tuple(value) for key, value in grouped.items()}
    _CACHE["conditions"] = (time.monotonic(), result)
    return result


async def load_condition_labels(db) -> dict[str, str]:
    """{condition_key: 中文名}（从情景表取；自动项不在情景表里，故另需 YAML 兜底）。"""
    cached = _CACHE.get("labels")
    if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]  # type: ignore[return-value]
    from app.models.work_ticket_condition import WorkTicketScenario

    rows = (await db.execute(select(WorkTicketScenario))).scalars().all()
    labels = {row.condition_key: row.label for row in rows}
    _CACHE["labels"] = (time.monotonic(), labels)
    return labels


async def load_scenarios(db, ticket_type: str) -> list[dict]:
    """该票种的情景区（只含人工勾选项，auto_rule 为空的项）。"""
    from app.models.work_ticket_condition import WorkTicketScenario

    rows = (
        await db.execute(
            select(WorkTicketScenario)
            .where(
                WorkTicketScenario.ticket_type == ticket_type,
                WorkTicketScenario.auto_rule.is_(None),
            )
            .order_by(WorkTicketScenario.sort_order)
        )
    ).scalars().all()
    return [{"key": row.condition_key, "label": row.label} for row in rows]


async def load_scenarios_by_type(db) -> dict[str, list[dict]]:
    """全部票种的情景区，按票种分组（供 /templates 一次取完，避免 N+1）。"""
    from app.models.work_ticket_condition import WorkTicketScenario

    rows = (
        await db.execute(
            select(WorkTicketScenario)
            .where(WorkTicketScenario.auto_rule.is_(None))
            .order_by(WorkTicketScenario.ticket_type, WorkTicketScenario.sort_order)
        )
    ).scalars().all()
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row.ticket_type, []).append(
            {"key": row.condition_key, "label": row.label}
        )
    return grouped


def invalidate_condition_cache() -> None:
    """重跑生成器并入库后调用（否则最多等 30 秒自动过期）。"""
    _CACHE.clear()
