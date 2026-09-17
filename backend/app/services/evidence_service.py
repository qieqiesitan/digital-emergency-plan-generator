"""依据层读写服务。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence import EvidenceRef


@dataclass(frozen=True)
class EvidenceInput:
    article_anchor: str
    regulation_id: str | None = None
    relation: str = "依据"
    note: str | None = None


async def _existing_anchors(db: AsyncSession, owner_type: str, owner_id: str) -> set[str]:
    res = await db.execute(
        select(EvidenceRef).where(
            EvidenceRef.owner_type == owner_type, EvidenceRef.owner_id == owner_id
        )
    )
    return {f"{r.article_anchor}|{r.relation}" for r in res.scalars().all()}


async def attach_evidence(
    db: AsyncSession,
    *,
    owner_type: str,
    owner_id: str,
    items: list[EvidenceInput],
    user_id: str | None = None,
) -> int:
    """挂载依据；同一 owner + 同一条文 + 同一关系已存在时跳过（幂等）。返回新增条数。"""
    if not owner_type or not owner_id:
        raise ValueError("owner_type 与 owner_id 不能为空")
    seen = await _existing_anchors(db, owner_type, owner_id)
    created = 0
    for item in items:
        key = f"{item.article_anchor}|{item.relation}"
        if key in seen:
            continue
        db.add(
            EvidenceRef(
                owner_type=owner_type,
                owner_id=owner_id,
                regulation_id=item.regulation_id,
                article_anchor=item.article_anchor,
                relation=item.relation,
                note=item.note,
                created_by=user_id,
            )
        )
        seen.add(key)
        created += 1
    if created:
        await db.commit()
    return created


async def list_evidence(db: AsyncSession, *, owner_type: str, owner_id: str) -> list[dict]:
    res = await db.execute(
        select(EvidenceRef)
        .where(EvidenceRef.owner_type == owner_type, EvidenceRef.owner_id == owner_id)
        .order_by(EvidenceRef.created_at)
    )
    return [
        {
            "id": r.id,
            "regulation_id": r.regulation_id,
            "article_anchor": r.article_anchor,
            "relation": r.relation,
            "note": r.note,
        }
        for r in res.scalars().all()
    ]
