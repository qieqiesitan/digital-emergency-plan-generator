"""第三方（vendor）配置统一读写：DB → env（非空）→ None，secret 加密存储。"""

import os

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import async_session
from app.models.third_party_config import ThirdPartyConfig
from app.services.secret_utils import decrypt_secret, encrypt_secret

# 单一映射：config_key -> (环境变量名, 存储类型)，避免 ENV_MAP / KEY_TYPES 双处维护漂移。
KEY_SPEC: dict[str, tuple[str, str]] = {
    "third_party.qcc.api_key": ("QCC_API_KEY", "secret"),
    "third_party.qcc.api_key_fallback": ("QCC_API_KEY_FALLBACK", "secret"),
    "third_party.qcc.endpoint": ("QCC_ENDPOINT", "string"),
    "third_party.amap.api_key": ("AMAP_KEY", "secret"),
    "third_party.protego.hmac_secret": ("EXTERNAL_API_HMAC_SECRET", "secret"),
    "third_party.protego.callback_url": ("PROTEGO_CALLBACK_URL", "string"),
}


def _config_type(config_key: str) -> str:
    """返回配置存储类型；未知 key 按 string 处理（与旧 KEY_TYPES.get 默认一致）。"""
    return KEY_SPEC.get(config_key, ("", "string"))[1]


async def get_third_party_config(config_key: str) -> str | None:
    """读取配置：DB 有值 → 返回（secret 解密）；否则 env 非空 → 返回；否则 None。"""
    async with async_session() as session:
        row = await session.get(ThirdPartyConfig, config_key)
        if row is not None:
            if _config_type(config_key) == "secret":
                return decrypt_secret(row.config_value)
            return row.config_value

    env_var = KEY_SPEC.get(config_key, ("", ""))[0]
    if env_var:
        env_value = os.environ.get(env_var, "").strip()
        if env_value != "":
            return env_value
    return None


async def set_third_party_config(
    config_key: str, value: str, updated_by: str | None = None
) -> None:
    """按主键原子 upsert 配置（PostgreSQL ON CONFLICT）；secret 加密存储；记录 updated_by。"""
    config_type = _config_type(config_key)
    stored = encrypt_secret(value) if config_type == "secret" else value

    stmt = pg_insert(ThirdPartyConfig).values(
        config_key=config_key,
        config_value=stored,
        config_type=config_type,
        updated_by=updated_by,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[ThirdPartyConfig.config_key],
        set_={
            "config_value": stmt.excluded.config_value,
            "config_type": stmt.excluded.config_type,
            "updated_by": stmt.excluded.updated_by,
            "updated_at": func.now(),
        },
    )
    async with async_session() as session:
        await session.execute(stmt)
        await session.commit()


async def import_seed_configs() -> None:
    """启动导入：对每个 key，DB 缺失且 env 非空 → 写入；空 env 跳过。"""
    for config_key, (env_var, _) in KEY_SPEC.items():
        env_value = os.environ.get(env_var, "").strip()
        if env_value == "":
            continue
        async with async_session() as session:
            row = await session.get(ThirdPartyConfig, config_key)
        if row is None:
            await set_third_party_config(config_key, env_value)
