"""AI 能力注册表。

把"平台有哪些 AI 能力、每个用哪个提示词与模型、能不能关"变成可查可改的数据，
而不是散在 24 个端点里各写各的。
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AICapability(Base):
    __tablename__ = "ai_capabilities"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    code: Mapped[str] = mapped_column(String(60), nullable=False)  # 与 llm_call_logs.capability 对齐
    module: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    prompt_ref: Mapped[Optional[str]] = mapped_column(String(120))  # 指向 prompt_templates.template_code
    model_override: Mapped[Optional[str]] = mapped_column(String(120))
    # 2026-09-19 演练发现：这里只有 ORM 侧 default，create_all 建表时**没有库级默认值**，
    # 于是 db_migration_20260917_ai_capability.sql 的种子 INSERT（未列这三列）
    # 在空库上直接违反非空约束 → 全新安装启动失败。补 server_default 与迁移 DDL 对齐。
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    allow_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
