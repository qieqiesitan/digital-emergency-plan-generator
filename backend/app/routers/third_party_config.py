"""管理员第三方配置 API：GET 掩码列表 / PUT 批量更新（secret 加密存储）。

- GET  /system/third-party-config：返回全部 key 的 label / configured /
  masked_value / type / description，secret 只返回掩码，永不返回明文；
- PUT  /system/third-party-config：批量更新，两遍处理——先全量校验
  （key ∈ KEY_SPEC、value strip 非空、长度 ≤ VALUE_MAX_LENGTH、同 key 去重），
  全部通过后再逐个写入，保证部分失败时无任何项生效；同 key 重复项去重
  （后写覆盖前写且只写一次）；secret 由服务层加密后入库；
  updated_by 记录操作人用户 id（current_user.id，与 hazard_management 先例一致）；
- 日志只记录 key 与操作人，不记录 value。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies import require_admin
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.secret_utils import mask_secret
from app.services.third_party_config import (
    KEY_SPEC,
    get_third_party_config,
    set_third_party_config,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system/third-party-config", tags=["Third Party Config"])

# 单条 value 长度上限：覆盖所有 key 的实际长度（API key / endpoint / 回调 URL）。
VALUE_MAX_LENGTH = 2000

# 展示元数据：config_key -> (label, description)，label 为管理员页面直接展示的中文名。
CONFIG_META: dict[str, dict[str, str]] = {
    "third_party.qcc.api_key": {
        "label": "企查查主 Key",
        "description": "企查查企业工商信息查询主密钥",
    },
    "third_party.qcc.api_key_fallback": {
        "label": "企查查备用 Key",
        "description": "企查查主 Key 不可用时的备用密钥",
    },
    "third_party.qcc.endpoint": {
        "label": "企查查 Endpoint",
        "description": "企查查 API 服务地址",
    },
    "third_party.amap.api_key": {
        "label": "高德 Web 服务 Key",
        "description": "高德地图 Web 服务密钥（地理编码/逆地理编码/POI 检索）",
    },
    "third_party.protego.hmac_secret": {
        "label": "PROTEGO HMAC Secret",
        "description": "PROTEGO 回调签名 HMAC 密钥",
    },
    "third_party.protego.callback_url": {
        "label": "PROTEGO 回调 URL",
        "description": "PROTEGO 回调通知地址",
    },
}


class ConfigItem(BaseModel):
    key: str
    label: str
    configured: bool
    masked_value: str
    type: str
    description: str


class ConfigUpdateItem(BaseModel):
    key: str
    value: str = Field(..., min_length=1, max_length=VALUE_MAX_LENGTH)


@router.get("", response_model=ApiResponse[list[ConfigItem]])
async def list_third_party_config(_: User = Depends(require_admin)):
    items: list[ConfigItem] = []
    for config_key, (_, config_type) in KEY_SPEC.items():
        value = await get_third_party_config(config_key)
        meta = CONFIG_META.get(config_key, {})
        if config_type == "secret":
            masked_value = mask_secret(value) if value else "****"
        else:
            # 非 secret（endpoint/回调 URL）非敏感，直接展示便于管理员核对
            masked_value = value or ""
        items.append(
            ConfigItem(
                key=config_key,
                label=meta.get("label", config_key),
                configured=value is not None,
                masked_value=masked_value,
                type=config_type,
                description=meta.get("description", ""),
            )
        )
    return ApiResponse(data=items)


@router.put("", response_model=ApiResponse[list[str]])
async def update_third_party_config(
    data: list[ConfigUpdateItem],
    current_user: User = Depends(require_admin),
):
    # 两遍处理：先全量校验（key ∈ KEY_SPEC、value strip 非空、同 key 去重），
    # 全部通过后再逐个写入，避免部分项失败时已写入的项无法回滚。
    # 同 key 重复项：去重（后写覆盖前写，且只写一次）。
    validated: dict[str, str] = {}
    for item in data:
        if item.key not in KEY_SPEC:
            raise HTTPException(status_code=422, detail=f"未知配置项: {item.key}")
        value = item.value.strip()
        if not value:
            raise HTTPException(status_code=422, detail=f"配置项 {item.key} 的值不能为空")
        validated[item.key] = value

    updated_keys: list[str] = []
    for config_key, value in validated.items():
        await set_third_party_config(config_key, value, updated_by=current_user.id)
        # 日志不打印 value，避免明文密钥泄露
        logger.info(
            "第三方配置已更新: key=%s operator=%s operator_id=%s",
            config_key,
            current_user.name,
            current_user.id,
        )
        updated_keys.append(config_key)
    return ApiResponse(data=updated_keys)
