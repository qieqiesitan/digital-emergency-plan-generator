"""系统级 AI 配置统一读取。"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enterprise import AIConfig


async def get_system_ai_config(db: AsyncSession) -> AIConfig | None:
    """返回系统级 AI 配置（user_id IS NULL 且激活），无则返回 None。"""
    result = await db.execute(
        select(AIConfig).where(
            AIConfig.user_id.is_(None),
            AIConfig.is_system.is_(True),
            AIConfig.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


# 能力覆盖只认这几个键，其余一律忽略。
# 历史教训 B19：客户端参数混入请求体会被严格 API 返回 400；
# 配置里塞进来的任意键更不能透传——那是把配置页变成请求体注入口。
ALLOWED_OVERRIDE_KEYS = ("model", "temperature", "max_tokens", "timeout")


def apply_capability_override(ai_config: Any, capability: str) -> dict:
    """返回该能力实际使用的模型参数；未命中覆盖时回落系统级配置。

    用途：抽取类任务用便宜的小模型、报告生成用强模型。
    覆盖为空或键不在白名单时，一切照旧用系统级配置。
    """
    overrides = getattr(ai_config, "capability_overrides", None) or {}
    entry = overrides.get(capability)
    if not isinstance(entry, dict):
        entry = {}

    # 注意：AIConfig 的模型字段名是 model_name（不是 model）；
    # 覆盖结构里统一用 "model" 作为键，便于与 llm_call_logs.model 对齐。
    out: dict = {
        "base_config": ai_config,
        "model": getattr(ai_config, "model_name", None) or getattr(ai_config, "model", None),
    }
    for key in ALLOWED_OVERRIDE_KEYS:
        value = entry.get(key)
        if value is not None:
            out[key] = value
    return out


async def get_ai_config_for(db: AsyncSession, capability: str) -> AIConfig | None:
    """取系统级 AI 配置。能力级覆盖由 apply_capability_override 处理。

    保留独立函数是为了调用点语义清晰（"我要的是给某项能力用的配置"），
    实现上暂时与 get_system_ai_config 一致。
    """
    return await get_system_ai_config(db)
