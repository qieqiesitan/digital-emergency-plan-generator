from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, Integer, Boolean, Text, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base

class DataDict(Base):
    __tablename__ = "data_dicts"
    __table_args__ = (UniqueConstraint("dict_type", "enterprise_id", "code", name="uq_data_dicts_type_ent_code"),)

    def __init__(self, **kwargs):
        kwargs.setdefault("enabled", True)
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    dict_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
    scope: Mapped[str] = mapped_column(String(10), default="system", nullable=False)
    enterprise_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
