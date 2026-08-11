"""公开只读风险告知卡 API（无鉴权，token 校验）。

现场扫码经 /r/{token} 访问公开页，由前端路由跳转到本数据端点；
token 无效统一 404，不泄露任何卡片内容。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.enterprise import Enterprise
from app.models.risk_management import RiskObject
from app.schemas.common import ApiResponse
from app.schemas.risk_notice_card import CardData
from app.services.risk_notice_card_service import (
    build_card_data,
    load_events_and_measures,
)

router = APIRouter(prefix="/public/risk-notice-cards", tags=["Public Risk Notice Card"])


@router.get("/{token}", response_model=ApiResponse[CardData])
async def public_card(token: str, db: AsyncSession = Depends(get_db)):
    """公开只读：按 public_token 返回 CardData，无鉴权。"""
    obj = (
        await db.execute(
            select(RiskObject)
            .options(selectinload(RiskObject.zone))
            .where(RiskObject.public_token == token)
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "卡片不存在或链接已失效")
    ent = (
        await db.execute(
            select(Enterprise).where(Enterprise.id == obj.enterprise_id)
        )
    ).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "卡片不存在或链接已失效")
    objects = (
        await db.execute(
            select(RiskObject)
            .where(RiskObject.enterprise_id == obj.enterprise_id)
            .order_by(RiskObject.created_at)
        )
    ).scalars().all()
    events, measures = await load_events_and_measures(db, obj.id)
    data = await build_card_data(db, ent, obj, list(objects), events, measures)
    return ApiResponse(data=data)
