from datetime import datetime, date
from uuid import uuid4
from typing import Optional
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, ForeignKey, Date, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base
from app.models.enterprise import EnterpriseFloor

class RiskAssessmentMethod(Base):
    __tablename__ = "risk_assessment_methods"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=True, index=True)
    method_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class RiskZone(Base):
    __tablename__ = "risk_zones"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True)
    floor_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprise_floors.id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    floor_plan_polygon: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    floor = relationship("EnterpriseFloor", lazy="selectin")
    objects = relationship("RiskObject", back_populates="zone", cascade="all, delete-orphan", lazy="selectin")

class RiskObject(Base):
    __tablename__ = "risk_objects"
    __table_args__ = (
        Index("idx_ro_legacy_source", "enterprise_id", "legacy_source_id"),
    )
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True)
    zone_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("risk_zones.id", ondelete="RESTRICT"), nullable=True)
    floor_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprise_floors.id", ondelete="RESTRICT"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    location: Mapped[Optional[str]] = mapped_column(String(500))
    location_x: Mapped[Optional[float]] = mapped_column(Float)
    location_y: Mapped[Optional[float]] = mapped_column(Float)
    description: Mapped[Optional[str]] = mapped_column(Text)
    legacy_source_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500))
    is_risk_point: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    zone = relationship("RiskZone", back_populates="objects", lazy="selectin")
    floor = relationship("EnterpriseFloor", lazy="selectin")
    units = relationship("RiskUnit", back_populates="object", cascade="all, delete-orphan", lazy="selectin")
    events = relationship("RiskEvent", back_populates="object", cascade="all, delete-orphan", lazy="selectin", primaryjoin="RiskObject.id==RiskEvent.object_id")

class RiskUnit(Base):
    __tablename__ = "risk_units"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    object_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("risk_objects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_type: Mapped[Optional[str]] = mapped_column(String(50))
    description: Mapped[Optional[str]] = mapped_column(Text)
    location: Mapped[Optional[str]] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    object = relationship("RiskObject", back_populates="units", lazy="selectin")
    events = relationship("RiskEvent", back_populates="unit", cascade="all, delete-orphan", lazy="selectin")

class RiskEvent(Base):
    __tablename__ = "risk_events"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    unit_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("risk_units.id", ondelete="CASCADE"), nullable=True)
    object_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("risk_objects.id", ondelete="CASCADE"), nullable=True)
    chemical_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("hazardous_chemicals.id", ondelete="SET NULL"), nullable=True, index=True)
    accident_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    trigger_conditions: Mapped[Optional[str]] = mapped_column(Text)
    consequences: Mapped[Optional[str]] = mapped_column(Text)
    method_type: Mapped[str] = mapped_column(String(20), default="LS")
    method_params: Mapped[dict] = mapped_column(JSONB, default=dict)
    risk_level: Mapped[Optional[str]] = mapped_column(String(20))
    risk_score: Mapped[Optional[str]] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    unit = relationship("RiskUnit", back_populates="events", lazy="selectin")
    object = relationship("RiskObject", back_populates="events", lazy="selectin", primaryjoin="RiskEvent.object_id==RiskObject.id")
    measures = relationship("RiskMeasure", back_populates="event", cascade="all, delete-orphan", lazy="selectin")

class RiskMeasure(Base):
    __tablename__ = "risk_measures"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("risk_events.id", ondelete="CASCADE"), nullable=False, index=True)
    measure_category: Mapped[str] = mapped_column(String(50), nullable=False)
    measure_type: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    responsible_person: Mapped[Optional[str]] = mapped_column(String(100))
    deadline: Mapped[Optional[date]] = mapped_column(Date)
    check_items: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    event = relationship("RiskEvent", back_populates="measures", lazy="selectin")
