"""应急组织整树读写。与 /enterprises/{id}/org/nodes（公司组织树）并列且互不影响。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.schemas.common import ApiResponse
from app.schemas.emergency_org import EmergencyOrgUpdate, EmergencyUnitOut
from app.services.emergency_org_service import load_emergency_org, save_emergency_org
from app.services.data_marks import DOMAIN_ORG, mark_data_changed

router = APIRouter(prefix="/enterprises/{enterprise_id}/emergency-org", tags=["Emergency Org"])


async def _get_ent(enterprise_id: str, user_id: str, db: AsyncSession) -> Enterprise:
    """按 id 取企业并做归属校验；非法 UUID 等数据层错误统一按 404 处理。"""
    try:
        ent = (
            await db.execute(
                select(Enterprise).where(
                    Enterprise.id == enterprise_id, Enterprise.user_id == user_id
                )
            )
        ).scalar_one_or_none()
    except Exception as exc:  # noqa: BLE001 - 非法 UUID 等数据层错误统一转 404
        raise HTTPException(404, "企业不存在") from exc
    if not ent:
        raise HTTPException(404, "企业不存在")
    return ent


@router.get("", response_model=ApiResponse[list[EmergencyUnitOut]])
async def get_emergency_org(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_ent(enterprise_id, current_user.id, db)
    return ApiResponse(data=await load_emergency_org(db, enterprise_id))


@router.put("", response_model=ApiResponse[list[EmergencyUnitOut]])
async def put_emergency_org(
    enterprise_id: str,
    data: EmergencyOrgUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_ent(enterprise_id, current_user.id, db)
    units = [u.model_dump() for u in data.units]
    result = await save_emergency_org(db, enterprise_id, units)
    # 整树覆盖式保存：新增/删除/改人的差异不体现在任何一行的时间戳上，需显式打点（D-3）
    await mark_data_changed(db, enterprise_id, DOMAIN_ORG)
    await db.commit()
    return ApiResponse(data=result)
