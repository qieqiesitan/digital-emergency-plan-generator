from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.chemical_library import ChemicalLibrary
from app.models.enterprise import Enterprise
from app.models.hazardous_chemicals import HazardousChemical
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse
from app.schemas.chemical_library import (
    ChemicalLibraryCollectRequest,
    ChemicalLibraryCreate,
    ChemicalLibraryUpdate,
    ChemicalLibraryResponse,
)
from app.schemas.hazardous_chemicals import HazardousChemicalResponse

router = APIRouter(prefix="/chemical-library", tags=["Chemical Library"])

COLLECT_FIELDS = [
    "name", "cas_no", "un_no", "physical_state", "flash_point", "explosion_limit",
    "ignition_temp", "density", "boiling_point", "health_hazard", "fire_hazard",
    "leak_response", "storage_transport", "first_aid", "protective_measures",
]


def _serialize(item: ChemicalLibrary) -> ChemicalLibraryResponse:
    return ChemicalLibraryResponse.model_validate(item)


async def _find_conflict(
    db: AsyncSession, name: str, cas_no: str | None, exclude_id: str | None = None
) -> ChemicalLibrary | None:
    """查重：CAS 非空按 CAS 精确匹配；CAS 为空按 trim 后名称匹配。"""
    cas = (cas_no or "").strip() or None
    stmt = select(ChemicalLibrary)
    if cas:
        stmt = stmt.where(ChemicalLibrary.cas_no == cas)
    else:
        stmt = stmt.where(ChemicalLibrary.cas_no.is_(None), ChemicalLibrary.name == (name or "").strip())
    if exclude_id:
        stmt = stmt.where(ChemicalLibrary.id != exclude_id)
    return (await db.execute(stmt.limit(1))).scalar_one_or_none()


@router.get("", response_model=PaginatedResponse[ChemicalLibraryResponse])
async def list_library_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    keyword: str = Query(""),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(ChemicalLibrary)
    if keyword.strip():
        like = f"%{keyword.strip()}%"
        base = base.where(or_(
            ChemicalLibrary.name.ilike(like),
            ChemicalLibrary.cas_no.ilike(like),
            ChemicalLibrary.un_no.ilike(like),
        ))
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(
        base.order_by(ChemicalLibrary.name).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return PaginatedResponse(data=PaginatedData(
        items=[_serialize(r) for r in rows], total=total, page=page, page_size=page_size,
    ))


@router.post("", response_model=ApiResponse[ChemicalLibraryResponse], status_code=201)
async def create_library_item(
    body: ChemicalLibraryCreate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    conflict = await _find_conflict(db, body.name, body.cas_no)
    if conflict:
        raise HTTPException(409, f"库中已存在该化学品条目（{conflict.name}），可改为编辑该条目")
    data = body.model_dump()
    item = ChemicalLibrary(**data)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return ApiResponse(data=_serialize(item))


@router.put("/{item_id}", response_model=ApiResponse[ChemicalLibraryResponse])
async def update_library_item(
    item_id: str,
    body: ChemicalLibraryUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(ChemicalLibrary, item_id)
    if not item:
        raise HTTPException(404, "库条目不存在")
    patch = body.model_dump(exclude_unset=True)
    new_name = patch.get("name", item.name)
    new_cas = patch.get("cas_no", item.cas_no)
    conflict = await _find_conflict(db, new_name, new_cas, exclude_id=item_id)
    if conflict:
        raise HTTPException(409, f"库中已存在该化学品条目（{conflict.name}），可改为编辑该条目")
    for key, value in patch.items():
        setattr(item, key, value)
    await db.commit()
    await db.refresh(item)
    return ApiResponse(data=_serialize(item))


@router.delete("/{item_id}", response_model=ApiResponse[None])
async def delete_library_item(
    item_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(ChemicalLibrary, item_id)
    if not item:
        raise HTTPException(404, "库条目不存在")
    await db.delete(item)
    await db.commit()
    return ApiResponse(data=None)


@router.get("/collect/enterprises", response_model=ApiResponse[list[dict]])
async def list_collect_enterprises(
    keyword: str = Query("", max_length=100),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员收录用：跨用户搜索企业（返回 id/name，最多 20 条）。"""
    stmt = select(Enterprise.id, Enterprise.name)
    if keyword.strip():
        stmt = stmt.where(Enterprise.name.ilike(f"%{keyword.strip()}%"))
    rows = (await db.execute(stmt.order_by(Enterprise.name).limit(20))).all()
    return ApiResponse(data=[{"id": r[0], "name": r[1]} for r in rows])


@router.get("/collect/enterprises/{enterprise_id}/chemicals",
            response_model=ApiResponse[list[HazardousChemicalResponse]])
async def list_collect_chemicals(
    enterprise_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    ent = await db.get(Enterprise, enterprise_id)
    if not ent:
        raise HTTPException(404, "企业不存在")
    rows = (await db.execute(
        select(HazardousChemical)
        .where(HazardousChemical.enterprise_id == enterprise_id)
        .order_by(HazardousChemical.name)
    )).scalars().all()
    return ApiResponse(data=[HazardousChemicalResponse.model_validate(r) for r in rows])


@router.post("/collect", response_model=ApiResponse[ChemicalLibraryResponse], status_code=201)
async def collect_from_enterprise(
    body: ChemicalLibraryCollectRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    ent = await db.get(Enterprise, body.enterprise_id)
    if not ent:
        raise HTTPException(404, "企业不存在")
    chem = await db.get(HazardousChemical, body.chemical_id)
    if not chem or chem.enterprise_id != body.enterprise_id:
        raise HTTPException(404, "该企业的化学品记录不存在")
    conflict = await _find_conflict(db, chem.name, chem.cas_no)
    if conflict:
        raise HTTPException(409, f"库中已存在该化学品条目（{conflict.name}），可改为编辑该条目")
    # id 需在 flush 前显式生成，否则 chem.library_id = item.id 时仍为 None，源记录无法回填
    item = ChemicalLibrary(id=str(uuid4()), **{f: getattr(chem, f) for f in COLLECT_FIELDS})
    db.add(item)
    chem.library_id = item.id
    await db.commit()
    await db.refresh(item)
    return ApiResponse(data=_serialize(item))
