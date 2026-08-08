from uuid import uuid4
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, and_
from app.database import get_db
from app.models.user import User
from app.models.enterprise import Enterprise, PlanProject, PlanSection, PlanTemplate
from app.schemas.plan import PlanCreate, PlanUpdate, PlanResponse, EnterprisePlanSummary
from app.schemas.common import ApiResponse, PaginatedResponse, PaginatedData
from app.dependencies import get_current_user

router = APIRouter(prefix="/plans", tags=["Plans"])

PLAN_TYPE_CODE = {"comprehensive": "ZH", "special": "ZX", "onsite": "XC"}


def _generate_plan_number(enterprise_name: str, plan_type: str, seq: int) -> str:
    """生成预案编号：{企业前缀}-{类型码}-{三位序号}。"""
    prefix = (enterprise_name or "").replace(" ", "")[:4] or "企业"
    code = PLAN_TYPE_CODE.get(plan_type, "YA")
    return f"{prefix}-{code}-{seq:03d}"


def _build_plan(p: PlanProject, ent_name: str = "") -> PlanResponse:
    sections = p.sections or []
    return PlanResponse(
        id=p.id, enterprise_id=p.enterprise_id, enterprise_name=ent_name,
        style_preference=p.style_preference, advanced_prompt_overrides=p.advanced_prompt_overrides,
        plan_type=p.plan_type, title=p.title, accident_type=p.accident_type,
        status=p.status, current_version=p.current_version,
        sections_count=len(sections),
        completed_sections=sum(1 for s in sections if s.content and s.content.strip()),
        plan_number=p.plan_number,
        version_number=p.version_number,
        created_at=p.created_at.isoformat() if p.created_at else "",
        updated_at=p.updated_at.isoformat() if p.updated_at else "",
    )

def _create_sections_from_template(db, plan_id: str, structure: list, counter: list | None = None):
    """Recursively create PlanSection rows from template structure"""
    if counter is None:
        counter = [0]
    for item in structure:
        key = item.get("key", f"auto_{uuid4().hex[:8]}")
        title = item.get("title", "")
        level = item.get("level", 1)
        sort_order = counter[0]
        counter[0] += 1
        section = PlanSection(
            id=str(uuid4()),
            plan_project_id=plan_id,
            section_key=key,
            title=title,
            level=level,
            sort_order=sort_order,
            content=None,
            ai_generated=False,
            ai_generatable=item.get("ai_generatable", True),
            auto_fill=item.get("auto_fill", False),
            auto_fill_source=item.get("auto_fill_source"),
            data_dependencies=item.get("data_dependencies", []),
        )
        db.add(section)
        subsections = item.get("subsections", [])
        if subsections:
            _create_sections_from_template(db, plan_id, subsections, counter)

@router.get("", response_model=PaginatedResponse[PlanResponse])
async def list_plans(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    enterprise_id: str = Query(""), plan_type: str = Query(""), status: str = Query(""),
    search: str = Query(""),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    query = select(PlanProject).where(PlanProject.user_id == current_user.id)
    if enterprise_id: query = query.where(PlanProject.enterprise_id == enterprise_id)
    if plan_type: query = query.where(PlanProject.plan_type == plan_type)
    if status: query = query.where(PlanProject.status == status)
    if search: query = query.where(PlanProject.title.ilike(f"%{search}%"))
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    offset = (page - 1) * page_size
    rows = (await db.execute(query.order_by(PlanProject.updated_at.desc()).offset(offset).limit(page_size))).scalars().all()
    items = []
    for p in rows:
        ent_result = await db.execute(select(Enterprise.name).where(Enterprise.id == p.enterprise_id))
        ent_name = ent_result.scalar_one_or_none() or ""
        items.append(_build_plan(p, ent_name))
    return PaginatedResponse(data=PaginatedData(items=items, total=total, page=page, page_size=page_size))


@router.get("/enterprise-summary", response_model=ApiResponse[list[EnterprisePlanSummary]])
async def enterprise_plan_summary(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """返回当前用户所有企业按预案类型的统计汇总"""
    # 子查询：每个企业的预案统计
    stmt = (
        select(
            Enterprise.id.label("enterprise_id"),
            Enterprise.name.label("enterprise_name"),
            Enterprise.industry.label("industry"),
            func.count(PlanProject.id).label("total"),
            func.count(case((PlanProject.plan_type == "comprehensive", 1))).label("comprehensive_count"),
            func.count(case((PlanProject.plan_type == "special", 1))).label("special_count"),
            func.count(case((PlanProject.plan_type == "onsite", 1))).label("onsite_count"),
            func.max(PlanProject.updated_at).label("last_updated"),
        )
        .select_from(Enterprise)
        .outerjoin(PlanProject, and_(
            PlanProject.enterprise_id == Enterprise.id,
            PlanProject.user_id == current_user.id,
        ))
        .where(Enterprise.user_id == current_user.id)
        .group_by(Enterprise.id, Enterprise.name, Enterprise.industry)
        .order_by(Enterprise.name)
    )
    result = await db.execute(stmt)
    rows = result.all()
    items = [
        EnterprisePlanSummary(
            enterprise_id=row.enterprise_id,
            enterprise_name=row.enterprise_name,
            industry=row.industry or "",
            total=row.total,
            comprehensive_count=row.comprehensive_count,
            special_count=row.special_count,
            onsite_count=row.onsite_count,
            last_updated=row.last_updated.isoformat() if row.last_updated else None,
        )
        for row in rows
    ]
    return ApiResponse(data=items)
@router.get("/{plan_id}", response_model=ApiResponse[PlanResponse])
async def get_plan(plan_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    result = await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))
    p = result.scalar_one_or_none()
    if not p: raise HTTPException(404, "预案不存在")
    ent_result = await db.execute(select(Enterprise.name).where(Enterprise.id == p.enterprise_id))
    ent_name = ent_result.scalar_one_or_none() or ""
    return ApiResponse(data=_build_plan(p, ent_name))

@router.post("", response_model=ApiResponse[PlanResponse], status_code=201)
async def create_plan(data: PlanCreate, current_user=Depends(get_current_user), db=Depends(get_db)):
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == data.enterprise_id, Enterprise.user_id == current_user.id))).scalar_one_or_none()
    if not ent: raise HTTPException(404, "企业不存在")
    plan_data = data.model_dump(exclude_none=True)

    # 预案编号为空时自动生成
    if not plan_data.get("plan_number"):
        existing_count = (
            await db.execute(
                select(func.count()).select_from(PlanProject).where(
                    PlanProject.enterprise_id == data.enterprise_id,
                    PlanProject.plan_type == data.plan_type,
                )
            )
        ).scalar() or 0
        plan_data["plan_number"] = _generate_plan_number(ent.name, data.plan_type, existing_count + 1)

    # 版本号为空时默认 A-{year}-{month}
    if not plan_data.get("version_number"):
        plan_data["version_number"] = f"A-{datetime.now().year}-{datetime.now().month:02d}"

    # 继承用户默认风格（前端未传时，从DB直接获取）
    if data.style_preference is None:
        user_row = (await db.execute(select(User).where(User.id == current_user.id))).scalar_one_or_none()
        if user_row and user_row.default_style_preference:
            plan_data["style_preference"] = user_row.default_style_preference
    p = PlanProject(user_id=current_user.id, **plan_data)
    db.add(p)
    await db.flush()

    # Initialize sections from active template
    tpl_result = await db.execute(
        select(PlanTemplate)
        .where(PlanTemplate.plan_type == data.plan_type, PlanTemplate.is_active == True)
        .order_by(PlanTemplate.version.desc())
        .limit(1)
    )
    template = tpl_result.scalar_one_or_none()
    if template and template.structure:
        _create_sections_from_template(db, p.id, template.structure)

    await db.commit()
    await db.refresh(p)
    return ApiResponse(data=_build_plan(p, ent.name))

@router.put("/{plan_id}", response_model=ApiResponse[PlanResponse])
async def update_plan(plan_id: str, data: PlanUpdate, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p: raise HTTPException(404, "预案不存在")
    if data.title is not None: p.title = data.title
    await db.commit(); await db.refresh(p)
    ent_result = await db.execute(select(Enterprise.name).where(Enterprise.id == p.enterprise_id))
    ent_name = ent_result.scalar_one_or_none() or ""
    return ApiResponse(data=_build_plan(p, ent_name))

@router.delete("/{plan_id}")
async def delete_plan(plan_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p: raise HTTPException(404, "预案不存在")
    await db.delete(p); await db.commit()
    return {"code": 0, "message": "已删除"}

@router.post("/{plan_id}/duplicate", response_model=ApiResponse[PlanResponse])
async def duplicate_plan(plan_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p: raise HTTPException(404, "预案不存在")

    # 自动生成编号与版本号，避免副本导出时因缺失报 400
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()
    existing_count = (
        await db.execute(
            select(func.count()).select_from(PlanProject).where(
                PlanProject.enterprise_id == p.enterprise_id,
                PlanProject.plan_type == p.plan_type,
            )
        )
    ).scalar() or 0
    plan_number = _generate_plan_number(ent.name if ent else "", p.plan_type, existing_count + 1)
    version_number = p.version_number or f"A-{datetime.now().year}-{datetime.now().month:02d}"

    dup = PlanProject(
        user_id=current_user.id, enterprise_id=p.enterprise_id, plan_type=p.plan_type,
        title=f"{p.title} (副本)", accident_type=p.accident_type,
        plan_number=plan_number, version_number=version_number,
    )
    db.add(dup)
    await db.flush()
    for s in (p.sections or []):
        ns = PlanSection(
            plan_project_id=dup.id, section_key=s.section_key,
            title=s.title, level=s.level, sort_order=s.sort_order,
            content=s.content, ai_generated=s.ai_generated,
            ai_generatable=s.ai_generatable, auto_fill=s.auto_fill,
            auto_fill_source=s.auto_fill_source,
            data_dependencies=s.data_dependencies,
        )
        db.add(ns)
    await db.commit(); await db.refresh(dup)
    return ApiResponse(data=_build_plan(dup))
