"""DataHub 接入服务核心。

一条铁律：**只有 confirm_items() 会把数据写进正式业务表**。
文件解析、AI 抽取、外部推送一律只能产出 status='pending' 的 ingest_items。
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Awaitable, Callable, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingest import IngestItem, IngestJob

logger = logging.getLogger("ingest_service")

TargetWriter = Callable[[AsyncSession, dict, IngestItem], Awaitable[str]]


class IngestError(ValueError):
    """接入流程中的数据或状态错误。"""


def build_idempotency_key(
    *,
    source_id: str,
    target: str,
    external_id: Optional[str] = None,
    payload: Optional[dict] = None,
) -> str:
    """幂等键：优先用来源侧外部 id；没有则用载荷内容 hash。

    必须同时带 source_id 与 target，避免不同来源/不同目标之间撞键。
    """
    if external_id:
        raw = f"{source_id}|{target}|{external_id}"
    elif payload:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        raw = f"{source_id}|{target}|{hashlib.sha256(body.encode('utf-8')).hexdigest()}"
    else:
        raise IngestError("生成幂等键需要 external_id 或 payload 之一")
    return raw[:300]


async def create_item(
    db: AsyncSession,
    *,
    job_id: str,
    idempotency_key: str,
    raw_payload: dict,
    target_entity: str,
    source_locator: Optional[str] = None,
    confidence: str = "medium",
) -> dict:
    """写入一条待确认条目。命中幂等键则跳过（不新增行）。"""
    res = await db.execute(
        select(IngestItem).where(IngestItem.idempotency_key == idempotency_key)
    )
    existing = res.scalar_one_or_none()
    if existing is not None:
        return {"created": False, "item_id": existing.id}
    row = IngestItem(
        job_id=job_id,
        idempotency_key=idempotency_key,
        raw_payload=raw_payload,
        target_entity=target_entity,
        status="pending",
        source_locator=source_locator,
        confidence=confidence,
    )
    db.add(row)
    await db.commit()
    return {"created": True, "item_id": getattr(row, "id", None)}


# 目标实体 → 写库函数。新增目标实体时在此注册，不要在调用点写 if/else。
TARGET_WRITERS: dict[str, TargetWriter] = {}


def register_target_writer(target_entity: str, fn: TargetWriter) -> None:
    TARGET_WRITERS[target_entity] = fn


async def _persist_target(
    db: AsyncSession, *, target_entity: str, raw_payload: dict, item: IngestItem
) -> str:
    writer = TARGET_WRITERS.get(target_entity)
    if writer is None:
        raise IngestError(f"目标实体「{target_entity}」尚未注册写入器")
    return await writer(db, raw_payload, item)


async def confirm_items(
    db: AsyncSession,
    *,
    item_ids: Sequence[str],
    approved_by: Optional[str] = None,
) -> dict:
    """确认入库：只处理传入的 item_ids。

    已审过的条目直接拒绝——避免重复入库与重复计量。
    单条失败不影响其余条目，失败的留在队列里可重试。
    """
    if not item_ids:
        raise IngestError("没有选中任何条目")
    confirmed = 0
    failed: list[dict] = []
    for item_id in item_ids:
        res = await db.execute(select(IngestItem).where(IngestItem.id == item_id))
        item = res.scalar_one_or_none()
        if item is None:
            failed.append({"item_id": item_id, "reason": "条目不存在"})
            continue
        if item.status != "pending":
            raise IngestError(f"条目 {item_id} 当前状态为 {item.status}，不能重复确认")
        try:
            target_id = await _persist_target(
                db,
                target_entity=item.target_entity,
                raw_payload=item.raw_payload,
                item=item,
            )
            item.status = "imported"
            item.target_id = target_id
            item.reviewed_by = approved_by
            confirmed += 1
        except Exception as exc:
            logger.exception("入库失败 item=%s", item_id)
            item.status = "failed"
            item.error = str(exc)[:2000]
            failed.append({"item_id": item_id, "reason": str(exc)[:300]})
    await db.commit()
    return {"confirmed": confirmed, "failed": failed}


async def update_job_counts(db: AsyncSession, *, job: IngestJob) -> dict:
    """按条目实际状态回填任务计数。计数由数据推导，不靠调用方自己累加。"""
    res = await db.execute(
        select(IngestItem.status, func.count())
        .where(IngestItem.job_id == job.id)
        .group_by(IngestItem.status)
    )
    counts = {status: int(n) for status, n in res.all()}
    job.total = sum(counts.values())
    job.imported = counts.get("imported", 0)
    job.skipped = counts.get("skipped", 0)
    job.failed = counts.get("failed", 0)
    job.pending_review = counts.get("pending", 0) + counts.get("needs_review", 0)
    if job.failed:
        job.status = "partial"
    elif job.pending_review:
        job.status = "running"
    else:
        job.status = "succeeded"
    await db.commit()
    return {
        "total": job.total,
        "imported": job.imported,
        "skipped": job.skipped,
        "failed": job.failed,
        "pending_review": job.pending_review,
    }
