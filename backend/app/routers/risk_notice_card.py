"""风险告知卡列表/详情 API。

列表返回 CardSummary 摘要（含筛选），详情返回 CardData 全量数据。
导出/AI 优化/快照/token 端点由后续任务补充。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.risk_management import RiskEvent, RiskObject, RiskUnit
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.risk_notice_card import CardData, CardSummary
from app.services.risk_notice_card_data import LEVEL_COLORS, LEVEL_ORDER
from app.services.risk_notice_card_service import (
    build_card_data,
    collect_measures,
    compute_level,
    match_signs,
    merge_object_events,
    resolve_responsible,
)

router = APIRouter(
    prefix="/enterprises/{enterprise_id}/risk-notice-cards",
    tags=["Risk Notice Card"],
)

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

    summaries: list[CardSummary] = []
    for obj in objs:
        events = merge_object_events(obj)
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
