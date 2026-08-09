from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.common import ApiResponse
from app.services.onboarding_service import compute_completion

router = APIRouter(tags=["Onboarding"])


@router.get("/enterprises/{enterprise_id}/completion", response_model=ApiResponse[dict])
async def get_enterprise_completion(
    enterprise_id: str,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await compute_completion(enterprise_id, db)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return ApiResponse(data=data)
