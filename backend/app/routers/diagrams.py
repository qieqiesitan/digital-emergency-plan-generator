from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import PlanProject, PlanSection, Enterprise, EmergencyResource
from app.models.enterprise_org import EnterpriseMember
from app.models.hazardous_chemicals import HazardousChemical
from app.routers.generation import _attach_diagrams, _collect_enterprise_data, _load_org_members
from app.services.risk_context_builder import build_risk_management_context

router = APIRouter(prefix="/plans", tags=["Diagrams"])


async def regenerate_missing_diagrams(db, plan, sections, ent_data) -> dict:
    regenerated = 0
    skipped = 0
    for s in sections:
        before = s.diagram_svgs or {}
        has_placeholder = any(
            isinstance(v, dict) and v.get("placeholder") for v in before.values()
        )
        if not has_placeholder:
            continue
        _attach_diagrams(s, plan.plan_type, ent_data)
        after = s.diagram_svgs or {}
        remaining = any(
            isinstance(v, dict) and v.get("placeholder") for v in after.values()
        )
        if remaining:
            skipped += 1
        else:
            regenerated += 1
    await db.commit()
    placeholders_remaining = sum(
        1 for s in sections
        if any(isinstance(v, dict) and v.get("placeholder") for v in (s.diagram_svgs or {}).values())
    )
    return {"regenerated": regenerated, "skipped": skipped, "placeholders_remaining": placeholders_remaining}


@router.post("/{plan_id}/diagrams/regenerate-missing")
async def regenerate_missing(plan_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(
        PlanProject.id == plan_id, PlanProject.user_id == current_user.id
    ))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "预案不存在")
    sections = (await db.execute(
        select(PlanSection).where(PlanSection.plan_project_id == plan_id)
    )).scalars().all()
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()
    resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == p.enterprise_id))).scalars().all()
    risk_context = await build_risk_management_context(p.enterprise_id, db) if ent else {}
    chemicals_rows = (await db.execute(
        select(HazardousChemical).where(HazardousChemical.enterprise_id == p.enterprise_id)
    )).scalars().all()
    chemicals = {c.id: c for c in chemicals_rows}
    org_members = await _load_org_members(db, p.enterprise_id) if ent else []
    ent_data = _collect_enterprise_data(ent, risk_context, resources, chemicals, org_members=org_members) if ent else {}
    result = await regenerate_missing_diagrams(db, p, sections, ent_data)
    return {"code": 0, "data": result}
