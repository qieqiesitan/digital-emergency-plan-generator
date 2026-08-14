from datetime import datetime
from uuid import uuid4
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EnterpriseMember(Base):
    __tablename__ = "enterprise_members"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "user_id", name="uq_enterprise_members_ent_user"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("role", "member")
        kwargs.setdefault("enabled", True)
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    org_node_id: Mapped[Optional[str]] = mapped_column(String(64))
    position: Mapped[Optional[str]] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
