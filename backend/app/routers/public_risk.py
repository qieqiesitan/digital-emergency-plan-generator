"""重大风险公示公开只读端点（无鉴权，token 校验 + 数据脱敏）。"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.enterprise import Enterprise
from app.models.risk_management import RiskZone
from app.schemas.common import ApiResponse
from app.services.risk_control_list_service import (
    ZONE_TREE_OPTIONS,
    desensitize,
    flatten_rows,
    is_major_publicity_row,
)

router = APIRouter(prefix="/public/risk", tags=["Public Risk"])


@router.get("/{token}", response_model=ApiResponse[dict])
async def public_risk(token: str, db: AsyncSession = Depends(get_db)):
    ent = (await db.execute(
        select(Enterprise).where(Enterprise.public_risk_token == token)
    )).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "链接已失效")
    zones = (await db.execute(
        select(RiskZone).where(RiskZone.enterprise_id == ent.id).options(*ZONE_TREE_OPTIONS)
    )).scalars().all()
    rows = [r for r in flatten_rows(zones, {})
            if is_major_publicity_row(r)]
    return ApiResponse(data={
        "enterprise_name": ent.name,
        "items": desensitize(rows),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })
