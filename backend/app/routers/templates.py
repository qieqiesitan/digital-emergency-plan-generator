from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.enterprise import PlanTemplate
from app.schemas.template import TemplateResponse
from app.schemas.common import ApiResponse, PaginatedResponse, PaginatedData

router = APIRouter(prefix="/templates", tags=["Templates"])

@router.get("", response_model=PaginatedResponse[TemplateResponse])
async def list_templates(plan_type: str = Query(""), db: AsyncSession = Depends(get_db)):
    query = select(PlanTemplate).where(PlanTemplate.is_active == True)
    if plan_type: query = query.where(PlanTemplate.plan_type == plan_type)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    rows = (await db.execute(query.order_by(PlanTemplate.plan_type, PlanTemplate.version.desc()))).scalars().all()
    items = [TemplateResponse.model_validate(t) for t in rows]
    return PaginatedResponse(data=PaginatedData(items=items, total=total, page=1, page_size=100))

@router.get("/{template_id}", response_model=ApiResponse[TemplateResponse])
async def get_template(template_id: str, db: AsyncSession = Depends(get_db)):
    t = (await db.execute(select(PlanTemplate).where(PlanTemplate.id == template_id))).scalar_one_or_none()
    if not t: raise HTTPException(404, "模板不存在")
    return ApiResponse(data=TemplateResponse.model_validate(t))
