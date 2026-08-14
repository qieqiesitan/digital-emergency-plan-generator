"""重大风险公示公开只读端点（无鉴权，token 校验 + 数据脱敏）。"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.enterprise import Enterprise
from app.models.risk_management import RiskEvent, RiskObject, RiskUnit, RiskZone
from app.schemas.common import ApiResponse
from app.services.risk_control_list_service import desensitize, flatten_rows

router = APIRouter(prefix="/public/risk", tags=["Public Risk"])

_ZONE_TREE_OPTIONS = (
    selectinload(RiskZone.objects).selectinload(RiskObject.units).selectinload(RiskUnit.events).selectinload(RiskEvent.measures),
    selectinload(RiskZone.objects).selectinload(RiskObject.events).selectinload(RiskEvent.measures),
)


@router.get("/{token}", response_model=ApiResponse[dict])
async def public_risk(token: str, db: AsyncSession = Depends(get_db)):
    ent = (await db.execute(
        select(Enterprise).where(Enterprise.public_risk_token == token)
    )).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "链接已失效")
    zones = (await db.execute(
        select(RiskZone).where(RiskZone.enterprise_id == ent.id).options(*_ZONE_TREE_OPTIONS)
    )).scalars().all()
    rows = [r for r in flatten_rows(zones, {})
            if r["current"] == "重大" or r["control_level"] == "企业"]
    return ApiResponse(data={
        "enterprise_name": ent.name,
        "items": desensitize(rows),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })
