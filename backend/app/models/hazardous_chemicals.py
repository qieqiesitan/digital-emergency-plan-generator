from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional
from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class HazardousChemical(Base):
    """危险化学品信息表 —— 存储企业涉及的危险化学品 MSDS 级数据"""
    __tablename__ = "hazardous_chemicals"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    cas_no: Mapped[Optional[str]] = mapped_column(String(50))
    un_no: Mapped[Optional[str]] = mapped_column(String(20))
    physical_state: Mapped[Optional[str]] = mapped_column(String(200))
    flash_point: Mapped[Optional[str]] = mapped_column(String(50))
    explosion_limit: Mapped[Optional[str]] = mapped_column(String(50))
    ignition_temp: Mapped[Optional[str]] = mapped_column(String(50))
    density: Mapped[Optional[str]] = mapped_column(String(50))
    boiling_point: Mapped[Optional[str]] = mapped_column(String(50))
    health_hazard: Mapped[Optional[str]] = mapped_column(Text)
    fire_hazard: Mapped[Optional[str]] = mapped_column(Text)
    leak_response: Mapped[Optional[str]] = mapped_column(Text)
    storage_transport: Mapped[Optional[str]] = mapped_column(Text)
    first_aid: Mapped[Optional[str]] = mapped_column(Text)
    protective_measures: Mapped[Optional[str]] = mapped_column(Text)
    location: Mapped[Optional[str]] = mapped_column(String(300))
    max_storage: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
