"""DataHub API：来源、任务、待确认队列、确认入库、对账。"""

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.ingest import IngestItem, IngestJob, IngestSource
from app.schemas.ingest import ConfirmIn, ItemOut, JobIn, JobOut, SourceIn, SourceOut
from app.services.ingest_service import IngestError, confirm_items, skip_items

router = APIRouter(prefix="/ingest", tags=["Ingest"])


def _ok(data):
    return {"success": True, "code": 200, "message": "success", "data": data}


@router.get("/sources")
async def list_sources(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(IngestSource).order_by(IngestSource.created_at.desc()))
    return _ok([SourceOut.model_validate(s) for s in res.scalars().all()])


@router.post("/sources")
async def create_source(payload: SourceIn, db: AsyncSession = Depends(get_db)):
    src = IngestSource(**payload.model_dump())
    db.add(src)
    await db.commit()
    await db.refresh(src)
    return _ok(SourceOut.model_validate(src))


@router.get("/jobs")
async def list_jobs(
    source_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(IngestJob).order_by(IngestJob.created_at.desc()).limit(limit)
    if source_id:
        stmt = stmt.where(IngestJob.source_id == source_id)
    res = await db.execute(stmt)
    return _ok([JobOut.model_validate(j) for j in res.scalars().all()])


@router.post("/jobs")
async def create_job(
    payload: JobIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """开一次接入执行。

    导入向导必须先拿到 job_id 才能触发抽取——`ingest_items.job_id` 是指向本表的
    NOT NULL 外键，条目无法挂在一个不存在的任务上。
    计数显式置 0：ORM 的 `default` 要到 flush 才生效，此处不入库前就要返回给前端。
    """
    job = IngestJob(
        id=str(uuid4()),
        source_id=payload.source_id,
        trigger=payload.trigger,
        status="running",
        total=0,
        imported=0,
        skipped=0,
        failed=0,
        pending_review=0,
        created_by=getattr(user, "id", None),
    )
    db.add(job)
    await db.commit()
    return _ok(JobOut.model_validate(job))


@router.get("/items")
async def list_items(
    job_id: str = Query(...),
    status: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """待确认队列。返回 default_checked 供前端决定默认勾选状态。

    规则：仅 high/medium 默认勾选；low 默认不勾（低置信度不该被顺带入库）。
    """
    stmt = select(IngestItem).where(IngestItem.job_id == job_id)
    if status:
        stmt = stmt.where(IngestItem.status == status)
    stmt = stmt.order_by(IngestItem.confidence, IngestItem.created_at)
    res = await db.execute(stmt)
    out = []
    for it in res.scalars().all():
        row = ItemOut(
            id=it.id,
            job_id=it.job_id,
            target_entity=it.target_entity,
            status=it.status,
            confidence=it.confidence,
            source_locator=it.source_locator,
            raw_payload=it.raw_payload,
            error=it.error,
            review_note=it.review_note,
            default_checked=it.confidence in ("high", "medium") and it.status == "pending",
        )
        out.append(row)
    return _ok(out)


@router.post("/items/confirm")
async def confirm(
    payload: ConfirmIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """确认入库。只处理传入的 item_ids——前端"整批默认全选 + 勾掉错的"的落点。"""
    try:
        out = await confirm_items(
            db, item_ids=payload.item_ids, approved_by=getattr(user, "id", None)
        )
    except IngestError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _ok(out)


@router.post("/items/skip")
async def skip(
    payload: ConfirmIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """跳过选中条目（标记 skipped，不删除、不写正式表）。"""
    try:
        out = await skip_items(
            db, item_ids=payload.item_ids, reviewed_by=getattr(user, "id", None)
        )
    except IngestError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _ok(out)
