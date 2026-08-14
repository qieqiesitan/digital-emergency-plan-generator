import json, math, os, logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.enterprise import Enterprise, EnterpriseFloor, RiskSource
from app.models.risk_management import RiskAssessmentMethod, RiskZone, RiskObject, RiskUnit, RiskEvent, RiskMeasure
from app.models.hazardous_chemicals import HazardousChemical
from app.schemas.risk_management import (MethodCreate, MethodUpdate, MethodResponse, FloorCreate, FloorUpdate, FloorResponse, RiskZoneCreate, RiskZoneUpdate, RiskZoneResponse, RiskObjectCreate, RiskObjectUpdate, RiskObjectResponse, RiskUnitCreate, RiskUnitUpdate, RiskUnitResponse, RiskEventCreate, RiskEventUpdate, RiskEventResponse, RiskMeasureCreate, RiskMeasureUpdate, RiskMeasureResponse, HierarchyZoneResponse, RiskZoneFloorPlanPolygon, WorkbenchResponse, WorkbenchZone, BatchSaveRequest, BatchSaveResponse, OverviewResponse, MigrationPreviewResponse, MigrationExecuteRequest, MigrationExecuteResponse, SmartGuideRequest, SmartGuideResponse, MethodPreviewRequest, MethodPreviewResponse, FourColorAnalyzeResponse, FourColorCommitRequest, FourColorCommitResponse)
from app.schemas.common import ApiResponse
from app.services.risk_method_engine import compute_risk, get_active_method_config, validate_dual_level, COAL_LS_DEFAULT_THRESHOLDS
from app.services.risk_ai_service import _get_ai_config, suggest_objects, suggest_events, suggest_measures, smart_guide, analyze_floor_plan, migrate_preview
from app.services.risk_source_migration_service import (
    build_migration_preview,
    execute_migration as execute_risk_source_migration,
)
from app.services.risk_mapping_service import ensure_default_floor, validate_polygon_v2, normalize_polygon, effective_color, max_risk_level, cascade_counts, LEVEL_COLORS
from app.services.floor_plan_storage_service import save_floor_plan, remove_floor_plan, remove_floor_plan_dir, normalize_floor_plan_url, save_four_color_temp, promote_four_color_file, remove_four_color_temp_dir, four_color_temp_dir
from app.services.four_color_recognizer import recognize_from_bytes, build_output_image
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

def _resolve_current_level(body, config) -> tuple[str, str]:
    """显式 risk_level 优先；否则按 method_params 计算。返回 (level, score)。"""
    if body.risk_level:
        return body.risk_level, body.risk_score or "-"
    rating = compute_risk(body.method_type, body.method_params, config)
    return rating.risk_level, rating.risk_score

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

async def _resolve_zone_floor(db: AsyncSession, enterprise_id: str, floor_id: str | None) -> str:
    """分区 floor_id 缺省时解析企业默认楼层；显式传入时校验楼层属于该企业。"""
    if not floor_id:
        floor = await _default_floor(db, enterprise_id)
        return floor.id
    floor = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.id == floor_id, EnterpriseFloor.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not floor:
        raise HTTPException(404, "楼层不存在")
    return floor.id

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
    if "floor_plan_url" in values:
        values["floor_plan_url"] = normalize_floor_plan_url(values["floor_plan_url"])
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
        if k == "floor_plan_url":
            v = normalize_floor_plan_url(v)
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
    if floor.is_default:
        alternative = (await db.execute(
            select(EnterpriseFloor).where(
                EnterpriseFloor.enterprise_id == enterprise_id,
                EnterpriseFloor.id != floor_id,
            ).order_by(EnterpriseFloor.sort_order).limit(1)
        )).scalar_one_or_none()
        if not alternative:
            raise HTTPException(409, "企业至少保留一个默认楼层")
        alternative.is_default = True
        ent = (await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))).scalar_one()
        ent.floor_plan_url = alternative.floor_plan_url
    old_url = floor.floor_plan_url
    await db.delete(floor)
    await db.commit()
    remove_floor_plan(old_url)
    remove_floor_plan_dir(enterprise_id, floor_id)
    return ApiResponse(data=None, message="已删除")

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

@router.post("/floors/{floor_id}/four-color/analyze", response_model=ApiResponse[FourColorAnalyzeResponse])
async def analyze_four_color(floor_id: str, enterprise_id: str, file: UploadFile = File(...), current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floor = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.id == floor_id, EnterpriseFloor.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not floor:
        raise HTTPException(404, "楼层不存在")
    data = await file.read()
    try:
        result = recognize_from_bytes(data)
    except Exception:
        raise HTTPException(422, "图片解析失败，请检查图片格式")
    if not result.zones:
        raise HTTPException(422, detail={"code": "NO_ZONE_DETECTED", "message": "未识别到红/橙/黄/蓝色块，请检查图片"})
    if result.processed_image is None:
        raise HTTPException(422, "图片处理失败，请检查图片格式")
    png_bytes, canvas_width, canvas_height = build_output_image(result.processed_image, result.width, result.height)
    preview_url, token = save_four_color_temp(enterprise_id, floor_id, png_bytes, "image/png")
    return ApiResponse(data=FourColorAnalyzeResponse(
        preview_url=preview_url,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        zones=result.zones,
        warnings=result.warnings,
        excluded=result.excluded,
        texts=result.texts,
    ))

@router.post("/floors/{floor_id}/four-color/commit", response_model=ApiResponse[FourColorCommitResponse])
async def commit_four_color_import(body: FourColorCommitRequest, floor_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floor = (await db.execute(
        select(EnterpriseFloor).where(EnterpriseFloor.id == floor_id, EnterpriseFloor.enterprise_id == enterprise_id).with_for_update()
    )).scalar_one_or_none()
    if not floor:
        raise HTTPException(404, "楼层不存在")
    if four_color_temp_dir(enterprise_id, floor_id, body.file_token) is None:
        raise HTTPException(404, "导入会话不存在")
    if not body.replace_existing:
        zone_count = (await db.execute(select(func.count(RiskZone.id)).where(RiskZone.floor_id == floor_id))).scalar() or 0
        unbound_point_count = (await db.execute(select(func.count(RiskObject.id)).where(RiskObject.floor_id == floor_id, RiskObject.zone_id.is_(None)))).scalar() or 0
        if zone_count or unbound_point_count or floor.canvas_texts:
            raise HTTPException(422, detail={"code": "FLOOR_NOT_EMPTY", "message": "楼层已有分区、风险点或文字标注，请确认替换后重试"})
    for zone in body.zones:
        polygon_v2 = {
            "version": 2,
            "color_source": "manual",
            "color": LEVEL_COLORS[zone.risk_level],
            "polygons": [
                {"id": f"poly-{i}", "label": zone.name, "points": [p.model_dump() for p in poly.points]}
                for i, poly in enumerate(zone.polygons)
            ],
        }
        errors = validate_polygon_v2(polygon_v2)
        if errors:
            raise HTTPException(422, f"分区「{zone.name}」多边形校验失败：{'；'.join(errors)}")
    try:
        new_url, width, height = promote_four_color_file(enterprise_id, floor_id, body.file_token)
    except FileNotFoundError:
        raise HTTPException(404, "导入会话不存在")
    old_url = floor.floor_plan_url
    if body.replace_existing:
        old_zones = (await db.execute(select(RiskZone).where(RiskZone.floor_id == floor_id))).scalars().all()
        for z in old_zones:
            await db.delete(z)
        await db.execute(delete(RiskObject).where(RiskObject.floor_id == floor_id, RiskObject.zone_id.is_(None)))
        floor.canvas_texts = []
    floor.floor_plan_url = new_url
    floor.canvas_width = width
    floor.canvas_height = height
    if floor.is_default:
        ent = (await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))).scalar_one()
        ent.floor_plan_url = new_url
    for i, zone in enumerate(body.zones):
        new_zone = RiskZone(
            enterprise_id=enterprise_id,
            floor_id=floor_id,
            name=zone.name,
            description=None,
            sort_order=i,
            floor_plan_polygon={
                "version": 2,
                "color_source": "manual",
                "color": LEVEL_COLORS[zone.risk_level],
                "polygons": [
                    {"id": f"poly-{i}-{j}", "label": zone.name, "points": [p.model_dump() for p in poly.points]}
                    for j, poly in enumerate(zone.polygons)
                ],
            },
        )
        db.add(new_zone)
    await db.commit()
    remove_four_color_temp_dir(enterprise_id, floor_id, body.file_token)
    if body.replace_existing:
        remove_floor_plan(old_url)
    saved_zones = (await db.execute(select(RiskZone).where(RiskZone.floor_id == floor_id).order_by(RiskZone.sort_order))).scalars().all()
    await db.refresh(floor)
    zone_responses = []
    for z in saved_zones:
        r = RiskZoneResponse.model_validate(z)
        # 导入的分区暂无风险对象：max_risk_level 保持 None，颜色取手动色板
        r.effective_color = effective_color(r.floor_plan_polygon, None)
        zone_responses.append(r)
    return ApiResponse(data=FourColorCommitResponse(
        floor=await _floor_response(db, floor),
        zones=zone_responses,
    ))

@router.delete("/floors/{floor_id}/four-color/{file_token}")
async def cancel_four_color_import(file_token: str, floor_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floor = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.id == floor_id, EnterpriseFloor.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not floor:
        raise HTTPException(404, "楼层不存在")
    if four_color_temp_dir(enterprise_id, floor_id, file_token) is None:
        raise HTTPException(404, "导入会话不存在")
    remove_four_color_temp_dir(enterprise_id, floor_id, file_token)
    return ApiResponse(data=None, message="已清理临时文件")

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
    return ApiResponse(data=None, message="已删除")

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
    return ApiResponse(data=MethodPreviewResponse(risk_level=r.risk_level, risk_score=r.risk_score, action=r.action, deadline=r.deadline, scenario=body.scenario))

# ── Workbench ──
def _same_ts(a, b) -> bool:
    """比较两个时间戳的绝对时刻（自动归一化时区与 datetime/字符串类型）。"""
    if not a or not b:
        return not a and not b

    def parse(v):
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(timezone.utc)
    return parse(a) == parse(b)


def _validate_point_range(x, y) -> None:
    """风险点坐标必须是 0-100 范围内的有限数值，否则抛 422 POINT_OUT_OF_RANGE。"""
    for v in (x, y):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v) or not (0 <= v <= 100):
            raise HTTPException(422, detail={"code": "POINT_OUT_OF_RANGE", "message": "风险点坐标必须是 0-100 范围内的有限数值"})


def _to_workbench_zone(z: RiskZone, floor: EnterpriseFloor) -> WorkbenchZone:
    """将分区 ORM 对象规范化为工作台/总览响应，补齐楼层名、多边形 v2、风险等级与有效色。"""
    resp = RiskZoneResponse.model_validate(z)
    resp.floor_name = floor.name
    resp.max_risk_level = max_risk_level(z)
    normalized = normalize_polygon(z.floor_plan_polygon, z.name)
    resp.floor_plan_polygon = RiskZoneFloorPlanPolygon.model_validate(normalized) if normalized else None
    resp.effective_color = effective_color(resp.floor_plan_polygon, resp.max_risk_level)
    resp.object_count = len(z.objects or [])
    return WorkbenchZone(
        id=resp.id,
        enterprise_id=resp.enterprise_id,
        floor_id=resp.floor_id,
        floor_name=resp.floor_name,
        name=resp.name,
        description=resp.description,
        sort_order=resp.sort_order,
        floor_plan_polygon=resp.floor_plan_polygon,
        max_risk_level=resp.max_risk_level,
        effective_color=resp.effective_color,
        object_count=resp.object_count,
        created_at=resp.created_at,
        updated_at=resp.updated_at,
        objects=[RiskObjectResponse.model_validate(o) for o in (z.objects or [])],
    )


@router.get("/workbench", response_model=ApiResponse[WorkbenchResponse])
async def load_workbench(enterprise_id: str, floor_id: str | None = Query(None), current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floor = await _default_floor(db, enterprise_id)
    if not floor_id:
        floor_id = floor.id
    current = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.id == floor_id, EnterpriseFloor.enterprise_id == enterprise_id))).scalar_one_or_none()
    if not current:
        raise HTTPException(404, "楼层不存在")
    await db.commit()
    floors = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.enterprise_id == enterprise_id).order_by(EnterpriseFloor.sort_order))).scalars().all()
    zones = (await db.execute(
        select(RiskZone).where(RiskZone.enterprise_id == enterprise_id, RiskZone.floor_id == floor_id)
        .options(
            selectinload(RiskZone.objects).selectinload(RiskObject.events),
            selectinload(RiskZone.objects).selectinload(RiskObject.units).selectinload(RiskUnit.events),
        ).order_by(RiskZone.sort_order)
    )).scalars().all()
    # 风险点可能因历史数据 floor_id 为空：只要绑定在当前楼层分区上就一并加载
    zone_ids = select(RiskZone.id).where(RiskZone.floor_id == floor_id)
    risk_points = (await db.execute(
        select(RiskObject).where(
            RiskObject.enterprise_id == enterprise_id,
            RiskObject.is_risk_point.is_(True),
            or_(RiskObject.floor_id == floor_id, RiskObject.zone_id.in_(zone_ids)),
        )
    )).scalars().all()
    return ApiResponse(data=WorkbenchResponse(
        floors=[await _floor_response(db, f) for f in floors],
        current_floor_id=current.id,
        zones=[_to_workbench_zone(z, current) for z in zones],
        risk_points=[RiskObjectResponse.model_validate(o) for o in risk_points],
        texts=current.canvas_texts or [],
    ))


@router.post("/workbench/batch-save", response_model=ApiResponse[BatchSaveResponse])
async def batch_save_workbench(body: BatchSaveRequest, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floor = (await db.execute(
        select(EnterpriseFloor).where(EnterpriseFloor.id == body.floor_id, EnterpriseFloor.enterprise_id == enterprise_id).with_for_update()
    )).scalar_one_or_none()
    if not floor:
        raise HTTPException(404, detail={"code": "FLOOR_NOT_FOUND", "message": "楼层不存在"})
    if not _same_ts(floor.updated_at, body.floor_updated_at):
        raise HTTPException(409, detail={"code": "SAVE_CONFLICT", "message": "楼层数据已变更，请刷新"})

    client_ids = [z.client_id for z in body.zones if z.client_id] + [r.client_id for r in body.risk_points if r.client_id]
    if len(client_ids) != len(set(client_ids)):
        raise HTTPException(422, detail={"code": "INVALID_PAYLOAD", "message": "client_id 重复"})

    existing_zones = {z.id: z for z in (await db.execute(select(RiskZone).where(RiskZone.floor_id == floor.id).with_for_update())).scalars()}
    existing_points = {o.id: o for o in (await db.execute(select(RiskObject).where(RiskObject.floor_id == floor.id, RiskObject.is_risk_point.is_(True)).with_for_update())).scalars()}

    submitted_zone_ids = {item.zone_id for item in body.zones if item.zone_id}
    missing_zone_ids = set(existing_zones) - submitted_zone_ids - set(body.deleted_zone_ids)
    if missing_zone_ids:
        raise HTTPException(422, detail={"code": "ZONE_NOT_BOUND", "message": "当前楼层存在缺失分区", "data": {"missing_zone_ids": sorted(missing_zone_ids)}})

    created_zone_map: dict[str, str] = {}
    for item in body.zones:
        polygon_errors = validate_polygon_v2(item.floor_plan_polygon.model_dump())
        if polygon_errors:
            raise HTTPException(422, detail={"code": "POLYGON_INVALID", "message": "；".join(polygon_errors)})
        if item.zone_id:
            zone = existing_zones.get(item.zone_id)
            if not zone:
                raise HTTPException(404, detail={"code": "ZONE_NOT_FOUND", "message": "分区不存在"})
            if not _same_ts(zone.updated_at, item.updated_at):
                raise HTTPException(409, detail={"code": "SAVE_CONFLICT", "message": "分区已变更，请刷新"})
            zone.name = item.name or zone.name
            zone.description = item.description
            zone.sort_order = item.sort_order
            zone.floor_plan_polygon = item.floor_plan_polygon.model_dump()
        else:
            if not item.client_id:
                raise HTTPException(422, detail={"code": "INVALID_PAYLOAD", "message": "新建分区必须提供 client_id"})
            zone = RiskZone(
                enterprise_id=enterprise_id,
                floor_id=floor.id,
                name=item.name or "",
                description=item.description,
                sort_order=item.sort_order,
                floor_plan_polygon=item.floor_plan_polygon.model_dump(),
            )
            db.add(zone)
            await db.flush()
            created_zone_map[item.client_id] = zone.id

    created_risk_point_map: dict[str, str] = {}
    for item in body.risk_points:
        if item.zone_id and item.zone_client_id:
            raise HTTPException(422, detail={"code": "INVALID_PAYLOAD", "message": "zone_id 与 zone_client_id 不允许同时提供"})
        _validate_point_range(item.location_x, item.location_y)
        if item.zone_id:
            bound_zone = (await db.execute(
                select(RiskZone.id).where(
                    RiskZone.id == item.zone_id,
                    RiskZone.floor_id == floor.id,
                    RiskZone.enterprise_id == enterprise_id,
                )
            )).scalar_one_or_none()
            if not bound_zone:
                raise HTTPException(422, detail={"code": "ZONE_FLOOR_MISMATCH", "message": "风险点绑定的分区不属于当前楼层或当前企业"})
        target_zone_id = item.zone_id or created_zone_map.get(item.zone_client_id or "")
        if not target_zone_id:
            raise HTTPException(422, detail={"code": "ZONE_NOT_FOUND", "message": "风险点必须绑定分区"})
        if item.id:
            point = existing_points.get(item.id)
            if not point:
                raise HTTPException(404, detail={"code": "RISK_POINT_NOT_FOUND", "message": "风险点不存在"})
            if not _same_ts(point.updated_at, item.updated_at):
                raise HTTPException(409, detail={"code": "SAVE_CONFLICT", "message": "风险点已变更，请刷新"})
            point.zone_id = target_zone_id
            point.floor_id = floor.id
            point.location_x = item.location_x
            point.location_y = item.location_y
            point.name = item.name or point.name
            point.category = item.category
            point.description = item.description
        else:
            if not item.client_id:
                raise HTTPException(422, detail={"code": "INVALID_PAYLOAD", "message": "新建风险点必须提供 client_id"})
            point = RiskObject(
                enterprise_id=enterprise_id,
                zone_id=target_zone_id,
                floor_id=floor.id,
                name=item.name or "",
                category=item.category,
                description=item.description,
                location_x=item.location_x,
                location_y=item.location_y,
                is_risk_point=True,
            )
            db.add(point)
            await db.flush()
            created_risk_point_map[item.client_id] = point.id

    for pid in body.deleted_risk_point_ids:
        point = existing_points.get(pid)
        if point:
            await db.delete(point)

    for zid in body.deleted_zone_ids:
        zone = existing_zones.get(zid)
        if not zone:
            continue
        counts = await cascade_counts(db, zid)
        if counts["object_count"] and zid not in body.confirm_cascade_zone_ids:
            raise HTTPException(409, detail={"code": "CASCADE_CONFIRM_REQUIRED", "message": "删除分区需要确认", "data": counts})
        await db.delete(zone)

    floor.canvas_texts = [t.model_dump() for t in body.texts]
    await db.commit()

    saved_zones = (await db.execute(select(RiskZone).where(RiskZone.floor_id == floor.id).order_by(RiskZone.sort_order))).scalars().all()
    saved_points = (await db.execute(select(RiskObject).where(RiskObject.floor_id == floor.id, RiskObject.is_risk_point.is_(True)))).scalars().all()
    await db.refresh(floor)
    return ApiResponse(data=BatchSaveResponse(
        floor=await _floor_response(db, floor),
        zones=[RiskZoneResponse.model_validate(z) for z in saved_zones],
        risk_points=[RiskObjectResponse.model_validate(o) for o in saved_points],
        texts=floor.canvas_texts or [],
        created_zone_map=created_zone_map,
        created_risk_point_map=created_risk_point_map,
    ), message="保存成功")


@router.get("/overview", response_model=ApiResponse[OverviewResponse])
async def get_overview(enterprise_id: str, floor_id: str | None = Query(None), current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    default = await _default_floor(db, enterprise_id)
    if not floor_id:
        current = default
    else:
        current = (await db.execute(select(EnterpriseFloor).where(EnterpriseFloor.id == floor_id, EnterpriseFloor.enterprise_id == enterprise_id))).scalar_one_or_none()
        if not current:
            raise HTTPException(404, "楼层不存在")
    await db.commit()
    zones = (await db.execute(select(RiskZone).where(RiskZone.floor_id == current.id).options(selectinload(RiskZone.objects)))).scalars().all()
    zone_ids = select(RiskZone.id).where(RiskZone.floor_id == current.id)
    points = (await db.execute(select(RiskObject).where(
        RiskObject.is_risk_point.is_(True),
        or_(RiskObject.floor_id == current.id, RiskObject.zone_id.in_(zone_ids)),
    ))).scalars().all()
    return ApiResponse(data=OverviewResponse(
        floor=await _floor_response(db, current),
        zones=[_to_workbench_zone(z, current) for z in zones],
        risk_points=[RiskObjectResponse.model_validate(o) for o in points],
    ))

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
    values = body.model_dump(exclude_unset=True)
    values["floor_id"] = await _resolve_zone_floor(db, enterprise_id, values.get("floor_id"))
    z = RiskZone(enterprise_id=enterprise_id, **values)
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
    updates = body.model_dump(exclude_unset=True)
    new_floor_id = updates.get("floor_id")
    if new_floor_id is not None:
        new_floor_id = await _resolve_zone_floor(db, enterprise_id, new_floor_id)
        if new_floor_id != z.floor_id:
            await db.execute(update(RiskObject).where(RiskObject.zone_id == zone_id).values(floor_id=new_floor_id))
            z.floor_id = new_floor_id
    for k, v in updates.items():
        if k == "floor_id":
            continue
        setattr(z, k, v)
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
    floor_id = body.floor_id
    if body.zone_id:
        zone = (await db.execute(select(RiskZone).where(RiskZone.id == body.zone_id, RiskZone.enterprise_id == enterprise_id))).scalar_one_or_none()
        if not zone:
            raise HTTPException(404, "分区不存在")
        if floor_id and floor_id != zone.floor_id:
            raise HTTPException(422, detail={"code": "ZONE_FLOOR_MISMATCH", "message": "分区与风险点楼层不一致"})
        floor_id = zone.floor_id
    if body.is_risk_point and (not body.zone_id or body.location_x is None or body.location_y is None):
        raise HTTPException(422, detail={"code": "RISK_POINT_INVALID", "message": "风险点必须绑定分区和坐标"})
    o = RiskObject(enterprise_id=enterprise_id, floor_id=floor_id, **body.model_dump(exclude_unset=True, exclude={"floor_id"}))
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
    return ApiResponse(data=None, message="已删除对象及其下级数据")

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
    return ApiResponse(data=None, message="已删除单元及其下级数据")

# ── Events (with auto-rating) ──
@router.post("/units/{unit_id}/events", response_model=ApiResponse[RiskEventResponse], status_code=201)
async def create_event(unit_id: str, body: RiskEventCreate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    u = (await db.execute(select(RiskUnit).where(RiskUnit.id==unit_id))).scalar_one_or_none()
    if not u: raise HTTPException(404, "单元不存在")
    if body.chemical_id:
        chem = (await db.execute(select(HazardousChemical).where(
            HazardousChemical.id == body.chemical_id,
            HazardousChemical.enterprise_id == enterprise_id,
        ))).scalar_one_or_none()
        if not chem:
            raise HTTPException(404, "关联的危化品不存在或不属于该企业")
    config = await get_active_method_config(db, enterprise_id, body.method_type)
    current_level, current_score = _resolve_current_level(body, config)
    try:
        validate_dual_level(current_level, body.inherent_risk_level)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    ev = RiskEvent(unit_id=unit_id, accident_type=body.accident_type, description=body.description or "", trigger_conditions=body.trigger_conditions or "", consequences=body.consequences or "", method_type=body.method_type, method_params=body.method_params, chemical_id=body.chemical_id, risk_level=current_level, risk_score=current_score, inherent_risk_level=body.inherent_risk_level, inherent_risk_score=body.inherent_risk_score, control_level=body.control_level)
    db.add(ev)
    await db.commit()
    await db.refresh(ev)
    return ApiResponse(data=RiskEventResponse.model_validate(ev))

@router.post("/objects/{object_id}/events", response_model=ApiResponse[RiskEventResponse], status_code=201)
async def create_object_event(object_id: str, body: RiskEventCreate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    obj = (await db.execute(select(RiskObject).where(RiskObject.id==object_id, RiskObject.enterprise_id==enterprise_id))).scalar_one_or_none()
    if not obj: raise HTTPException(404, "对象不存在")
    if body.chemical_id:
        chem = (await db.execute(select(HazardousChemical).where(
            HazardousChemical.id == body.chemical_id,
            HazardousChemical.enterprise_id == enterprise_id,
        ))).scalar_one_or_none()
        if not chem:
            raise HTTPException(404, "关联的危化品不存在或不属于该企业")
    config = await get_active_method_config(db, enterprise_id, body.method_type)
    current_level, current_score = _resolve_current_level(body, config)
    try:
        validate_dual_level(current_level, body.inherent_risk_level)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    ev = RiskEvent(object_id=object_id, accident_type=body.accident_type, description=body.description or "", trigger_conditions=body.trigger_conditions or "", consequences=body.consequences or "", method_type=body.method_type, method_params=body.method_params, chemical_id=body.chemical_id, risk_level=current_level, risk_score=current_score, inherent_risk_level=body.inherent_risk_level, inherent_risk_score=body.inherent_risk_score, control_level=body.control_level)
    db.add(ev)
    await db.commit()
    await db.refresh(ev)
    return ApiResponse(data=RiskEventResponse.model_validate(ev))

@router.put("/events/{event_id}", response_model=ApiResponse[RiskEventResponse])
async def update_event(event_id: str, body: RiskEventUpdate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    ev = (await db.execute(select(RiskEvent).where(RiskEvent.id==event_id))).scalar_one_or_none()
    if not ev: raise HTTPException(404, "事件不存在")
    if body.chemical_id:
        chem = (await db.execute(select(HazardousChemical).where(
            HazardousChemical.id == body.chemical_id,
            HazardousChemical.enterprise_id == enterprise_id,
        ))).scalar_one_or_none()
        if not chem:
            raise HTTPException(404, "关联的危化品不存在或不属于该企业")
    for k, v in body.model_dump(exclude_unset=True).items(): setattr(ev, k, v)
    # 重算守卫：仅当显式提供了 method_type/method_params（参数变更）才重算；
    # 两者都未提供（未改动保存）时不重算，避免空参数覆盖已存等级
    if body.risk_level is None and (body.method_type is not None or body.method_params is not None):
        config = await get_active_method_config(db, enterprise_id, ev.method_type)
        rating = compute_risk(ev.method_type, ev.method_params, config)
        ev.risk_level = rating.risk_level; ev.risk_score = rating.risk_score
    # 无条件校验双等级约束：仅改固有等级（不重算）时也要拦截
    try:
        validate_dual_level(ev.risk_level, ev.inherent_risk_level)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    await db.commit(); await db.refresh(ev)
    return ApiResponse(data=RiskEventResponse.model_validate(ev))

@router.delete("/events/{event_id}")
async def delete_event(event_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    ev = (await db.execute(select(RiskEvent).where(RiskEvent.id==event_id))).scalar_one_or_none()
    if not ev: raise HTTPException(404, "事件不存在")
    await db.delete(ev)
    await db.commit()
    return ApiResponse(data=None, message="已删除事件及其下级数据")

@router.post("/events/{event_id}/recalc", response_model=ApiResponse[RiskEventResponse])
async def recalc_event(event_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    ev = (await db.execute(select(RiskEvent).where(RiskEvent.id==event_id))).scalar_one_or_none()
    if not ev: raise HTTPException(404, "事件不存在")
    config = await get_active_method_config(db, enterprise_id, ev.method_type)
    rating = compute_risk(ev.method_type, ev.method_params, config)
    try:
        validate_dual_level(rating.risk_level, ev.inherent_risk_level)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    ev.risk_level = rating.risk_level; ev.risk_score = rating.risk_score
    await db.commit(); await db.refresh(ev)
    return ApiResponse(data=RiskEventResponse.model_validate(ev))

@router.get("/events/{event_id}/conversion-reference", response_model=ApiResponse[dict])
async def event_conversion_reference(enterprise_id: str, event_id: str,
                                     current_user=Depends(get_current_user), db=Depends(get_db)):
    """按固有分值 × 管控措施综合系数给出现有风险参考等级/分值（自动折算参考）。"""
    await _get_ent(enterprise_id, current_user.id, db)
    event = (await db.execute(select(RiskEvent).where(RiskEvent.id == event_id))).scalar_one_or_none()
    if not event:
        raise HTTPException(404, "风险事件不存在")
    # 归属校验：事件必须属于当前企业（事件经 object_id 或 unit_id 链归属对象，与创建路径一致）
    owned_object = None
    if event.object_id:
        owned_object = (await db.execute(select(RiskObject).where(RiskObject.id == event.object_id))).scalar_one_or_none()
    elif event.unit_id:
        unit = (await db.execute(select(RiskUnit).where(RiskUnit.id == event.unit_id))).scalar_one_or_none()
        if unit:
            owned_object = (await db.execute(select(RiskObject).where(RiskObject.id == unit.object_id))).scalar_one_or_none()
    if not owned_object or owned_object.enterprise_id != enterprise_id:
        raise HTTPException(404, "风险事件不存在")
    from app.services.data_dict_service import get_dict_map
    from app.services.risk_conversion_service import conversion_reference
    factors = await get_dict_map(db, enterprise_id, "measure_factors")
    factor_map: dict[str, float] = {}
    for code, entry in factors.items():
        if code == "mode":
            continue
        value = entry.get("value") if isinstance(entry, dict) else None
        factor = value.get("factor") if isinstance(value, dict) else None
        if isinstance(factor, (int, float)):
            factor_map[code] = float(factor)
    mode_entry = factors.get("mode")
    mode_value = mode_entry.get("value") if isinstance(mode_entry, dict) else None
    mode = mode_value.get("mode", "min") if isinstance(mode_value, dict) else "min"
    config = await get_active_method_config(db, enterprise_id, event.method_type)
    thresholds = (config or {}).get("risk_thresholds", [])
    if event.method_type == "COAL_LS" and not thresholds:
        thresholds = COAL_LS_DEFAULT_THRESHOLDS
    result = conversion_reference(event.inherent_risk_score or "", factor_map, mode, thresholds, event.method_type)
    return ApiResponse(data=result)

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
    return ApiResponse(data=None, message="已删除措施")

# ── Hierarchy ──
def sort_zones_by_floor(zones: list, floor_order: dict[str, int]) -> list:
    """按（楼层顺序，分区 sort_order）排序；未知/空楼层排最后。

    floor_order 由 enterprise_floors.sort_order 生成：{floor_id: index}。
    纯函数，便于单元测试。
    """
    fallback = len(floor_order)
    return sorted(zones, key=lambda z: (floor_order.get(z.floor_id, fallback), z.sort_order))


@router.get("/hierarchy", response_model=ApiResponse[list[HierarchyZoneResponse]])
async def get_hierarchy(enterprise_id: str, floor_id: str | None = Query(None), current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floors = (await db.execute(
        select(EnterpriseFloor).where(EnterpriseFloor.enterprise_id == enterprise_id).order_by(EnterpriseFloor.sort_order)
    )).scalars().all()
    floor_order = {f.id: i for i, f in enumerate(floors)}
    if floor_id:
        floor = next((f for f in floors if f.id == floor_id), None)
        if not floor:
            raise HTTPException(404, "楼层不存在")
        zones = (await db.execute(
            select(RiskZone).where(RiskZone.enterprise_id == enterprise_id, RiskZone.floor_id == floor_id)
            .options(
                selectinload(RiskZone.objects).selectinload(RiskObject.units).selectinload(RiskUnit.events).selectinload(RiskEvent.measures),
                selectinload(RiskZone.objects).selectinload(RiskObject.events).selectinload(RiskEvent.measures),
            )
            .order_by(RiskZone.sort_order)
        )).scalars().all()
    else:
        zones = (await db.execute(
            select(RiskZone).where(RiskZone.enterprise_id == enterprise_id)
            .options(
                selectinload(RiskZone.objects).selectinload(RiskObject.units).selectinload(RiskUnit.events).selectinload(RiskEvent.measures),
                selectinload(RiskZone.objects).selectinload(RiskObject.events).selectinload(RiskEvent.measures),
            )
        )).scalars().all()
        zones = sort_zones_by_floor(zones, floor_order)
    floors_by_id = {f.id: f for f in floors}
    out = []
    for z in zones:
        resp = HierarchyZoneResponse.model_validate(z)
        f = floors_by_id.get(z.floor_id)
        resp.floor_name = f.name if f else None
        normalized = normalize_polygon(z.floor_plan_polygon, z.name)
        resp.floor_plan_polygon = RiskZoneFloorPlanPolygon.model_validate(normalized) if normalized else None
        resp.max_risk_level = max_risk_level(z)
        resp.effective_color = effective_color(resp.floor_plan_polygon, resp.max_risk_level)
        out.append(resp)
    return ApiResponse(data=out)

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
    zone_rows = (await db.execute(select(RiskZone.name).where(RiskZone.enterprise_id == enterprise_id))).scalars().all()
    object_rows = (await db.execute(select(RiskObject.name).where(RiskObject.enterprise_id == enterprise_id))).scalars().all()
    existing_names = {"zones": list(zone_rows), "objects": list(object_rows)}
    result = await smart_guide(body.description, info, ai_config, existing_names=existing_names)
    return ApiResponse(data=SmartGuideResponse(hierarchy=result.get("zones",[]), summary=result.get("summary",{})))

@router.post("/ai/analyze-floor-plan")
async def ai_analyze_floor_plan(body: dict, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    ai_config = await _get_ai_config(current_user.id, db)
    result = await analyze_floor_plan(body.get("enterprise_info",{}), ai_config)
    return ApiResponse(data=result)

@router.post("/ai/migrate-preview", response_model=ApiResponse[MigrationPreviewResponse])
async def ai_migrate_preview(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    mappings: list[dict] = []
    try:
        ai_config = await _get_ai_config(current_user.id, db)
        old = (await db.execute(
            select(RiskSource).where(
                RiskSource.enterprise_id == enterprise_id,
                RiskSource.migrated.is_(False),
            )
        )).scalars().all()
        if old:
            sources = [{
                "id": s.id,
                "name": s.name,
                "categories": s.categories,
                "location": s.location,
                "risk_level": s.risk_level,
                "description": s.description,
            } for s in old]
            mappings = await migrate_preview(sources, ai_config)
    except HTTPException:
        mappings = []
    data = await build_migration_preview(db, enterprise_id, ai_mappings=mappings)
    return ApiResponse(data=MigrationPreviewResponse(**data))

# ── Migration ──
@router.get("/migrate/preview", response_model=ApiResponse[MigrationPreviewResponse])
async def get_migration_preview(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    data = await build_migration_preview(db, enterprise_id)
    return ApiResponse(data=MigrationPreviewResponse(**data))

@router.post("/migrate/execute", response_model=ApiResponse[MigrationExecuteResponse])
async def execute_migration(body: MigrationExecuteRequest, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    data = await execute_risk_source_migration(db, enterprise_id, body.mappings)
    return ApiResponse(
        data=MigrationExecuteResponse(**data),
        message=f"已迁移 {data['migrated']} 条数据",
    )
