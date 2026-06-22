import json
import os
from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, ForeignKey, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base

class Enterprise(Base):
    __tablename__ = "enterprises"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(500))
    industry: Mapped[Optional[str]] = mapped_column(String(255))
    business_scope: Mapped[Optional[str]] = mapped_column(Text)
    employee_count: Mapped[Optional[int]] = mapped_column(Integer)
    building_overview: Mapped[Optional[str]] = mapped_column(Text)
    org_structure: Mapped[list] = mapped_column(JSONB, default=list)
    # 法定基本信息
    credit_code: Mapped[Optional[str]] = mapped_column(String(50))
    legal_representative: Mapped[Optional[str]] = mapped_column(String(100))
    economic_type: Mapped[Optional[str]] = mapped_column(String(50))
    established_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    registered_capital: Mapped[Optional[float]] = mapped_column(Float)
    # 联系与位置信息
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    fax: Mapped[Optional[str]] = mapped_column(String(50))
    postal_code: Mapped[Optional[str]] = mapped_column(String(10))
    land_area: Mapped[Optional[float]] = mapped_column(Float)
    building_area: Mapped[Optional[float]] = mapped_column(Float)
    # 安全管理
    safety_officer: Mapped[Optional[str]] = mapped_column(String(100))
    safety_officer_phone: Mapped[Optional[str]] = mapped_column(String(50))
    safety_staff_count: Mapped[Optional[int]] = mapped_column(Integer)
    safety_standardization: Mapped[Optional[str]] = mapped_column(String(20))
    fire_approval: Mapped[Optional[str]] = mapped_column(String(50))
    fire_approval_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_plan_filing_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_plan_filing_authority: Mapped[Optional[str]] = mapped_column(String(200))
    # 生产与物料
    main_products: Mapped[Optional[str]] = mapped_column(Text)
    annual_capacity: Mapped[Optional[str]] = mapped_column(Text)
    hazardous_chemicals: Mapped[Optional[str]] = mapped_column(Text)

    # P1 新增字段 —— 风险评估报告增强
    fire_protection_summary: Mapped[Optional[str]] = mapped_column(Text)
    special_equipment_detail: Mapped[Optional[str]] = mapped_column(Text)
    main_equipment_list: Mapped[Optional[str]] = mapped_column(Text)
    natural_conditions: Mapped[Optional[str]] = mapped_column(Text)
    special_equipment: Mapped[Optional[str]] = mapped_column(Text)
    surrounding_info: Mapped[Optional[dict]] = mapped_column(JSONB)
    # 厂区平面图 & GIS 定位
    floor_plan_url: Mapped[Optional[str]] = mapped_column(String(500))
    gis_lat: Mapped[Optional[float]] = mapped_column(Float)
    gis_lng: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    risk_sources = relationship("RiskSource", back_populates="enterprise", cascade="all, delete-orphan", lazy="selectin")
    resources = relationship("EmergencyResource", back_populates="enterprise", cascade="all, delete-orphan", lazy="selectin")
    plans = relationship("PlanProject", back_populates="enterprise", cascade="all, delete-orphan", lazy="selectin")

class RiskSource(Base):
    __tablename__ = "risk_sources"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True)
    categories: Mapped[str] = mapped_column(String(500), nullable=False, default="")  # comma-separated
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(500))
    # 厂区平面图上的点选坐标（百分比 0~100）
    location_x: Mapped[Optional[float]] = mapped_column(Float)
    location_y: Mapped[Optional[float]] = mapped_column(Float)
    description: Mapped[Optional[str]] = mapped_column(Text)
    likelihood: Mapped[Optional[int]] = mapped_column(Integer, default=3)
    severity: Mapped[Optional[int]] = mapped_column(Integer, default=3)
    risk_level: Mapped[Optional[str]] = mapped_column(String(20))
    control_measures: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    enterprise = relationship("Enterprise", back_populates="risk_sources", lazy="selectin")

class EmergencyResource(Base):
    __tablename__ = "emergency_resources"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    specification: Mapped[Optional[str]] = mapped_column(String(500))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    location: Mapped[Optional[str]] = mapped_column(String(500))
    responsible_person: Mapped[Optional[str]] = mapped_column(String(100))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50))
    is_external: Mapped[bool] = mapped_column(Boolean, default=False)
    external_address: Mapped[Optional[str]] = mapped_column(String(500))
    external_distance_km: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    enterprise = relationship("Enterprise", back_populates="resources", lazy="selectin")

class PlanTypeEnum(str, Enum):
    comprehensive = "comprehensive"
    special = "special"
    onsite = "onsite"

class PlanStatusEnum(str, Enum):
    draft = "draft"
    generating = "generating"
    completed = "completed"

class PlanProject(Base):
    __tablename__ = "plan_projects"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    enterprise_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    accident_type: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="draft")
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    enterprise = relationship("Enterprise", back_populates="plans", lazy="selectin")
    sections = relationship("PlanSection", back_populates="plan_project", cascade="all, delete-orphan", lazy="selectin")
    versions = relationship("PlanVersion", back_populates="plan_project", cascade="all, delete-orphan", lazy="selectin")

class PlanSection(Base):
    __tablename__ = "plan_sections"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    plan_project_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("plan_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    section_key: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[Optional[str]] = mapped_column(Text)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    mermaid_svgs: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    plan_project = relationship("PlanProject", back_populates="sections", lazy="selectin")

class PlanVersion(Base):
    __tablename__ = "plan_versions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    plan_project_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("plan_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[str] = mapped_column(String(50), default="manual")
    description: Mapped[Optional[str]] = mapped_column(String(500))
    snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    plan_project = relationship("PlanProject", back_populates="versions", lazy="selectin")

class PlanTemplate(Base):
    __tablename__ = "plan_templates"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    plan_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    structure: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class AIConfig(Base):
    __tablename__ = "ai_configs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(String(1024), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(String(500))
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=16384)
    top_p: Mapped[float] = mapped_column(Float, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_test_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
