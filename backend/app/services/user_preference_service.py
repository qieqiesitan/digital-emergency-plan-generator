"""用户偏好读写（生成风格/常用企业等），进程内缓存 TTL 5 分钟。"""

import time
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func, select
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# 模型内建于此（计划允许「service 内建 Table」路线，避免把新表拆到 app/models/
# 再改导出文件；与迁移 backend/db_migration_20260902_agent_preferences.sql 对应）。


class UserPreference(Base):
    """每个用户一行：生成风格/详细程度/报告主题/常用企业等偏好。"""

    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    style_preference: Mapped[str | None] = mapped_column(String(20))
    detail_level: Mapped[str | None] = mapped_column(String(20))
    report_topics: Mapped[list | None] = mapped_column(JSONB)
    common_enterprise_ids: Mapped[list | None] = mapped_column(JSONB)
    extra: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

_PREF_KEYS = (
    "style_preference",
    "detail_level",
    "report_topics",
    "common_enterprise_ids",
    "extra",
)

_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 300


def _row_to_prefs(row: UserPreference | None) -> dict:
    """把 ORM 行转为偏好 dict；无行 → 全字段默认 None。"""
    prefs = {key: None for key in _PREF_KEYS}
    if row is None:
        return prefs
    for key in _PREF_KEYS:
        prefs[key] = getattr(row, key)
    return prefs


async def get_preferences(db, user_id: str) -> dict:
    """读取用户偏好：命中 TTL 缓存直接返回，否则查表并回填缓存。"""
    cached = _cache.get(user_id)
    if cached and time.time() - cached[0] < _CACHE_TTL:
        return cached[1]
    row = (
        await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
    ).scalar_one_or_none()
    prefs = _row_to_prefs(row)
    _cache[user_id] = (time.time(), prefs)
    return prefs


async def set_preferences(db, user_id: str, updates: dict) -> dict:
    """upsert 用户偏好：已存在行就地更新，否则新建；成功后失效缓存。"""
    row = await db.get(UserPreference, user_id)
    if row is None:
        row = UserPreference(user_id=user_id)
        db.add(row)
    for key, value in updates.items():
        if key in _PREF_KEYS:
            setattr(row, key, value)
    invalidate_cache(user_id)
    return _row_to_prefs(row)


def invalidate_cache(user_id: str) -> None:
    """主动失效某用户缓存（set 后或外部直接写库后调用）。"""
    _cache.pop(user_id, None)
