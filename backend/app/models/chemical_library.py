from datetime import datetime
from uuid import uuid4
from typing import Optional
from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class ChemicalLibrary(Base):
    """系统级危险化学品公共库条目（MSDS 标准属性，跨企业共享）。"""
    __tablename__ = "chemical_library"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    alias: Mapped[Optional[str]] = mapped_column(String(500))
    cas_no: Mapped[Optional[str]] = mapped_column(String(50))
    remark: Mapped[Optional[str]] = mapped_column(String(100))
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
