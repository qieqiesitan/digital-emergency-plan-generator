from fastapi import APIRouter, Depends, HTTPException, Query
from app.dependencies import get_current_user
from app.schemas.common import ApiResponse
from app import ywt_client

router = APIRouter(prefix="/system", tags=["System Dict"])


@router.get("/dicts/{dict_type}", response_model=ApiResponse[list])
async def get_dict_items(
    dict_type: str,
    current_user=Depends(get_current_user),
):
    """获取指定字典类型的所有条目（从中台API代理）"""
    items = await ywt_client.fetch_dict_items(dict_type)
    return ApiResponse(data=items)


@router.get("/dict-types", response_model=ApiResponse[list])
async def list_dict_types(
    current_user=Depends(get_current_user),
):
    """列出所有字典类型（从中台API代理）"""
    result = await ywt_client.fetch_all_dict_types()
    return ApiResponse(data=result.get("data", []) or [])
