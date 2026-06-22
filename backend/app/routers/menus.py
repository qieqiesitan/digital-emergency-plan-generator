from fastapi import APIRouter, Depends, Query
from typing import Optional
from app.dependencies import get_current_user
from app.schemas.common import ApiResponse
from app import ywt_client

router = APIRouter(prefix="/system", tags=["System Menu"])


@router.get("/menus", response_model=ApiResponse[list])
async def get_menu_tree(
    sys_code: Optional[str] = Query(None),
    app_id: Optional[int] = Query(None),
    current_user=Depends(get_current_user),
):
    """获取菜单树（从中台API代理）"""
    items = await ywt_client.fetch_menu_tree(sys_code=sys_code, app_id=app_id)
    return ApiResponse(data=items)
