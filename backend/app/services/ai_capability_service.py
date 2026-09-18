"""AI 能力注册表服务。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_capability import AICapability


class CapabilityError(ValueError):
    """能力配置错误。"""


def is_capability_enabled(capability) -> bool:
    """未注册的能力默认启用。

    注册表是"可管理"，不是"必须注册才能用"——否则新加一个 AI 能力忘了注册
    就会静默失效，这类 bug 极难排查。
    """
    if capability is None:
        return True
    return bool(getattr(capability, "is_enabled", True))


async def get_capability(db: AsyncSession, code: str):
    res = await db.execute(select(AICapability).where(AICapability.code == code))
    return res.scalar_one_or_none()


async def list_capabilities(db: AsyncSession) -> list[AICapability]:
    res = await db.execute(select(AICapability).order_by(AICapability.sort_order))
    return list(res.scalars().all())
