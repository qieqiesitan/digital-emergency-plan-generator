"""第三方（vendor）配置统一读写：DB → env（非空）→ None，secret 加密存储。"""

import os

from app.database import async_session
from app.models.third_party_config import ThirdPartyConfig
from app.services.secret_utils import decrypt_secret, encrypt_secret

ENV_MAP = {
    "third_party.qcc.api_key": "QCC_API_KEY",
    "third_party.qcc.api_key_fallback": "QCC_API_KEY_FALLBACK",
    "third_party.qcc.endpoint": "QCC_ENDPOINT",
    "third_party.amap.api_key": "AMAP_KEY",
    "third_party.protego.hmac_secret": "EXTERNAL_API_HMAC_SECRET",
    "third_party.protego.callback_url": "PROTEGO_CALLBACK_URL",
}

KEY_TYPES = {
    "third_party.qcc.api_key": "secret",
    "third_party.qcc.api_key_fallback": "secret",
    "third_party.qcc.endpoint": "string",
    "third_party.amap.api_key": "secret",
    "third_party.protego.hmac_secret": "secret",
    "third_party.protego.callback_url": "string",
}


async def get_third_party_config(config_key: str) -> str | None:
    """读取配置：DB 有值 → 返回（secret 解密）；否则 env 非空 → 返回；否则 None。"""
    async with async_session() as session:
        row = await session.get(ThirdPartyConfig, config_key)
        if row is not None:
            if KEY_TYPES.get(config_key) == "secret":
                return decrypt_secret(row.config_value)
            return row.config_value

    env_var = ENV_MAP.get(config_key)
    if env_var:
        env_value = os.environ.get(env_var, "")
        if env_value != "":
            return env_value
    return None


async def set_third_party_config(
    config_key: str, value: str, updated_by: str | None = None
) -> None:
    """按主键 upsert 配置；secret 加密存储；记录 updated_by。"""
    config_type = KEY_TYPES.get(config_key, "string")
    stored = encrypt_secret(value) if config_type == "secret" else value

    async with async_session() as session:
        row = await session.get(ThirdPartyConfig, config_key)
        if row is None:
            session.add(
                ThirdPartyConfig(
                    config_key=config_key,
                    config_value=stored,
                    config_type=config_type,
                    updated_by=updated_by,
                )
            )
        else:
            row.config_value = stored
            row.config_type = config_type
            row.updated_by = updated_by
        await session.commit()


async def import_seed_configs() -> None:
    """启动导入：对每个 key，DB 缺失且 env 非空 → 写入；空 env 跳过。"""
    for config_key, env_var in ENV_MAP.items():
        env_value = os.environ.get(env_var, "")
        if env_value == "":
            continue
        async with async_session() as session:
            row = await session.get(ThirdPartyConfig, config_key)
        if row is None:
            await set_third_party_config(config_key, env_value)
