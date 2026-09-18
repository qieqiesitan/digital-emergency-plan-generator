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


class MemberPosition(Base):
    """成员任职关系：一人可挂多个组织节点（一个主岗 + 若干兼岗）。

    enterprise_members.org_node_id 保留为主岗镜像列，由 member_position_service 同步维护，
    使只认主岗的既有消费方（隐患报表部门列等）零改动。
    """

    __tablename__ = "member_positions"
    __table_args__ = (
        Index("uq_member_positions_member_node", "member_id", "org_node_id", unique=True),
        # 部分唯一索引：每个成员最多一个主岗
        Index(
            "uq_member_positions_primary",
            "member_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("is_primary", False)
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprise_members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_node_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
