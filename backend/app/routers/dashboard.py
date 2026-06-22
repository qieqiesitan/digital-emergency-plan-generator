from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.user import User
from app.models.enterprise import Enterprise, PlanProject, RiskSource
from app.schemas.dashboard import DashboardResponse, DashboardStats, DashboardRecentPlan, DashboardRecentEnterprise
from app.schemas.common import ApiResponse
from app.dependencies import get_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("", response_model=ApiResponse[DashboardResponse])
async def get_dashboard(current_user=Depends(get_current_user), db=Depends(get_db)):
    ent_count = (await db.execute(select(func.count(Enterprise.id)).where(Enterprise.user_id == current_user.id))).scalar() or 0
    plan_count = (await db.execute(select(func.count(PlanProject.id)).where(PlanProject.user_id == current_user.id))).scalar() or 0
    completed = (await db.execute(select(func.count(PlanProject.id)).where(PlanProject.user_id == current_user.id, PlanProject.status == "completed"))).scalar() or 0
    rs_query = select(func.count(RiskSource.id)).join(Enterprise).where(Enterprise.user_id == current_user.id)
    rs_count = (await db.execute(rs_query)).scalar() or 0
    stats = DashboardStats(enterprise_count=ent_count, plan_count=plan_count, completed_plan_count=completed, risk_source_count=rs_count)

    recent_plans_rows = (await db.execute(select(PlanProject).where(PlanProject.user_id == current_user.id).order_by(PlanProject.updated_at.desc()).limit(5))).scalars().all()
    recent_plans = []
    for p in recent_plans_rows:
        ent_name = (await db.execute(select(Enterprise.name).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none() or ""
        total_s = len(p.sections or [])
        comp_s = sum(1 for s in (p.sections or []) if s.content and s.content.strip())
        recent_plans.append(DashboardRecentPlan(id=p.id, title=p.title, plan_type=p.plan_type, enterprise_name=ent_name, status=p.status, completed_sections=comp_s, total_sections=total_s, updated_at=p.updated_at.isoformat() if p.updated_at else ""))

    recent_ents = (await db.execute(select(Enterprise).where(Enterprise.user_id == current_user.id).order_by(Enterprise.updated_at.desc()).limit(5))).scalars().all()
    recent_enterprises = [DashboardRecentEnterprise(id=e.id, name=e.name, plan_count=len(e.plans or []), updated_at=e.updated_at.isoformat() if e.updated_at else "") for e in recent_ents]

    return ApiResponse(data=DashboardResponse(stats=stats, recent_plans=recent_plans, recent_enterprises=recent_enterprises))
