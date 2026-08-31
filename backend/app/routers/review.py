"""预案 AI 审查路由。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise, PlanProject, PlanSection
from app.services.plan_review_service import review_plan

router = APIRouter(prefix="/plans", tags=["Plan Review"])


@router.get("/{plan_id}/review")
async def get_plan_review(plan_id: str, current_user=Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(
        PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "预案不存在")
    ent = (await db.execute(select(Enterprise).where(
        Enterprise.id == p.enterprise_id))).scalar_one_or_none()
    sections = (await db.execute(select(PlanSection).where(
        PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order))).scalars().all()
    result = review_plan(p, ent, sections)
    return {"plan_id": plan_id, "title": p.title, **result}
