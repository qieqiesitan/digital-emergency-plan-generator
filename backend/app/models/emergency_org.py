"""应急组织：应急指挥部/应急小组（units）、组内角色（roles）、人员指派（assignments）。

与公司组织架构（enterprises.org_structure + enterprise_members）完全分离：
应急角色只引用成员 id，不引用公司组织节点，避免一人多岗与一人多任互相限制。
"""

from datetime import datetime
from uuid import uuid4
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EmergencyOrgUnit(Base):
    __tablename__ = "emergency_org_units"
    __table_args__ = (
        Index("idx_emergency_org_units_ent", "enterprise_id", "parent_id", "sort_order"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("sort_order", 0)
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("emergency_org_units.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    duties: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EmergencyOrgRole(Base):
    __tablename__ = "emergency_org_roles"
    __table_args__ = (
        Index("idx_emergency_org_roles_unit", "unit_id", "sort_order"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("sort_order", 0)
        kwargs.setdefault("is_required", False)
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False
    )
    unit_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("emergency_org_units.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    duties: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EmergencyOrgAssignment(Base):
    __tablename__ = "emergency_org_assignments"
    __table_args__ = (
        Index("idx_emergency_org_assignments_role", "role_id"),
        Index("idx_emergency_org_assignments_member", "member_id"),
        Index("uq_emergency_org_assignments_role_member", "role_id", "member_id", unique=True),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("sort_order", 0)
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("emergency_org_roles.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprise_members.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
