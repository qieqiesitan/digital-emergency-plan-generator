"""重大危险源 API：单元、单元品种、计算、快照、常量查询、档案与依据。"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
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
from app.services.major_hazard_service import (
    MajorHazardRuleError,
    compute_unit_snapshot,
    preview_unit_calculation,
)

router = APIRouter(prefix="/major-hazard", tags=["MajorHazard"])

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
):
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
):
    if payload is None:
        raise HTTPException(422, "请求体不能为空")
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
):
    res = await db.execute(select(MajorHazardUnit).where(MajorHazardUnit.id == unit_id))
    unit = res.scalar_one_or_none()
    if unit is None:
        raise HTTPException(404, "重大危险源单元不存在")
    for key, value in payload.model_dump().items():
        setattr(unit, key, value)
    await db.commit()
    return _ok(UnitOut.model_validate(unit))


@router.delete("/units/{unit_id}")
async def delete_unit(unit_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(MajorHazardUnit).where(MajorHazardUnit.id == unit_id))
    unit = res.scalar_one_or_none()
    if unit is None:
        raise HTTPException(404, "重大危险源单元不存在")
    await db.delete(unit)
    await db.commit()
    return _ok({"id": unit_id})


@router.get("/units/{unit_id}/chemicals")
async def list_unit_chemicals(unit_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(MajorHazardUnitChemical).where(MajorHazardUnitChemical.unit_id == unit_id)
    )
    return _ok([UnitChemicalOut.model_validate(c) for c in res.scalars().all()])


@router.put("/units/{unit_id}/chemicals")
async def replace_unit_chemicals(
    unit_id: str,
    payload: list[UnitChemicalIn],
    db: AsyncSession = Depends(get_db),
):
    """整体替换单元内品种清单（前端一次提交整个表格）。"""
    res = await db.execute(select(MajorHazardUnit).where(MajorHazardUnit.id == unit_id))
    if res.scalar_one_or_none() is None:
        raise HTTPException(404, "重大危险源单元不存在")
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
):
    """实时预览：只计算不写快照。前端在输入变化（防抖）时调用。

    与 /compute 的区别只有一个：不写 major_hazard_calculations。
    快照是审计凭证，必须由用户显式点「固化」才产生。
    """
    try:
        snapshot = await preview_unit_calculation(
            db, unit_id=unit_id, exposed_population=payload.exposed_population
        )
    except MajorHazardRuleError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _ok(snapshot)


@router.get("/units/{unit_id}/calculations")
async def list_calculations(unit_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(MajorHazardCalculation)
        .where(MajorHazardCalculation.unit_id == unit_id)
        .order_by(MajorHazardCalculation.seq.desc())
    )
    return _ok([CalculationOut.model_validate(c) for c in res.scalars().all()])


@router.get("/units/{unit_id}/evidence")
async def list_unit_evidence(unit_id: str, db: AsyncSession = Depends(get_db)):
    """查看该重大危险源单元挂载的法规依据。"""
    data = await list_evidence(db, owner_type="major_hazard_unit", owner_id=unit_id)
    return _ok(data)


@router.post("/units/{unit_id}/evidence")
async def attach_unit_evidence(
    unit_id: str,
    payload: list[EvidenceIn],
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    created = await attach_evidence(
        db,
        owner_type="major_hazard_unit",
        owner_id=unit_id,
        items=[EvidenceInput(**item.model_dump()) for item in payload],
        user_id=getattr(user, "id", None),
    )
    return _ok({"created": created})


@router.get("/units/{unit_id}/record")
async def get_unit_record(unit_id: str, db: AsyncSession = Depends(get_db)):
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
):
    """档案不存在则创建，存在则按提供的字段局部更新。"""
    unit_res = await db.execute(select(MajorHazardUnit).where(MajorHazardUnit.id == unit_id))
    if unit_res.scalar_one_or_none() is None:
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
