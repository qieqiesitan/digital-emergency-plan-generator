"""重大危险源 API：单元、单元品种、计算、快照、常量查询、档案与依据。"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.major_hazard import (
    MajorHazardCalculation,
    MajorHazardRecord,
    MajorHazardUnit,
    MajorHazardUnitChemical,
)
from app.models.standard_constants import CriticalQuantity
from app.schemas.major_hazard import (
    CalculationOut,
    ComputeIn,
    CriticalQuantityOut,
    EvidenceIn,
    RecordIn,
    RecordOut,
    UnitChemicalIn,
    UnitChemicalOut,
    UnitIn,
    UnitOut,
)
from app.services.evidence_service import EvidenceInput, attach_evidence, list_evidence
from app.services.major_hazard_lookup import lookup_chemical_definition
from app.services.major_hazard_linkage import (
    LinkageError,
    link_risk_object,
    link_unit_chemical_to_ledger,
    list_linkable_risk_objects,
    suggest_design_max_from_ledger,
)
from app.services.major_hazard_service import (
    MajorHazardRuleError,
    compute_unit_snapshot,
    preview_unit_calculation,
)
from app.services.major_hazard_report_data import ReportNotReadyError, build_chapters
from app.services.report_docx import generate_report_docx
from app.services.access_control import ensure_enterprise_owned, ensure_major_hazard_unit_owned
from app.services.filename_safety import safe_filename

logger = logging.getLogger("major_hazard")

router = APIRouter(prefix="/major-hazard", tags=["MajorHazard"], dependencies=[Depends(get_current_user)])

STANDARD = "GB18218-2018"


def _ok(data):
    return {"success": True, "code": 200, "message": "success", "data": data}


@router.get("/definitions/critical-quantities")
async def list_critical_quantities(
    keyword: Optional[str] = Query(default=None),
    limit: int = Query(default=30, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """按名称/别名/CAS 检索 GB 18218 表1/表2 的临界量，供前端选物质。"""
    stmt = select(CriticalQuantity).where(CriticalQuantity.standard == STANDARD)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                CriticalQuantity.chemical_name.ilike(like),
                CriticalQuantity.alias.ilike(like),
                CriticalQuantity.cas_no.ilike(like),
            )
        )
    stmt = stmt.order_by(CriticalQuantity.table_no, CriticalQuantity.chemical_name).limit(limit)
    res = await db.execute(stmt)
    rows = res.scalars().all()
    return _ok([CriticalQuantityOut.model_validate(r) for r in rows])


@router.get("/units")
async def list_units(
    enterprise_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    await ensure_enterprise_owned(db, user, enterprise_id)
    res = await db.execute(
        select(MajorHazardUnit)
        .where(MajorHazardUnit.enterprise_id == enterprise_id)
        .order_by(MajorHazardUnit.sort_order, MajorHazardUnit.created_at)
    )
    return _ok([UnitOut.model_validate(u) for u in res.scalars().all()])


@router.post("/units")
async def create_unit(
    enterprise_id: str = Query(...),
    payload: UnitIn = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    if payload is None:
        raise HTTPException(422, "请求体不能为空")
    await ensure_enterprise_owned(db, user, enterprise_id)
    unit = MajorHazardUnit(enterprise_id=enterprise_id, **payload.model_dump())
    db.add(unit)
    await db.commit()
    await db.refresh(unit)
    return _ok(UnitOut.model_validate(unit))


@router.put("/units/{unit_id}")
async def update_unit(
    unit_id: str,
    payload: UnitIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    unit = await ensure_major_hazard_unit_owned(db, user, unit_id)
    # exclude_unset：前端只提交表单里的 6 个字段，未传的（风险点关联、楼层、平面图落点）
    # 一律不许动；显式传 null 仍可清空。与 enterprises.py 的编辑接口同一约定。
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(unit, key, value)
    await db.commit()
    return _ok(UnitOut.model_validate(unit))


@router.delete("/units/{unit_id}")
async def delete_unit(
    unit_id: str, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)
):
    unit = await ensure_major_hazard_unit_owned(db, user, unit_id)
    await db.delete(unit)
    await db.commit()
    return _ok({"id": unit_id})


@router.get("/units/{unit_id}/chemicals")
async def list_unit_chemicals(
    unit_id: str, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)
):
    await ensure_major_hazard_unit_owned(db, user, unit_id)
    res = await db.execute(
        select(MajorHazardUnitChemical).where(MajorHazardUnitChemical.unit_id == unit_id)
    )
    return _ok([UnitChemicalOut.model_validate(c) for c in res.scalars().all()])


@router.put("/units/{unit_id}/chemicals")
async def replace_unit_chemicals(
    unit_id: str,
    payload: list[UnitChemicalIn],
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """整体替换单元内品种清单（前端一次提交整个表格）。"""
    await ensure_major_hazard_unit_owned(db, user, unit_id)
    existing = await db.execute(
        select(MajorHazardUnitChemical).where(MajorHazardUnitChemical.unit_id == unit_id)
    )
    for row in existing.scalars().all():
        await db.delete(row)
    for item in payload:
        db.add(MajorHazardUnitChemical(unit_id=unit_id, **item.model_dump()))
    await db.commit()
    return _ok({"unit_id": unit_id, "count": len(payload)})


@router.post("/units/{unit_id}/compute")
async def compute_unit(
    unit_id: str,
    payload: ComputeIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """执行一次 R 值法计算并写入不可变快照。"""
    try:
        await ensure_major_hazard_unit_owned(db, user, unit_id)
        snapshot = await compute_unit_snapshot(
            db,
            unit_id=unit_id,
            exposed_population=payload.exposed_population,
            user_id=getattr(user, "id", None),
        )
    except MajorHazardRuleError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _ok(snapshot)


@router.post("/units/{unit_id}/preview")
async def preview_unit(
    unit_id: str,
    payload: ComputeIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """实时预览：只计算不写快照。前端在输入变化（防抖）时调用。

    与 /compute 的区别只有一个：不写 major_hazard_calculations。
    快照是审计凭证，必须由用户显式点「固化」才产生。
    """
    try:
        await ensure_major_hazard_unit_owned(db, user, unit_id)
        snapshot = await preview_unit_calculation(
            db, unit_id=unit_id, exposed_population=payload.exposed_population
        )
    except MajorHazardRuleError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _ok(snapshot)


@router.get("/units/{unit_id}/calculations")
async def list_calculations(
    unit_id: str, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)
):
    await ensure_major_hazard_unit_owned(db, user, unit_id)
    res = await db.execute(
        select(MajorHazardCalculation)
        .where(MajorHazardCalculation.unit_id == unit_id)
        .order_by(MajorHazardCalculation.seq.desc())
    )
    return _ok([CalculationOut.model_validate(c) for c in res.scalars().all()])


@router.get("/units/{unit_id}/evidence")
async def list_unit_evidence(
    unit_id: str, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)
):
    """查看该重大危险源单元挂载的法规依据。"""
    await ensure_major_hazard_unit_owned(db, user, unit_id)
    data = await list_evidence(db, owner_type="major_hazard_unit", owner_id=unit_id)
    return _ok(data)


@router.post("/units/{unit_id}/evidence")
async def attach_unit_evidence(
    unit_id: str,
    payload: list[EvidenceIn],
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    await ensure_major_hazard_unit_owned(db, user, unit_id)
    created = await attach_evidence(
        db,
        owner_type="major_hazard_unit",
        owner_id=unit_id,
        items=[EvidenceInput(**item.model_dump()) for item in payload],
        user_id=getattr(user, "id", None),
    )
    return _ok({"created": created})


@router.get("/units/{unit_id}/record")
async def get_unit_record(
    unit_id: str, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)
):
    await ensure_major_hazard_unit_owned(db, user, unit_id)
    res = await db.execute(select(MajorHazardRecord).where(MajorHazardRecord.unit_id == unit_id))
    record = res.scalar_one_or_none()
    if record is None:
        raise HTTPException(404, "该单元尚未建立档案")
    return _ok(RecordOut.model_validate(record))


@router.put("/units/{unit_id}/record")
async def upsert_unit_record(
    unit_id: str,
    payload: RecordIn,
    enterprise_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """档案不存在则创建，存在则按提供的字段局部更新。"""
    unit = await ensure_major_hazard_unit_owned(db, user, unit_id)
    if unit.enterprise_id != enterprise_id:
        raise HTTPException(404, "重大危险源单元不存在")

    res = await db.execute(select(MajorHazardRecord).where(MajorHazardRecord.unit_id == unit_id))
    record = res.scalar_one_or_none()
    if record is None:
        # attachments / completeness 的模型默认值在 flush 时才生效，
        # 构造期显式给空字典，避免本请求内序列化到 None。
        record = MajorHazardRecord(
            unit_id=unit_id,
            enterprise_id=enterprise_id,
            attachments={},
            completeness={},
        )
        db.add(record)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(record, key, value)
    await db.commit()
    await db.refresh(record)
    return _ok(RecordOut.model_validate(record))


@router.get("/definitions/lookup")
async def api_lookup_chemical(
    name: str = Query(..., min_length=1, description="危险化学品名称"),
    hazard_symbol: Optional[str] = Query(
        default=None, description="危险性类别符号（如 W5.1），用于按表4 反查 β"
    ),
    db: AsyncSession = Depends(get_db),
):
    """按品种名查临界量 Q 与校正系数 β。

    前端录入品种时用它自动带出 Q 与 β；β 查不到（表3 未命中）时返回
    `needs_hazard_symbol=true` 与表4 的类别清单，让用户选完再查一次。
    """
    return _ok(await lookup_chemical_definition(db, name=name, hazard_symbol=hazard_symbol))


# --- 跨模块关联（计划 7）---------------------------------------------------


class LinkRiskObjectIn(BaseModel):
    """传 null 表示解除关联。"""

    risk_object_id: Optional[str] = None


class LinkChemicalIn(BaseModel):
    """传 null 表示解除台账引用。"""

    chemical_id: Optional[str] = None


class UnitPolygonIn(BaseModel):
    """平面图落点。传 null 表示清空落点。"""

    floor_id: Optional[str] = None
    polygon: Optional[dict] = None


@router.put("/units/{unit_id}/polygon")
async def api_set_unit_polygon(
    unit_id: str,
    payload: UnitPolygonIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """设置单元在平面图上的落点。polygon 结构与 RiskZone.floor_plan_polygon 一致。

    floor_id 与 polygon 必须同时给或同时清空——只改一个会让单元落到错误的楼层上。
    """
    if (payload.floor_id is None) != (payload.polygon is None):
        raise HTTPException(422, "floor_id 与 polygon 必须同时提供或同时清空")
    await ensure_major_hazard_unit_owned(db, user, unit_id)

    res = await db.execute(select(MajorHazardUnit).where(MajorHazardUnit.id == unit_id))
    unit = res.scalar_one_or_none()
    if unit is None:
        raise HTTPException(404, "重大危险源单元不存在")

    unit.floor_id = payload.floor_id
    unit.polygon = payload.polygon
    await db.commit()
    return _ok({"unit_id": unit_id, "floor_id": payload.floor_id})


@router.get("/linkable/risk-objects")
async def api_list_linkable_risk_objects(
    enterprise_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """列出本企业可关联的风险点。"""
    await ensure_enterprise_owned(db, user, enterprise_id)
    return _ok(await list_linkable_risk_objects(db, enterprise_id=enterprise_id))


@router.put("/units/{unit_id}/risk-object")
async def api_link_risk_object(
    unit_id: str,
    payload: LinkRiskObjectIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """把单元关联到风险点（同企业校验）。"""
    await ensure_major_hazard_unit_owned(db, user, unit_id)
    try:
        out = await link_risk_object(
            db, unit_id=unit_id, risk_object_id=payload.risk_object_id
        )
    except LinkageError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _ok(out)


@router.get("/units/{unit_id}/report.docx")
async def export_unit_report(
    unit_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """导出《危险化学品重大危险源辨识报告》。没有计算快照时拒绝导出。

    报告含企业完整辨识数据，必须登录后才能导出（与同文件 compute/evidence 端点一致）。
    """
    unit = await ensure_major_hazard_unit_owned(db, user, unit_id)

    ent_res = await db.execute(select(Enterprise).where(Enterprise.id == unit.enterprise_id))
    enterprise = ent_res.scalar_one_or_none()
    enterprise_name = getattr(enterprise, "name", "") or "（未填写单位名称）"

    chem_res = await db.execute(
        select(MajorHazardUnitChemical).where(MajorHazardUnitChemical.unit_id == unit_id)
    )
    chemicals = list(chem_res.scalars().all())

    calc_res = await db.execute(
        select(MajorHazardCalculation)
        .where(MajorHazardCalculation.unit_id == unit_id)
        .order_by(MajorHazardCalculation.seq.desc())
        .limit(1)
    )
    latest = calc_res.scalar_one_or_none()
    snapshot = latest.inputs_snapshot if latest is not None else None

    rec_res = await db.execute(select(MajorHazardRecord).where(MajorHazardRecord.unit_id == unit_id))
    record = rec_res.scalar_one_or_none()

    evidences = await list_evidence(db, owner_type="major_hazard_unit", owner_id=unit_id)

    try:
        chapters = build_chapters(
            enterprise_name=enterprise_name,
            unit=unit,
            chemicals=chemicals,
            snapshot=snapshot,
            record=record,
            evidences=evidences,
        )
    except ReportNotReadyError as exc:
        raise HTTPException(422, str(exc)) from exc

    try:
        doc = generate_report_docx(
            company_name=enterprise_name,
            report_kind="major_hazard_identification",
            chapters=chapters,
            report_title="危险化学品重大危险源辨识报告",
        )
        os.makedirs(settings.EXPORT_DIR, exist_ok=True)
        safe_unit = safe_filename(unit.name, fallback="单元")
        filename = f"重大危险源辨识报告-{safe_unit}.docx"
        filepath = os.path.join(settings.EXPORT_DIR, filename)
        doc.save(filepath)
    except Exception as exc:  # pragma: no cover - 渲染失败路径
        logger.exception("重大危险源辨识报告生成失败 unit=%s", unit_id)
        raise HTTPException(500, "报告生成失败，请稍后重试") from exc

    return FileResponse(
        filepath,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/ledger/chemicals")
async def api_list_ledger_chemicals(
    enterprise_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """列出本企业危化品台账条目，供单元品种关联选择。"""
    await ensure_enterprise_owned(db, user, enterprise_id)
    from app.models.hazardous_chemicals import HazardousChemical

    res = await db.execute(
        select(HazardousChemical)
        .where(HazardousChemical.enterprise_id == enterprise_id)
        .order_by(HazardousChemical.name)
    )
    return _ok(
        [
            {
                "id": c.id,
                "name": c.name,
                "cas_no": c.cas_no,
                "max_storage": c.max_storage,
                "storage_amount": (
                    float(c.storage_amount)
                    if getattr(c, "storage_amount", None) is not None
                    else None
                ),
                "storage_unit": c.storage_unit,
            }
            for c in res.scalars().all()
        ]
    )


@router.get("/ledger/chemicals/{chemical_id}/suggest-design-max")
async def api_suggest_design_max(
    chemical_id: str,
    enterprise_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """返回设计最大量的**建议初值** + 口径提示。

    注意语义：本接口只给建议，不写库。真正落库要等用户在界面上确认后保存品种清单。
    因为设计最大量与台账最大储存量在标准里是两个口径，直接采用会算小导致漏判。
    """
    await ensure_enterprise_owned(db, user, enterprise_id)
    try:
        out = await suggest_design_max_from_ledger(
            db, chemical_id=chemical_id, enterprise_id=enterprise_id
        )
    except LinkageError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _ok(out)


@router.put("/unit-chemicals/{unit_chemical_id}/ledger-link")
async def api_link_unit_chemical(
    unit_chemical_id: str,
    payload: LinkChemicalIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """把单元品种行关联到危化品台账条目（只写引用，不改数量）。"""
    row = (await db.execute(
        select(MajorHazardUnitChemical).where(MajorHazardUnitChemical.id == unit_chemical_id)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "单元品种不存在")
    await ensure_major_hazard_unit_owned(db, user, row.unit_id)
    try:
        out = await link_unit_chemical_to_ledger(
            db, unit_chemical_id=unit_chemical_id, chemical_id=payload.chemical_id
        )
    except LinkageError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _ok(out)
