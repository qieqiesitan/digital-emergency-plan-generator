from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.enterprise import PlanProject, PlanSection
from app.schemas.plan import SectionResponse, SectionUpdate
from app.schemas.common import ApiResponse
from app.dependencies import get_current_user

router = APIRouter(prefix="/plans", tags=["Sections"])

@router.get("/{plan_id}/sections", response_model=ApiResponse[list[SectionResponse]])
async def list_sections(plan_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p: raise HTTPException(404, "预案不存在")
    rows = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order))).scalars().all()
    return ApiResponse(data=[SectionResponse.model_validate(s) for s in rows])

@router.get("/{plan_id}/sections/{section_key}", response_model=ApiResponse[SectionResponse])
async def get_section(plan_id: str, section_key: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p: raise HTTPException(404, "预案不存在")
    s = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id, PlanSection.section_key == section_key))).scalar_one_or_none()
    if not s: raise HTTPException(404, "章节不存在")
    return ApiResponse(data=SectionResponse.model_validate(s))

@router.put("/{plan_id}/sections/{section_key}", response_model=ApiResponse[SectionResponse])
async def update_section(plan_id: str, section_key: str, data: SectionUpdate, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p: raise HTTPException(404, "预案不存在")
    s = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id, PlanSection.section_key == section_key))).scalar_one_or_none()
    if not s: raise HTTPException(404, "章节不存在")
    s.content = data.content; await db.commit(); await db.refresh(s)
    return ApiResponse(data=SectionResponse.model_validate(s))
