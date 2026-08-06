from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.user import User
from app.models.enterprise import Enterprise
from app.schemas.enterprise import EnterpriseCreate, EnterpriseUpdate, EnterpriseResponse, AutofillRequest, AutofillResponse
from app.schemas.common import ApiResponse, PaginatedResponse, PaginatedData
from app.dependencies import get_current_user
from app.services.enterprise_cleanup_service import delete_enterprise_complete
from app.services.floor_plan_storage_service import remove_enterprise_uploads
from app.services.risk_stats_service import (
    count_enterprise_risk_events,
    count_enterprises_risk_events,
)

router = APIRouter(prefix="/enterprises", tags=["Enterprises"])

# ── Autofill ──

REASON_MESSAGES = {
    "rate_limited": "操作过于频繁，请稍后再试",
    "credits_exhausted": "今日免费额度已用完，请手动填写企业信息",
    "not_found": "未找到该企业信息，请检查企业名称是否正确",
    "network_error": "查询服务暂时不可用，请手动填写企业信息",
    "not_configured": "未配置企查查 API Key，请联系管理员",
}

@router.post("/autofill", response_model=ApiResponse[AutofillResponse])
async def autofill_enterprise(
    data: AutofillRequest,
    current_user: User = Depends(get_current_user),
):
    from app.services.enterprise_autofill import autofill as do_autofill
    result = await do_autofill(current_user.id, data.name)
    if result["ok"]:
        return ApiResponse(data=AutofillResponse(name=result["name"], fields=result["fields"]))
    reason = result.get("reason", "network_error")
    return ApiResponse(
        code=1,
        message=REASON_MESSAGES.get(reason, "查询失败"),
        data=AutofillResponse(error=reason),
    )

def _build_response(e: Enterprise, risk_events_count: int = 0) -> EnterpriseResponse:
    def _fmt_date(d):
        return d.strftime('%Y-%m-%d') if d else None
    return EnterpriseResponse(
        id=e.id, name=e.name, address=e.address, industry=e.industry,
        business_scope=e.business_scope, employee_count=e.employee_count,
        building_overview=e.building_overview, org_structure=e.org_structure or [],
        surrounding_info=e.surrounding_info,
        risk_method_config=e.risk_method_config or {},
        floor_plan_url=e.floor_plan_url,
        gis_lat=e.gis_lat,
        gis_lng=e.gis_lng,
        credit_code=e.credit_code,
        legal_representative=e.legal_representative,
        economic_type=e.economic_type,
        established_date=_fmt_date(e.established_date),
        registered_capital=e.registered_capital,
        phone=e.phone,
        fax=e.fax,
        postal_code=e.postal_code,
        land_area=e.land_area,
        building_area=e.building_area,
        safety_officer=e.safety_officer,
        safety_officer_phone=e.safety_officer_phone,
        safety_staff_count=e.safety_staff_count,
        safety_standardization=e.safety_standardization,
        fire_approval=e.fire_approval,
        fire_approval_date=_fmt_date(e.fire_approval_date),
        last_plan_filing_date=_fmt_date(e.last_plan_filing_date),
        last_plan_filing_authority=e.last_plan_filing_authority,
        main_products=e.main_products,
        annual_capacity=e.annual_capacity,
        hazardous_chemicals=e.hazardous_chemicals,
        special_equipment=e.special_equipment,
        risk_sources_count=len(e.risk_sources) if e.risk_sources else 0,
        risk_events_count=risk_events_count,
        resources_count=len(e.resources) if e.resources else 0,
        plans_count=len(e.plans) if e.plans else 0,
        created_at=e.created_at.isoformat() if e.created_at else "",
        updated_at=e.updated_at.isoformat() if e.updated_at else "",
    )

@router.get("", response_model=PaginatedResponse[EnterpriseResponse])
async def list_enterprises(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    search: str = Query(""), industry: str = Query(""),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    query = select(Enterprise).where(Enterprise.user_id == current_user.id)
    if search: query = query.where(Enterprise.name.ilike(f"%{search}%"))
    if industry: query = query.where(Enterprise.industry == industry)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    offset = (page - 1) * page_size
    rows = (await db.execute(query.order_by(Enterprise.created_at.desc()).offset(offset).limit(page_size))).scalars().all()
    event_counts = await count_enterprises_risk_events(db, [e.id for e in rows])
    items = [_build_response(e, event_counts.get(e.id, 0)) for e in rows]
    return PaginatedResponse(data=PaginatedData(items=items, total=total, page=page, page_size=page_size))

@router.get("/{enterprise_id}", response_model=ApiResponse[EnterpriseResponse])
async def get_enterprise(enterprise_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))
    e = result.scalar_one_or_none()
    if not e: raise HTTPException(status_code=404, detail="企业不存在")
    risk_events_count = await count_enterprise_risk_events(db, enterprise_id)
    return ApiResponse(data=_build_response(e, risk_events_count))

@router.post("", response_model=ApiResponse[EnterpriseResponse], status_code=201)
async def create_enterprise(data: EnterpriseCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    values = data.model_dump(exclude_none=True)
    date_fields = {"established_date", "fire_approval_date", "last_plan_filing_date"}
    for df in date_fields:
        if df in values and isinstance(values[df], str):
            s = values[df]
            parsed = None
            date_formats = ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"]
            for fmt in date_formats:
                try:
                    clean = s[:19].split(".")[0]
                    parsed = datetime.strptime(clean, fmt.split(".")[0])
                    break
                except ValueError:
                    continue
            if parsed is None and len(s) >= 10:
                try:
                    parsed = datetime.strptime(s[:10], "%Y-%m-%d")
                except ValueError:
                    pass
            if parsed is not None:
                values[df] = parsed
            else:
                del values[df]
    e = Enterprise(user_id=current_user.id, **values)
    db.add(e); await db.commit(); await db.refresh(e)
    return ApiResponse(data=_build_response(e))

@router.put("/{enterprise_id}", response_model=ApiResponse[EnterpriseResponse])
async def update_enterprise(enterprise_id: str, data: EnterpriseUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))
    e = result.scalar_one_or_none()
    if not e: raise HTTPException(status_code=404, detail="企业不存在")
    date_fields = {"established_date", "fire_approval_date", "last_plan_filing_date"}
    def _parse_date(s):
        if not isinstance(s, str):
            return s
        date_formats = ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"]
        for fmt in date_formats:
            try:
                clean = s[:19].split(".")[0]
                return datetime.strptime(clean, fmt.split(".")[0])
            except ValueError:
                continue
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            try:
                return datetime.strptime(s[:10], "%Y-%m-%d")
            except ValueError:
                pass
        return None
    for k, v in data.model_dump(exclude_none=True).items():
        if k in date_fields:
            v = _parse_date(v)
        if v is not None:
            setattr(e, k, v)
    await db.commit(); await db.refresh(e)
    return ApiResponse(data=_build_response(e))

@router.delete("/{enterprise_id}")
async def delete_enterprise(enterprise_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))
    e = result.scalar_one_or_none()
    if not e: raise HTTPException(status_code=404, detail="企业不存在")
    counts = await delete_enterprise_complete(db, enterprise_id)
    await db.commit()
    remove_enterprise_uploads(enterprise_id)
    return ApiResponse(data=counts, message="已删除")

