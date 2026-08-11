"""风险告知卡 API。

列表返回 CardSummary 摘要（含筛选），详情返回 CardData 全量数据，
AI 优化（ai-optimize）、快照（snapshot）与批量 docx 导出（export）端点已实现。
token 端点由任务 9 补充。
"""
import os
import logging
import asyncio
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.risk_notice_card import RiskNoticeCard
from app.models.risk_management import RiskEvent, RiskObject, RiskUnit
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.risk_notice_card import (
    AiOptimizeResponse,
    CardData,
    CardSummary,
    ExportRequest,
    ExportResponse,
    SnapshotSaveRequest,
    SnapshotResponse,
    TokenResetResponse,
)
from app.services.risk_notice_card_data import LEVEL_COLORS, LEVEL_ORDER
from app.services.risk_notice_card_ai import optimize_right_column
from app.services.risk_notice_card_docx import render_cards_docx, svg_to_png
from app.services.risk_notice_card_service import (
    build_card_data,
    build_right_column,
    collect_measures,
    compute_level,
    is_stale,
    load_events_and_measures,
    match_signs,
    merge_object_events,
    resolve_responsible,
    save_snapshot,
)

router = APIRouter(
    prefix="/enterprises/{enterprise_id}/risk-notice-cards",
    tags=["Risk Notice Card"],
)

logger = logging.getLogger(__name__)

# 合法 level 筛选值：LEVEL_ORDER（重大/较大/一般/低）+ 未评估
VALID_LEVELS = [*LEVEL_ORDER, "未评估"]


async def _get_ent(eid: str, uid: str, db: AsyncSession) -> Enterprise:
    ent = (
        await db.execute(
            select(Enterprise).where(Enterprise.id == eid, Enterprise.user_id == uid)
        )
    ).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    return ent


@router.get("", response_model=ApiResponse[list[CardSummary]])
async def list_cards(
    enterprise_id: str,
    level: str | None = Query(None),
    zone_id: str | None = None,
    keyword: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if level is not None and level not in VALID_LEVELS:
        raise HTTPException(
            422, f"非法的 level 参数：{level}，合法值：{', '.join(VALID_LEVELS)}"
        )
    ent = await _get_ent(enterprise_id, current_user.id, db)
    objs = (
        await db.execute(
            select(RiskObject)
            .options(
                selectinload(RiskObject.zone),
                selectinload(RiskObject.units)
                .selectinload(RiskUnit.events)
                .selectinload(RiskEvent.measures),
                selectinload(RiskObject.events).selectinload(RiskEvent.measures),
            )
            .where(RiskObject.enterprise_id == enterprise_id)
            .order_by(RiskObject.created_at)
        )
    ).scalars().all()
    snap_rows = (
        await db.execute(
            select(RiskNoticeCard).where(
                RiskNoticeCard.enterprise_id == enterprise_id
            )
        )
    ).scalars().all()
    snapshot_by_object = {s.object_id: s for s in snap_rows}

    summaries: list[CardSummary] = []
    for obj in objs:
        events = merge_object_events(obj)
        measures = collect_measures(events)
        timestamps = [
            t
            for t in (
                [obj.updated_at or obj.created_at]
                + [e.updated_at or e.created_at for e in events]
                + [m.updated_at or m.created_at for m in measures]
            )
            if t is not None
        ]
        source_updated = max(timestamps) if timestamps else None
        snap = snapshot_by_object.get(obj.id)
        lv = compute_level(events)
        if level and lv != level:
            continue
        if zone_id and obj.zone_id != zone_id:
            continue
        if keyword and keyword not in obj.name and keyword not in (obj.responsible_unit or ""):
            continue
        unit, _person, _phone, _fallback = resolve_responsible(obj, ent)
        accident_types = list(
            dict.fromkeys(e.accident_type for e in events if e.accident_type)
        )
        summaries.append(
            CardSummary(
                object_id=obj.id,
                name=obj.name,
                zone_name=obj.zone.name if obj.zone else "",
                level=lv,
                level_color=LEVEL_COLORS.get(lv, "#bfbfbf"),
                accident_types=accident_types,
                signs=match_signs(accident_types),
                responsible_unit=unit,
                public_url=f"/r/{obj.public_token}",
                snapshot=(
                    {"version": snap.version, "source": snap.source}
                    if snap
                    else None
                ),
                stale=is_stale(snap, source_updated) if snap else False,
            )
        )
    return ApiResponse(data=summaries)


@router.get("/{object_id}", response_model=ApiResponse[CardData])
async def card_detail(
    enterprise_id: str,
    object_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ent = await _get_ent(enterprise_id, current_user.id, db)
    obj = (
        await db.execute(
            select(RiskObject)
            .options(
                selectinload(RiskObject.units)
                .selectinload(RiskUnit.events)
                .selectinload(RiskEvent.measures),
                selectinload(RiskObject.events).selectinload(RiskEvent.measures),
            )
            .where(
                RiskObject.id == object_id,
                RiskObject.enterprise_id == enterprise_id,
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "风险点不存在")
    objects = (
        await db.execute(
            select(RiskObject)
            .where(RiskObject.enterprise_id == enterprise_id)
            .order_by(RiskObject.created_at)
        )
    ).scalars().all()
    events = merge_object_events(obj)
    measures = collect_measures(events)
    data = await build_card_data(db, ent, obj, list(objects), events, measures)
    return ApiResponse(data=data)


@router.post("/export", response_model=ApiResponse[ExportResponse])
async def export_cards(
    enterprise_id: str,
    body: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批量导出风险告知卡 docx（A4 每卡一页 + 右上角二维码）。

    先一次查询企业全部风险点（compute_code 需要）用于逐卡归属校验并组装
    CardData；不存在的 object_id 跳过并记入 warnings；全部无效时返回 400。
    生成文件落入 settings.EXPORT_DIR。
    """
    ent = await _get_ent(enterprise_id, current_user.id, db)
    objects = (
        await db.execute(
            select(RiskObject)
            .where(RiskObject.enterprise_id == enterprise_id)
            .order_by(RiskObject.created_at)
        )
    ).scalars().all()
    object_by_id = {obj.id: obj for obj in objects}
    cards: list[CardData] = []
    warnings: list[str] = []
    for oid in body.object_ids:
        obj = object_by_id.get(oid)
        if obj is None:
            warnings.append(f"风险点不存在：{oid}")
            continue
        events, measures = await load_events_and_measures(db, oid)
        cards.append(
            await build_card_data(db, ent, obj, list(objects), events, measures)
        )
    if not cards:
        raise HTTPException(400, "没有可导出的卡片")

    sign_pngs: dict[str, bytes] = {}
    for card in cards:
        for sign in card.signs:
            if sign.svg_name not in sign_pngs:
                sign_pngs[sign.svg_name] = await svg_to_png(sign.svg_name)

    os.makedirs(settings.EXPORT_DIR, exist_ok=True)
    file_key = (
        f"risk-notice-{enterprise_id[:8]}-"
        f"{datetime.now().strftime('%Y%m%d%H%M%S-%f')}.docx"
    )
    out_path = os.path.join(settings.EXPORT_DIR, file_key)
    try:
        await asyncio.to_thread(render_cards_docx, cards, out_path, sign_pngs)
    except Exception:
        logger.exception("风险告知卡导出渲染失败: enterprise=%s", enterprise_id)
        raise HTTPException(500, "导出失败，请稍后重试")
    if warnings:
        logger.warning(
            "风险告知卡导出：%d 个 object_id 不存在，已跳过：%s",
            len(warnings),
            "，".join(warnings),
        )
    return ApiResponse(data=ExportResponse(file_key=file_key, warnings=warnings))


@router.post("/{object_id}/ai-optimize", response_model=ApiResponse[AiOptimizeResponse])
async def ai_optimize(
    enterprise_id: str,
    object_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ent = await _get_ent(enterprise_id, current_user.id, db)
    obj = (
        await db.execute(
            select(RiskObject).where(
                RiskObject.id == object_id,
                RiskObject.enterprise_id == enterprise_id,
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "风险点不存在")
    events, measures = await load_events_and_measures(db, object_id)
    original = build_right_column(events, measures)
    try:
        optimized = await optimize_right_column(
            db, current_user.id, ent.name, obj.name, original
        )
    except HTTPException:
        raise  # AI 未配置等业务错误保留原语义（如 400）
    except Exception:
        logger.exception(
            "风险告知卡 AI 优化失败: enterprise=%s object=%s",
            enterprise_id,
            object_id,
        )
        raise HTTPException(502, "AI 优化失败，请稍后重试或保留原版")
    return ApiResponse(data=AiOptimizeResponse(original=original, optimized=optimized))


@router.put("/{object_id}/snapshot", response_model=ApiResponse[SnapshotResponse])
async def save_card_snapshot(
    enterprise_id: str,
    object_id: str,
    body: SnapshotSaveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_ent(enterprise_id, current_user.id, db)
    obj = (
        await db.execute(
            select(RiskObject).where(
                RiskObject.id == object_id,
                RiskObject.enterprise_id == enterprise_id,
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "风险点不存在")
    snap = await save_snapshot(
        db, enterprise_id, object_id, current_user.id, body.content.model_dump()
    )
    return ApiResponse(data=SnapshotResponse(version=snap.version, source=snap.source))


@router.post("/{object_id}/token/reset", response_model=ApiResponse[TokenResetResponse])
async def reset_token(
    enterprise_id: str,
    object_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """重置公开 token：旧链接立即 404，返回新公开链接。"""
    await _get_ent(enterprise_id, current_user.id, db)
    obj = (
        await db.execute(
            select(RiskObject).where(
                RiskObject.id == object_id,
                RiskObject.enterprise_id == enterprise_id,
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "风险点不存在")
    obj.public_token = secrets.token_hex(32)
    await db.commit()
    return ApiResponse(data=TokenResetResponse(public_url=f"/r/{obj.public_token}"))
