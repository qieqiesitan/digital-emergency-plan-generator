from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.system import SysConfig
from app.schemas.system import ConfigItem, ConfigCreate, ConfigUpdate
from app.schemas.common import ApiResponse
from app.dependencies import get_current_user

router = APIRouter(prefix="/configs", tags=["System Config"])


@router.get("", response_model=ApiResponse[list[ConfigItem]])
async def list_configs(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(SysConfig).order_by(SysConfig.config_key))).scalars().all()
    return ApiResponse(data=[ConfigItem.model_validate(r) for r in rows])


@router.get("/{config_key}", response_model=ApiResponse[ConfigItem])
async def get_config(
    config_key: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(select(SysConfig).where(SysConfig.config_key == config_key))).scalar_one_or_none()
    if not row:
        raise HTTPException(404, f"配置项 {config_key} 不存在")
    return ApiResponse(data=ConfigItem.model_validate(row))


@router.put("/{config_key}", response_model=ApiResponse[ConfigItem])
async def set_config(
    config_key: str,
    data: ConfigUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(select(SysConfig).where(SysConfig.config_key == config_key))).scalar_one_or_none()
    if row:
        row.config_value = data.config_value
        if data.config_type:
            row.config_type = data.config_type
        if data.description is not None:
            row.description = data.description
    else:
        row = SysConfig(
            config_key=config_key,
            config_value=data.config_value,
            config_type=data.config_type or "string",
            description=data.description,
        )
        db.add(row)
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=ConfigItem.model_validate(row))


@router.delete("/{config_key}")
async def delete_config(
    config_key: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(select(SysConfig).where(SysConfig.config_key == config_key))).scalar_one_or_none()
    if row:
        await db.delete(row)
        await db.commit()
    return {"code": 0, "message": "已删除"}
