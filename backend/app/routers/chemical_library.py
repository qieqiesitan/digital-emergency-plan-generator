from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.chemical_library import ChemicalLibrary
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse
from app.schemas.chemical_library import (
    ChemicalLibraryCreate,
    ChemicalLibraryUpdate,
    ChemicalLibraryResponse,
)

router = APIRouter(prefix="/chemical-library", tags=["Chemical Library"])


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
