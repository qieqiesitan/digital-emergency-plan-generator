from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.user import User
from app.models.enterprise import Enterprise, RiskSource, EmergencyResource
from app.schemas.risk_source import RiskSourceCreate, RiskSourceUpdate, RiskSourceResponse
from app.schemas.emergency_resource import EmergencyResourceCreate, EmergencyResourceUpdate, EmergencyResourceResponse
from app.schemas.enterprise import SurroundingInfo
from app.schemas.common import ApiResponse, PaginatedResponse, PaginatedData
from app.dependencies import get_current_user

router = APIRouter(prefix="/enterprises", tags=["Enterprise Sub"])

def _cats_to_str(categories: list[str] | None) -> str:
    """Convert categories list to comma-separated string for DB storage."""
    if not categories:
        return ""
    return ",".join(c for c in categories if c)

@router.get("/{enterprise_id}/org-structure")
async def get_org_structure(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    result = await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))
    e = result.scalar_one_or_none()
    if not e: raise HTTPException(404, "��ҵ������")
    return ApiResponse(data=e.org_structure or [])

@router.put("/{enterprise_id}/org-structure")
async def update_org_structure(enterprise_id: str, data: list = Body(...), current_user=Depends(get_current_user), db=Depends(get_db)):
    result = await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))
    e = result.scalar_one_or_none()
    if not e: raise HTTPException(404, "��ҵ������")
    e.org_structure = data; await db.commit()
    return ApiResponse(data=e.org_structure)

@router.get("/{enterprise_id}/surrounding")
async def get_surrounding(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    result = await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))
    e = result.scalar_one_or_none()
    if not e: raise HTTPException(404, "��ҵ������")
    return ApiResponse(data=e.surrounding_info or {"nearby_units": [], "sensitive_targets": [], "traffic_info": ""})

@router.put("/{enterprise_id}/surrounding")
async def update_surrounding(enterprise_id: str, data: SurroundingInfo, current_user=Depends(get_current_user), db=Depends(get_db)):
    result = await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))
    e = result.scalar_one_or_none()
    if not e: raise HTTPException(404, "��ҵ������")
    e.surrounding_info = data.model_dump(); await db.commit()
    return ApiResponse(data=e.surrounding_info)

@router.get("/{enterprise_id}/risk-sources", response_model=PaginatedResponse[RiskSourceResponse])
async def list_risk_sources(enterprise_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200), current_user=Depends(get_current_user), db=Depends(get_db)):
    result = await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))
    if not result.scalar_one_or_none(): raise HTTPException(404, "��ҵ������")
    q = select(RiskSource).where(RiskSource.enterprise_id == enterprise_id)
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    offset = (page - 1) * page_size
    rows = (await db.execute(q.order_by(RiskSource.sort_order).offset(offset).limit(page_size))).scalars().all()
    items = [RiskSourceResponse.model_validate(r) for r in rows]
    return PaginatedResponse(data=PaginatedData(items=items, total=total, page=page, page_size=page_size))

@router.get("/{enterprise_id}/risk-sources/{risk_id}", response_model=ApiResponse[RiskSourceResponse])
async def get_risk_source(enterprise_id: str, risk_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    r = (await db.execute(select(RiskSource).where(RiskSource.id == risk_id, RiskSource.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not r: raise HTTPException(404, "����Դ������")
    return ApiResponse(data=RiskSourceResponse.model_validate(r))

@router.post("/{enterprise_id}/risk-sources", response_model=ApiResponse[RiskSourceResponse], status_code=201)
async def create_risk_source(enterprise_id: str, data: RiskSourceCreate, current_user=Depends(get_current_user), db=Depends(get_db)):
    result = await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))
    if not result.scalar_one_or_none(): raise HTTPException(404, "��ҵ������")
    vals = data.model_dump(exclude_none=True)
    vals["categories"] = _cats_to_str(vals.get("categories"))
    r = RiskSource(enterprise_id=enterprise_id, **vals)
    db.add(r); await db.commit(); await db.refresh(r)
    return ApiResponse(data=RiskSourceResponse.model_validate(r))

@router.put("/{enterprise_id}/risk-sources/{risk_id}", response_model=ApiResponse[RiskSourceResponse])
async def update_risk_source(enterprise_id: str, risk_id: str, data: RiskSourceUpdate, current_user=Depends(get_current_user), db=Depends(get_db)):
    r = (await db.execute(select(RiskSource).where(RiskSource.id == risk_id, RiskSource.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not r: raise HTTPException(404, "����Դ������")
    for k, v in data.model_dump(exclude_none=True).items():
        if k == "categories":
            setattr(r, k, _cats_to_str(v))
        else:
            setattr(r, k, v)
    await db.commit(); await db.refresh(r)
    return ApiResponse(data=RiskSourceResponse.model_validate(r))

@router.delete("/{enterprise_id}/risk-sources/{risk_id}")
async def delete_risk_source(enterprise_id: str, risk_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    r = (await db.execute(select(RiskSource).where(RiskSource.id == risk_id, RiskSource.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not r: raise HTTPException(404, "����Դ������")
    await db.delete(r); await db.commit()
    return {"code": 0, "message": "��ɾ��"}

@router.get("/{enterprise_id}/resources", response_model=PaginatedResponse[EmergencyResourceResponse])
async def list_resources(enterprise_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200), current_user=Depends(get_current_user), db=Depends(get_db)):
    result = await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))
    if not result.scalar_one_or_none(): raise HTTPException(404, "��ҵ������")
    q = select(EmergencyResource).where(EmergencyResource.enterprise_id == enterprise_id)
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    offset = (page - 1) * page_size
    rows = (await db.execute(q.offset(offset).limit(page_size))).scalars().all()
    items = [EmergencyResourceResponse.model_validate(r) for r in rows]
    return PaginatedResponse(data=PaginatedData(items=items, total=total, page=page, page_size=page_size))

@router.get("/{enterprise_id}/resources/{resource_id}", response_model=ApiResponse[EmergencyResourceResponse])
async def get_resource(enterprise_id: str, resource_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    r = (await db.execute(select(EmergencyResource).where(EmergencyResource.id == resource_id, EmergencyResource.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not r: raise HTTPException(404, "Ӧ����Դ������")
    return ApiResponse(data=EmergencyResourceResponse.model_validate(r))

@router.post("/{enterprise_id}/resources", response_model=ApiResponse[EmergencyResourceResponse], status_code=201)
async def create_resource(enterprise_id: str, data: EmergencyResourceCreate, current_user=Depends(get_current_user), db=Depends(get_db)):
    result = await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))
    if not result.scalar_one_or_none(): raise HTTPException(404, "��ҵ������")
    r = EmergencyResource(enterprise_id=enterprise_id, **data.model_dump(exclude_none=True))
    db.add(r); await db.commit(); await db.refresh(r)
    return ApiResponse(data=EmergencyResourceResponse.model_validate(r))

@router.put("/{enterprise_id}/resources/{resource_id}", response_model=ApiResponse[EmergencyResourceResponse])
async def update_resource(enterprise_id: str, resource_id: str, data: EmergencyResourceUpdate, current_user=Depends(get_current_user), db=Depends(get_db)):
    r = (await db.execute(select(EmergencyResource).where(EmergencyResource.id == resource_id, EmergencyResource.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not r: raise HTTPException(404, "Ӧ����Դ������")
    for k, v in data.model_dump(exclude_none=True).items(): setattr(r, k, v)
    await db.commit(); await db.refresh(r)
    return ApiResponse(data=EmergencyResourceResponse.model_validate(r))

@router.delete("/{enterprise_id}/resources/{resource_id}")
async def delete_resource(enterprise_id: str, resource_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    r = (await db.execute(select(EmergencyResource).where(EmergencyResource.id == resource_id, EmergencyResource.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not r: raise HTTPException(404, "Ӧ����Դ������")
    await db.delete(r); await db.commit()
    return {"code": 0, "message": "��ɾ��"}
