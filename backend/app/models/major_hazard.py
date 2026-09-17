"""重大危险源业务 ORM：单元、单元内品种、计算快照、档案。

设计要点：
- `q_design_max` 是「设计最大量」——GB 18218-2018 4.2.2 规定实际存在量按设计最大量确定，
  因此它是计算的取值来源，不是参考字段。它与危化品台账的 `max_storage`（最大储存量）
  是两回事，故分开存、不共用字段。
- `critical_quantity_t` 与 `beta` 存在单元品种上是「当前计算口径」；
  每次计算把它们连同 q 一起复制进 `major_hazard_calculations.inputs_snapshot`，
  这样标准修订后历史结论依然可复算。
- `major_hazard_calculations` 只追加不修改：应用层只提供新增与查询，不提供更新/删除。
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MajorHazardUnit(Base):
    """重大危险源单元。GB 18218 3.5/3.6：生产单元、储存单元。"""

    __tablename__ = "major_hazard_units"
    __table_args__ = (Index("idx_mhu_enterprise", "enterprise_id", "is_active"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_type: Mapped[str] = mapped_column(String(20), nullable=False)  # production | storage
    boundary_desc: Mapped[Optional[str]] = mapped_column(Text)
    floor_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprise_floors.id", ondelete="SET NULL")
    )
    polygon: Mapped[Optional[dict]] = mapped_column(JSONB)
    address: Mapped[Optional[str]] = mapped_column(String(500))
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    department: Mapped[Optional[str]] = mapped_column(String(255))
    responsible_person: Mapped[Optional[str]] = mapped_column(String(100))
    responsible_phone: Mapped[Optional[str]] = mapped_column(String(50))
    risk_object_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("risk_objects.id", ondelete="SET NULL")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    established_at: Mapped[Optional[date]] = mapped_column(Date)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    chemicals = relationship(
        "MajorHazardUnitChemical", back_populates="unit", cascade="all, delete-orphan", lazy="selectin"
    )
    record = relationship(
        "MajorHazardRecord", back_populates="unit", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )


class MajorHazardUnitChemical(Base):
    """单元内的一种危险化学品及其存量（计算输入）。"""

    __tablename__ = "major_hazard_unit_chemicals"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    unit_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("major_hazard_units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chemical_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("hazardous_chemicals.id", ondelete="SET NULL")
    )
    chemical_name: Mapped[str] = mapped_column(String(500), nullable=False)
    physical_state: Mapped[Optional[str]] = mapped_column(String(200))
    storage_location: Mapped[Optional[str]] = mapped_column(String(300))
    q_design_max: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    q_actual: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    critical_quantity_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("critical_quantities.id", ondelete="SET NULL")
    )
    critical_quantity_t: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    beta: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    beta_source: Mapped[str] = mapped_column(String(10), nullable=False)  # table3 | table4 | manual
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    unit = relationship("MajorHazardUnit", back_populates="chemicals", lazy="selectin")


class MajorHazardCalculation(Base):
    """计算快照。只追加、不修改——保证任何历史结论都能原样复算。"""

    __tablename__ = "major_hazard_calculations"
    __table_args__ = (UniqueConstraint("unit_id", "seq", name="uq_mhc_unit_seq"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    unit_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("major_hazard_units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    s_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    r_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    alpha: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    exposed_population: Mapped[int] = mapped_column(Integer, nullable=False)
    is_major_hazard: Mapped[bool] = mapped_column(Boolean, nullable=False)
    level: Mapped[Optional[str]] = mapped_column(String(20))
    formula_version: Mapped[str] = mapped_column(String(40), nullable=False)
    inputs_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    calculated_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MajorHazardRecord(Base):
    """重大危险源档案与备案：包保责任人、备案信息、附件资料。"""

    __tablename__ = "major_hazard_records"
    __table_args__ = (UniqueConstraint("enterprise_id", "hazard_code", name="uq_mhr_ent_code"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    unit_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("major_hazard_units.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hazard_code: Mapped[Optional[str]] = mapped_column(String(64))
    filing_status: Mapped[str] = mapped_column(String(20), nullable=False, default="未备案")
    filing_no: Mapped[Optional[str]] = mapped_column(String(100))
    filing_date: Mapped[Optional[date]] = mapped_column(Date)
    chief_name: Mapped[Optional[str]] = mapped_column(String(100))
    chief_post: Mapped[Optional[str]] = mapped_column(String(100))
    chief_phone: Mapped[Optional[str]] = mapped_column(String(50))
    tech_name: Mapped[Optional[str]] = mapped_column(String(100))
    tech_post: Mapped[Optional[str]] = mapped_column(String(100))
    tech_phone: Mapped[Optional[str]] = mapped_column(String(50))
    oper_name: Mapped[Optional[str]] = mapped_column(String(100))
    oper_post: Mapped[Optional[str]] = mapped_column(String(100))
    oper_phone: Mapped[Optional[str]] = mapped_column(String(50))
    attachments: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    completeness: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    unit = relationship("MajorHazardUnit", back_populates="record", lazy="selectin")
