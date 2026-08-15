from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.data_dict import DataDict
from app.models.enterprise import Enterprise
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.data_dict import DataDictCreate, DataDictResponse, DataDictUpdate
from app.services.data_dict_service import invalidate_dict_cache

router = APIRouter(tags=["Data Dicts"])


async def _get_enterprise(enterprise_id: str, user_id: str, db: AsyncSession) -> Enterprise:
    ent = (await db.execute(select(Enterprise).where(
        Enterprise.id == enterprise_id, Enterprise.user_id == user_id))).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    return ent


@router.get("/settings/data-dicts", response_model=ApiResponse[list[DataDictResponse]])
async def list_system_dicts(dict_type: str | None = None, _=Depends(require_admin), db=Depends(get_db)):
    stmt = select(DataDict).where(DataDict.enterprise_id.is_(None))
    if dict_type:
        stmt = stmt.where(DataDict.dict_type == dict_type)
    rows = (await db.execute(stmt.order_by(DataDict.dict_type, DataDict.sort_order))).scalars().all()
    return ApiResponse(data=[_serialize(r) for r in rows])


@router.post("/settings/data-dicts", response_model=ApiResponse, status_code=201)
async def create_system_dict(body: DataDictCreate, _=Depends(require_admin), db=Depends(get_db)):
    exists = (await db.execute(select(DataDict.id).where(
        DataDict.dict_type == body.dict_type, DataDict.enterprise_id.is_(None), DataDict.code == body.code))).first()
    if exists:
        raise HTTPException(409, "同类型同 code 的系统条目已存在")
    db.add(DataDict(**body.model_dump(), scope="system", is_system=True, enterprise_id=None))
    await db.commit()
    invalidate_dict_cache(dict_type=body.dict_type)
    return ApiResponse(data={}, message="已创建")


@router.put("/settings/data-dicts/{dict_id}", response_model=ApiResponse)
async def update_system_dict(dict_id: str, body: DataDictUpdate, _=Depends(require_admin), db=Depends(get_db)):
    row = await db.get(DataDict, dict_id)
    if not row or row.enterprise_id is not None:
        raise HTTPException(404, "字典条目不存在")
    for k, v in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(row, k, v)
    await db.commit()
    invalidate_dict_cache(dict_type=row.dict_type)
    return ApiResponse(data={}, message="已更新")


@router.get("/enterprises/{enterprise_id}/data-dicts", response_model=ApiResponse[list[DataDictResponse]])
async def list_enterprise_dicts(enterprise_id: str, dict_type: str | None = None,
                                current_user: User = Depends(get_current_user), db=Depends(get_db)):
    await _get_enterprise(enterprise_id, current_user.id, db)
    stmt = select(DataDict).where(
        (DataDict.enterprise_id == enterprise_id) | (DataDict.enterprise_id.is_(None)))
    if dict_type:
        stmt = stmt.where(DataDict.dict_type == dict_type)
    rows = (await db.execute(stmt.order_by(DataDict.scope, DataDict.dict_type, DataDict.sort_order))).scalars().all()
    return ApiResponse(data=[_serialize(r) for r in rows])


@router.post("/enterprises/{enterprise_id}/data-dicts", response_model=ApiResponse, status_code=201)
async def create_enterprise_dict(enterprise_id: str, body: DataDictCreate,
                                 current_user: User = Depends(get_current_user), db=Depends(get_db)):
    await _get_enterprise(enterprise_id, current_user.id, db)
    exists = (await db.execute(select(DataDict.id).where(
        DataDict.dict_type == body.dict_type, DataDict.enterprise_id == enterprise_id,
        DataDict.code == body.code))).first()
    if exists:
        raise HTTPException(409, "同类型同 code 的企业条目已存在（可编辑覆盖）")
    db.add(DataDict(**body.model_dump(), scope="enterprise", enterprise_id=enterprise_id, is_system=False))
    await db.commit()
    invalidate_dict_cache(enterprise_id, body.dict_type)
    return ApiResponse(data={}, message="已创建")


@router.put("/enterprises/{enterprise_id}/data-dicts/{dict_id}", response_model=ApiResponse)
async def update_enterprise_dict(enterprise_id: str, dict_id: str, body: DataDictUpdate,
                                 current_user: User = Depends(get_current_user), db=Depends(get_db)):
    row = await db.get(DataDict, dict_id)
    if not row or row.enterprise_id != enterprise_id:
        raise HTTPException(404, "企业字典条目不存在")
    for k, v in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(row, k, v)
    await db.commit()
    invalidate_dict_cache(enterprise_id, row.dict_type)
    return ApiResponse(data={}, message="已更新")


@router.delete("/enterprises/{enterprise_id}/data-dicts/{dict_id}", response_model=ApiResponse)
async def delete_enterprise_dict(enterprise_id: str, dict_id: str,
                                 current_user: User = Depends(get_current_user), db=Depends(get_db)):
    row = await db.get(DataDict, dict_id)
    if not row or row.enterprise_id != enterprise_id:
        raise HTTPException(404, "企业字典条目不存在")
    await db.delete(row)
    await db.commit()
    invalidate_dict_cache(enterprise_id, row.dict_type)
    return ApiResponse(data={}, message="已删除（恢复系统默认）")


def _serialize(r: DataDict) -> DataDictResponse:
    return DataDictResponse.model_validate(r)
