from datetime import datetime
from uuid import uuid4
from typing import Optional

from sqlalchemy import Index, String, Boolean, DateTime, ForeignKey, text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EnterpriseMember(Base):
    __tablename__ = "enterprise_members"
    __table_args__ = (
        # 部分唯一索引：仅绑定账号的成员去重；未绑定账号（user_id IS NULL）可多名
        Index(
            "uq_enterprise_members_bound_user",
            "enterprise_id",
            "user_id",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("role", "member")
        kwargs.setdefault("enabled", True)
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    org_node_id: Mapped[Optional[str]] = mapped_column(String(64))
    position: Mapped[Optional[str]] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
