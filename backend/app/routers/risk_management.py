import json, os, logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.enterprise import Enterprise, EnterpriseFloor, RiskSource
from app.models.risk_management import RiskAssessmentMethod, RiskZone, RiskObject, RiskUnit, RiskEvent, RiskMeasure
from app.schemas.risk_management import (MethodCreate, MethodUpdate, MethodResponse, FloorCreate, FloorUpdate, FloorResponse, RiskZoneCreate, RiskZoneUpdate, RiskZoneResponse, RiskObjectCreate, RiskObjectUpdate, RiskObjectResponse, RiskUnitCreate, RiskUnitUpdate, RiskUnitResponse, RiskEventCreate, RiskEventUpdate, RiskEventResponse, RiskMeasureCreate, RiskMeasureUpdate, RiskMeasureResponse, HierarchyZoneResponse, MigrationPreviewItem, MigrationPreviewResponse, MigrationExecuteRequest, SmartGuideRequest, SmartGuideResponse, MethodPreviewRequest, MethodPreviewResponse)
from app.schemas.common import ApiResponse
from app.services.risk_method_engine import compute_risk, get_active_method_config
from app.services.risk_ai_service import _get_ai_config, suggest_objects, suggest_events, suggest_measures, smart_guide, analyze_floor_plan, migrate_preview
from app.services.risk_mapping_service import ensure_default_floor, validate_polygon_v2
from app.services.floor_plan_storage_service import save_floor_plan, remove_floor_plan
from app.config import settings
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/enterprises/{enterprise_id}/risk-management", tags=["Risk Management"])
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

async def _get_ent(eid: str, uid: str, db: AsyncSession):
    result = await db.execute(select(Enterprise).where(Enterprise.id == eid, Enterprise.user_id == uid))
    ent = result.scalar_one_or_none()
    if not ent: raise HTTPException(404, "企业不存在")
    return ent

def _validate_zone_polygon(polygon) -> None:
    if polygon is None:
        return
    data = polygon.model_dump() if hasattr(polygon, "model_dump") else polygon
    errors = validate_polygon_v2(data)
    if errors:
        raise HTTPException(status_code=422, detail={"code": "POLYGON_INVALID", "message": "；".join(errors)})

# ── Floors ──
async def _default_floor(db: AsyncSession, enterprise_id: str) -> EnterpriseFloor:
    """获取或创建默认楼层；并发首访依赖 enterprise_floors 唯一索引防重，冲突时回滚后回退查询。"""
    try:
        return await ensure_default_floor(db, enterprise_id)
    except IntegrityError:
        await db.rollback()
        return await ensure_default_floor(db, enterprise_id)

async def _floor_response(db: AsyncSession, floor: EnterpriseFloor) -> FloorResponse:
    zone_count = (await db.execute(select(func.count(RiskZone.id)).where(RiskZone.floor_id == floor.id))).scalar() or 0
    risk_point_count = (await db.execute(select(func.count(RiskObject.id)).where(RiskObject.floor_id == floor.id, RiskObject.is_risk_point.is_(True)))).scalar() or 0
    resp = FloorResponse.model_validate(floor)
    resp.zone_count = zone_count
    resp.risk_point_count = risk_point_count
    return resp

@router.get("/floors", response_model=ApiResponse[list[FloorResponse]])
async def list_floors(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    await _default_floor(db, enterprise_id)
    await db.commit()
    floors = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.enterprise_id == enterprise_id).order_by(EnterpriseFloor.sort_order))).scalars().all()
    return ApiResponse(data=[await _floor_response(db, f) for f in floors])

@router.post("/floors", response_model=ApiResponse[FloorResponse], status_code=201)
async def create_floor(body: FloorCreate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    exists = (await db.execute(select(EnterpriseFloor.id).where(EnterpriseFloor.enterprise_id == enterprise_id, EnterpriseFloor.name == body.name))).first()
    if exists:
        raise HTTPException(409, "楼层名称已存在")
    values = body.model_dump(exclude_unset=True)
    if not body.is_default:
        has_default = (await db.execute(select(func.count(EnterpriseFloor.id)).where(EnterpriseFloor.enterprise_id == enterprise_id, EnterpriseFloor.is_default.is_(True)))).scalar() or 0
        if has_default == 0:
            values["is_default"] = True
    if values.get("is_default"):
        await db.execute(update(EnterpriseFloor).where(EnterpriseFloor.enterprise_id == enterprise_id).values(is_default=False))
    floor = EnterpriseFloor(enterprise_id=enterprise_id, **values)
    db.add(floor)
    await db.commit()
    await db.refresh(floor)
    return ApiResponse(data=await _floor_response(db, floor))

@router.put("/floors/{floor_id}", response_model=ApiResponse[FloorResponse])
async def update_floor(floor_id: str, body: FloorUpdate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floor = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.id == floor_id, EnterpriseFloor.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not floor:
        raise HTTPException(404, "楼层不存在")
    if body.is_default is False and floor.is_default:
        default_count = (await db.execute(select(func.count(EnterpriseFloor.id)).where(EnterpriseFloor.enterprise_id == enterprise_id, EnterpriseFloor.is_default.is_(True)))).scalar() or 0
        if default_count <= 1:
            raise HTTPException(409, "企业必须保留一个默认楼层")
    if body.is_default:
        await db.execute(update(EnterpriseFloor).where(EnterpriseFloor.enterprise_id == enterprise_id).values(is_default=False))
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(floor, k, v)
    if floor.is_default and floor.floor_plan_url:
        ent = (await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))).scalar_one()
        ent.floor_plan_url = floor.floor_plan_url
    await db.commit()
    await db.refresh(floor)
    return ApiResponse(data=await _floor_response(db, floor))

@router.delete("/floors/{floor_id}")
async def delete_floor(floor_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floor = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.id == floor_id, EnterpriseFloor.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not floor:
        raise HTTPException(404, "楼层不存在")
    zone_count = (await db.execute(select(func.count(RiskZone.id)).where(RiskZone.floor_id == floor_id))).scalar() or 0
    object_count = (await db.execute(select(func.count(RiskObject.id)).where(RiskObject.floor_id == floor_id))).scalar() or 0
    if zone_count or object_count:
        raise HTTPException(409, "楼层存在分区或风险对象，不允许删除")
    if floor.is_default and (await db.execute(select(func.count(EnterpriseFloor.id)).where(EnterpriseFloor.enterprise_id == enterprise_id))).scalar() == 1:
        raise HTTPException(409, "唯一默认楼层不可删除")
    await db.delete(floor)
    await db.commit()
    return ApiResponse(message="已删除")

@router.post("/floors/{floor_id}/plan", response_model=ApiResponse[FloorResponse])
async def upload_floor_plan(floor_id: str, enterprise_id: str, file: UploadFile = File(...), current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floor = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.id == floor_id, EnterpriseFloor.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not floor:
        raise HTTPException(404, "楼层不存在")
    old_url = floor.floor_plan_url
    url, width, height = await save_floor_plan(enterprise_id, floor_id, file)
    floor.floor_plan_url = url
    floor.canvas_width = width
    floor.canvas_height = height
    if floor.is_default:
        ent = (await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))).scalar_one()
        ent.floor_plan_url = url
    await db.commit()
    remove_floor_plan(old_url)
    await db.refresh(floor)
    return ApiResponse(data=await _floor_response(db, floor))

# ── Methods ──
@router.get("/methods", response_model=ApiResponse[list[MethodResponse]])
async def list_methods(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    result = await db.execute(select(RiskAssessmentMethod).where((RiskAssessmentMethod.enterprise_id==enterprise_id)|(RiskAssessmentMethod.enterprise_id.is_(None))).where(RiskAssessmentMethod.is_active==True))
    return ApiResponse(data=[MethodResponse.model_validate(m) for m in result.scalars().all()])

@router.get("/methods/{method_id}", response_model=ApiResponse[MethodResponse])
async def get_method(method_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    m = (await db.execute(select(RiskAssessmentMethod).where(RiskAssessmentMethod.id==method_id))).scalar_one_or_none()
    if not m: raise HTTPException(404, "方法不存在")
    return ApiResponse(data=MethodResponse.model_validate(m))

@router.post("/methods", response_model=ApiResponse[MethodResponse], status_code=201)
async def create_method(body: MethodCreate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    m = RiskAssessmentMethod(enterprise_id=enterprise_id, method_type=body.method_type, name=body.name, description=body.description, config=body.config, is_system=False)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return ApiResponse(data=MethodResponse.model_validate(m))

@router.put("/methods/{method_id}", response_model=ApiResponse[MethodResponse])
async def update_method(method_id: str, body: MethodUpdate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    m = (await db.execute(select(RiskAssessmentMethod).where(RiskAssessmentMethod.id==method_id))).scalar_one_or_none()
    if not m: raise HTTPException(404, "方法不存在")
    if m.is_system: raise HTTPException(403, "系统方法不可直接编辑，请复制后再修改")
    for k, v in body.model_dump(exclude_unset=True).items(): setattr(m, k, v)
    await db.commit(); await db.refresh(m)
    return ApiResponse(data=MethodResponse.model_validate(m))

@router.delete("/methods/{method_id}")
async def delete_method(method_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    m = (await db.execute(select(RiskAssessmentMethod).where(RiskAssessmentMethod.id==method_id))).scalar_one_or_none()
    if not m: raise HTTPException(404, "方法不存在")
    if m.is_system: raise HTTPException(403, "系统方法不可删除")
    await db.delete(m)
    await db.commit()
    return ApiResponse(message="已删除")

@router.post("/methods/{method_id}/duplicate", response_model=ApiResponse[MethodResponse], status_code=201)
async def duplicate_method(method_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    src = (await db.execute(select(RiskAssessmentMethod).where(RiskAssessmentMethod.id==method_id))).scalar_one_or_none()
    if not src: raise HTTPException(404, "方法不存在")
    m = RiskAssessmentMethod(enterprise_id=enterprise_id, method_type=src.method_type, name=f"{src.name}（副本）", description=src.description, config=src.config, is_system=False)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return ApiResponse(data=MethodResponse.model_validate(m))

@router.post("/methods/preview", response_model=ApiResponse[MethodPreviewResponse])
async def preview_method(body: MethodPreviewRequest, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    m = (await db.execute(select(RiskAssessmentMethod).where(RiskAssessmentMethod.id==body.method_id))).scalar_one_or_none()
    if not m: raise HTTPException(404, "方法不存在")
    r = compute_risk(m.method_type, body.params, m.config)
    return ApiResponse(data=MethodPreviewResponse(risk_level=r.risk_level, risk_score=r.risk_score, action=r.action, deadline=r.deadline))

# ── Zones ──
@router.get("/zones", response_model=ApiResponse[list[RiskZoneResponse]])
async def list_zones(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    zones = (await db.execute(select(RiskZone).where(RiskZone.enterprise_id==enterprise_id).order_by(RiskZone.sort_order))).scalars().all()
    out = []; 
    for z in zones:
        cnt = (await db.execute(select(func.count(RiskObject.id)).where(RiskObject.zone_id==z.id))).scalar() or 0
        r = RiskZoneResponse.model_validate(z); r.object_count = cnt; out.append(r)
    return ApiResponse(data=out)

@router.post("/zones", response_model=ApiResponse[RiskZoneResponse], status_code=201)
async def create_zone(body: RiskZoneCreate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    _validate_zone_polygon(body.floor_plan_polygon)
    z = RiskZone(enterprise_id=enterprise_id, **body.model_dump(exclude_unset=True))
    db.add(z)
    await db.commit()
    await db.refresh(z)
    return ApiResponse(data=RiskZoneResponse.model_validate(z))

@router.put("/zones/{zone_id}", response_model=ApiResponse[RiskZoneResponse])
async def update_zone(zone_id: str, body: RiskZoneUpdate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    _validate_zone_polygon(body.floor_plan_polygon)
    z = (await db.execute(select(RiskZone).where(RiskZone.id==zone_id, RiskZone.enterprise_id==enterprise_id))).scalar_one_or_none()
    if not z: raise HTTPException(404, "分区不存在")
    for k, v in body.model_dump(exclude_unset=True).items(): setattr(z, k, v)
    await db.commit(); await db.refresh(z)
    return ApiResponse(data=RiskZoneResponse.model_validate(z))

@router.delete("/zones/{zone_id}")
async def delete_zone(zone_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    z = (await db.execute(select(RiskZone).where(RiskZone.id==zone_id, RiskZone.enterprise_id==enterprise_id))).scalar_one_or_none()
    if not z: raise HTTPException(404, "分区不存在")
    cnt = (await db.execute(select(func.count(RiskObject.id)).where(RiskObject.zone_id==zone_id))).scalar() or 0
    await db.delete(z)
    await db.commit()
    return ApiResponse(message=f"已删除分区及 {cnt} 个对象", data={"cascade_count": cnt})

# ── Objects ──
@router.get("/objects", response_model=ApiResponse[list[RiskObjectResponse]])
async def list_objects(enterprise_id: str, zone_id: str|None=None, is_risk_point: bool|None=None, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    q = select(RiskObject).where(RiskObject.enterprise_id==enterprise_id)
    if zone_id: q = q.where(RiskObject.zone_id==zone_id)
    if is_risk_point is not None: q = q.where(RiskObject.is_risk_point==is_risk_point)
    objs = (await db.execute(q.order_by(RiskObject.sort_order))).scalars().all()
    out = []
    for o in objs:
        cnt = (await db.execute(select(func.count(RiskUnit.id)).where(RiskUnit.object_id==o.id))).scalar() or 0
        r = RiskObjectResponse.model_validate(o); r.unit_count = cnt; out.append(r)
    return ApiResponse(data=out)

@router.post("/objects", response_model=ApiResponse[RiskObjectResponse], status_code=201)
async def create_object(body: RiskObjectCreate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    o = RiskObject(enterprise_id=enterprise_id, **body.model_dump(exclude_unset=True))
    db.add(o)
    await db.commit()
    await db.refresh(o)
    return ApiResponse(data=RiskObjectResponse.model_validate(o))

@router.put("/objects/{object_id}", response_model=ApiResponse[RiskObjectResponse])
async def update_object(object_id: str, body: RiskObjectUpdate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    o = (await db.execute(select(RiskObject).where(RiskObject.id==object_id, RiskObject.enterprise_id==enterprise_id))).scalar_one_or_none()
    if not o: raise HTTPException(404, "对象不存在")
    for k, v in body.model_dump(exclude_unset=True).items(): setattr(o, k, v)
    await db.commit(); await db.refresh(o)
    return ApiResponse(data=RiskObjectResponse.model_validate(o))

@router.delete("/objects/{object_id}")
async def delete_object(object_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    o = (await db.execute(select(RiskObject).where(RiskObject.id==object_id, RiskObject.enterprise_id==enterprise_id))).scalar_one_or_none()
    if not o: raise HTTPException(404, "对象不存在")
    await db.delete(o)
    await db.commit()
    return ApiResponse(message="已删除对象及其下级数据")

# ── Units ──
@router.get("/objects/{object_id}/units", response_model=ApiResponse[list[RiskUnitResponse]])
async def list_units(object_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    units = (await db.execute(select(RiskUnit).where(RiskUnit.object_id==object_id).order_by(RiskUnit.sort_order))).scalars().all()
    out = []
    for u in units:
        cnt = (await db.execute(select(func.count(RiskEvent.id)).where(RiskEvent.unit_id==u.id))).scalar() or 0
        r = RiskUnitResponse.model_validate(u); r.event_count = cnt; out.append(r)
    return ApiResponse(data=out)

@router.post("/objects/{object_id}/units", response_model=ApiResponse[RiskUnitResponse], status_code=201)
async def create_unit(object_id: str, body: RiskUnitCreate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    u = RiskUnit(object_id=object_id, **body.model_dump(exclude_unset=True))
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return ApiResponse(data=RiskUnitResponse.model_validate(u))

@router.put("/objects/{object_id}/units/{unit_id}", response_model=ApiResponse[RiskUnitResponse])
async def update_unit(object_id: str, unit_id: str, body: RiskUnitUpdate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    u = (await db.execute(select(RiskUnit).where(RiskUnit.id==unit_id, RiskUnit.object_id==object_id))).scalar_one_or_none()
    if not u: raise HTTPException(404, "单元不存在")
    for k, v in body.model_dump(exclude_unset=True).items(): setattr(u, k, v)
    await db.commit(); await db.refresh(u)
    return ApiResponse(data=RiskUnitResponse.model_validate(u))

@router.delete("/objects/{object_id}/units/{unit_id}")
async def delete_unit(object_id: str, unit_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    u = (await db.execute(select(RiskUnit).where(RiskUnit.id==unit_id, RiskUnit.object_id==object_id))).scalar_one_or_none()
    if not u: raise HTTPException(404, "单元不存在")
    await db.delete(u)
    await db.commit()
    return ApiResponse(message="已删除单元及其下级数据")

# ── Events (with auto-rating) ──
@router.post("/units/{unit_id}/events", response_model=ApiResponse[RiskEventResponse], status_code=201)
async def create_event(unit_id: str, body: RiskEventCreate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    u = (await db.execute(select(RiskUnit).where(RiskUnit.id==unit_id))).scalar_one_or_none()
    if not u: raise HTTPException(404, "单元不存在")
    config = await get_active_method_config(db, enterprise_id, body.method_type)
    rating = compute_risk(body.method_type, body.method_params, config)
    ev = RiskEvent(unit_id=unit_id, accident_type=body.accident_type, description=body.description or "", trigger_conditions=body.trigger_conditions or "", consequences=body.consequences or "", method_type=body.method_type, method_params=body.method_params, risk_level=rating.risk_level, risk_score=rating.risk_score)
    db.add(ev)
    await db.commit()
    await db.refresh(ev)
    return ApiResponse(data=RiskEventResponse.model_validate(ev))

@router.post("/objects/{object_id}/events", response_model=ApiResponse[RiskEventResponse], status_code=201)
async def create_object_event(object_id: str, body: RiskEventCreate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    obj = (await db.execute(select(RiskObject).where(RiskObject.id==object_id, RiskObject.enterprise_id==enterprise_id))).scalar_one_or_none()
    if not obj: raise HTTPException(404, "对象不存在")
    config = await get_active_method_config(db, enterprise_id, body.method_type)
    rating = compute_risk(body.method_type, body.method_params, config)
    ev = RiskEvent(object_id=object_id, accident_type=body.accident_type, description=body.description or "", trigger_conditions=body.trigger_conditions or "", consequences=body.consequences or "", method_type=body.method_type, method_params=body.method_params, risk_level=rating.risk_level, risk_score=rating.risk_score)
    db.add(ev)
    await db.commit()
    await db.refresh(ev)
    return ApiResponse(data=RiskEventResponse.model_validate(ev))

@router.put("/events/{event_id}", response_model=ApiResponse[RiskEventResponse])
async def update_event(event_id: str, body: RiskEventUpdate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    ev = (await db.execute(select(RiskEvent).where(RiskEvent.id==event_id))).scalar_one_or_none()
    if not ev: raise HTTPException(404, "事件不存在")
    for k, v in body.model_dump(exclude_unset=True).items(): setattr(ev, k, v)
    if body.method_type or body.method_params:
        config = await get_active_method_config(db, enterprise_id, ev.method_type)
        rating = compute_risk(ev.method_type, ev.method_params, config)
        ev.risk_level = rating.risk_level; ev.risk_score = rating.risk_score
    await db.commit(); await db.refresh(ev)
    return ApiResponse(data=RiskEventResponse.model_validate(ev))

@router.delete("/events/{event_id}")
async def delete_event(event_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    ev = (await db.execute(select(RiskEvent).where(RiskEvent.id==event_id))).scalar_one_or_none()
    if not ev: raise HTTPException(404, "事件不存在")
    await db.delete(ev)
    await db.commit()
    return ApiResponse(message="已删除事件及其下级数据")

@router.post("/events/{event_id}/recalc", response_model=ApiResponse[RiskEventResponse])
async def recalc_event(event_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    ev = (await db.execute(select(RiskEvent).where(RiskEvent.id==event_id))).scalar_one_or_none()
    if not ev: raise HTTPException(404, "事件不存在")
    config = await get_active_method_config(db, enterprise_id, ev.method_type)
    rating = compute_risk(ev.method_type, ev.method_params, config)
    ev.risk_level = rating.risk_level; ev.risk_score = rating.risk_score
    await db.commit(); await db.refresh(ev)
    return ApiResponse(data=RiskEventResponse.model_validate(ev))

# ── Measures ──
@router.get("/events/{event_id}/measures", response_model=ApiResponse[list[RiskMeasureResponse]])
async def list_measures(event_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    measures = (await db.execute(select(RiskMeasure).where(RiskMeasure.event_id==event_id).order_by(RiskMeasure.sort_order))).scalars().all()
    return ApiResponse(data=[RiskMeasureResponse.model_validate(m) for m in measures])

@router.post("/events/{event_id}/measures", response_model=ApiResponse[RiskMeasureResponse], status_code=201)
async def create_measure(event_id: str, body: RiskMeasureCreate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    m = RiskMeasure(event_id=event_id, **body.model_dump(exclude_unset=True))
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return ApiResponse(data=RiskMeasureResponse.model_validate(m))

@router.put("/events/{event_id}/measures/{measure_id}", response_model=ApiResponse[RiskMeasureResponse])
async def update_measure(event_id: str, measure_id: str, body: RiskMeasureUpdate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    m = (await db.execute(select(RiskMeasure).where(RiskMeasure.id==measure_id, RiskMeasure.event_id==event_id))).scalar_one_or_none()
    if not m: raise HTTPException(404, "措施不存在")
    for k, v in body.model_dump(exclude_unset=True).items(): setattr(m, k, v)
    await db.commit(); await db.refresh(m)
    return ApiResponse(data=RiskMeasureResponse.model_validate(m))

@router.delete("/events/{event_id}/measures/{measure_id}")
async def delete_measure(event_id: str, measure_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    m = (await db.execute(select(RiskMeasure).where(RiskMeasure.id==measure_id, RiskMeasure.event_id==event_id))).scalar_one_or_none()
    if not m: raise HTTPException(404, "措施不存在")
    await db.delete(m)
    await db.commit()
    return ApiResponse(message="已删除措施")

# ── Hierarchy ──
@router.get("/hierarchy", response_model=ApiResponse[list[HierarchyZoneResponse]])
async def get_hierarchy(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    zones = (await db.execute(select(RiskZone).where(RiskZone.enterprise_id==enterprise_id).options(selectinload(RiskZone.objects).selectinload(RiskObject.units).selectinload(RiskUnit.events).selectinload(RiskEvent.measures), selectinload(RiskZone.objects).selectinload(RiskObject.events).selectinload(RiskEvent.measures)).order_by(RiskZone.sort_order))).scalars().all()
    return ApiResponse(data=[HierarchyZoneResponse.model_validate(z) for z in zones])

# ── AI endpoints ──
@router.post("/ai/suggest-objects")
async def ai_suggest_objects(body: dict, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    ai_config = await _get_ai_config(current_user.id, db)
    result = await suggest_objects(body.get("zone_name",""), body.get("zone_desc",""), body.get("enterprise_info",{}), ai_config, body.get("existing_names",[]))
    return ApiResponse(data=result)

@router.post("/ai/suggest-events")
async def ai_suggest_events(body: dict, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    ai_config = await _get_ai_config(current_user.id, db)
    result = await suggest_events(body.get("unit_name",""), body.get("unit_type",""), body.get("object_name",""), body.get("zone_name",""), body.get("enterprise_info",{}), ai_config)
    return ApiResponse(data=result)

@router.post("/ai/suggest-measures")
async def ai_suggest_measures(body: dict, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    ai_config = await _get_ai_config(current_user.id, db)
    result = await suggest_measures(body.get("accident_type",""), body.get("risk_level",""), body.get("unit_name",""), body.get("object_name",""), body.get("enterprise_info",{}), ai_config)
    return ApiResponse(data=result)

@router.post("/ai/smart-guide", response_model=ApiResponse[SmartGuideResponse])
async def ai_smart_guide(body: SmartGuideRequest, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    ai_config = await _get_ai_config(current_user.id, db)
    ent = await _get_ent(enterprise_id, current_user.id, db)
    info = {"name":ent.name,"industry":ent.industry,"business_scope":ent.business_scope,"building_overview":ent.building_overview,"hazardous_chemicals":ent.hazardous_chemicals,"special_equipment":ent.special_equipment}
    result = await smart_guide(body.description, info, ai_config)
    return ApiResponse(data=SmartGuideResponse(hierarchy=result.get("zones",[]), summary=result.get("summary",{})))

@router.post("/ai/analyze-floor-plan")
async def ai_analyze_floor_plan(body: dict, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    ai_config = await _get_ai_config(current_user.id, db)
    result = await analyze_floor_plan(body.get("enterprise_info",{}), ai_config)
    return ApiResponse(data=result)

@router.post("/ai/migrate-preview")
async def ai_migrate_preview(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    ai_config = await _get_ai_config(current_user.id, db)
    old = (await db.execute(select(RiskSource).where(RiskSource.enterprise_id==enterprise_id, RiskSource.migrated==False))).scalars().all()
    if not old: return ApiResponse(data=[])
    sources = [{"id":s.id,"name":s.name,"categories":s.categories,"location":s.location,"risk_level":s.risk_level,"description":s.description} for s in old]
    result = await migrate_preview(sources, ai_config)
    return ApiResponse(data=result)

# ── Migration ──
@router.get("/migrate/preview", response_model=ApiResponse[MigrationPreviewResponse])
async def get_migration_preview(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    old = (await db.execute(select(RiskSource).where(RiskSource.enterprise_id==enterprise_id, RiskSource.migrated==False))).scalars().all()
    return ApiResponse(data=MigrationPreviewResponse(items=[MigrationPreviewItem(source_id=s.id, source_name=s.name) for s in old], total=len(old)))

@router.post("/migrate/execute")
async def execute_migration(body: MigrationExecuteRequest, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    for mp in body.mappings:
        sid = mp.get("source_id")
        src = (await db.execute(select(RiskSource).where(RiskSource.id==sid))).scalar_one_or_none()
        if not src: continue
        zn = mp.get("zone_name","未命名分区")
        on = mp.get("object_name", src.name)
        zone = (await db.execute(select(RiskZone).where(RiskZone.enterprise_id==enterprise_id, RiskZone.name==zn))).scalar_one_or_none()
        if not zone:
            zone = RiskZone(enterprise_id=enterprise_id, name=zn); db.add(zone); await db.flush()
        obj = RiskObject(enterprise_id=enterprise_id, zone_id=zone.id, name=on, category=src.categories, location=src.location, description=src.description or "")
        db.add(obj); await db.flush()
        params = mp.get("method_params",{})
        rating = compute_risk("LS", params if params else {"l":3,"s":3})
        ev = RiskEvent(object_id=obj.id, accident_type=mp.get("accident_type","火灾"), method_type="LS", method_params=params, risk_level=rating.risk_level, risk_score=rating.risk_score)
        db.add(ev); src.migrated = True
    await db.commit()
    return ApiResponse(message=f"已迁移 {len(body.mappings)} 条数据")
