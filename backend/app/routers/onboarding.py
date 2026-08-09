from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.onboarding_service import compute_completion

router = APIRouter(tags=["Onboarding"])


@router.get("/enterprises/{enterprise_id}/completion", response_model=ApiResponse[dict])
async def get_enterprise_completion(
    enterprise_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Enterprise).where(
        Enterprise.id == enterprise_id,
        Enterprise.user_id == current_user.id,
    ))
    ent = result.scalar_one_or_none()
    if not ent:
        raise HTTPException(status_code=404, detail="企业不存在")
    data = await compute_completion(enterprise_id, db, enterprise=ent)
    return ApiResponse(data=data)
