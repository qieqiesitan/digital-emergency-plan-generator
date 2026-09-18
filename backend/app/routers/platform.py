"""平台级 API：AI 能力管理、调用统计、跨企业总览。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ai_capability import AICapability
from app.schemas.platform import CapabilityOut, CapabilityUpdateIn
from app.services.ai_usage_stats import usage_stats
from app.services.platform_overview import overview_totals

router = APIRouter(prefix="/platform", tags=["Platform"])


def _ok(data):
    return {"success": True, "code": 200, "message": "success", "data": data}


@router.get("/capabilities")
async def list_capabilities(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(AICapability).order_by(AICapability.sort_order))
    return _ok([CapabilityOut.model_validate(c) for c in res.scalars().all()])


@router.put("/capabilities/{code}")
async def update_capability(
    code: str, payload: CapabilityUpdateIn, db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(AICapability).where(AICapability.code == code))
    cap = res.scalar_one_or_none()
    if cap is None:
        raise HTTPException(404, "AI 能力不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(cap, key, value)
    await db.commit()
    return _ok(CapabilityOut.model_validate(cap))


@router.get("/ai-usage")
async def ai_usage(
    days: int = Query(default=30, ge=1, le=365),
    module: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """AI 调用统计：按能力看调用数、失败率、截断数、token 与耗时。"""
    return _ok(await usage_stats(db, days=days, module=module))


@router.get("/overview")
async def platform_overview(db: AsyncSession = Depends(get_db)):
    """跨企业总览。注意：这是平台级视角，与单企业驾驶舱不同。"""
    return _ok(await overview_totals(db))
