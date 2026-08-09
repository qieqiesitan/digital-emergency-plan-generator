"""系统级 AI 配置统一读取。"""
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
