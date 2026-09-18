from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, Integer, Boolean, Text, DateTime, UniqueConstraint, ForeignKey, func, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base

class DataDict(Base):
    __tablename__ = "data_dicts"
    __table_args__ = (UniqueConstraint("dict_type", "enterprise_id", "code", name="uq_data_dicts_type_ent_code"),)

    def __init__(self, **kwargs):
        kwargs.setdefault("enabled", True)
        super().__init__(**kwargs)

    # 与迁移 DDL 对齐：data_dicts 的种子 INSERT 不写 id，靠库级默认值 gen_random_uuid()；
    # 只写 ORM default 时 create_all 建表没有该默认值 → 空库插入违反非空约束（2026-09-19 演练发现）
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )
    dict_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
    scope: Mapped[str] = mapped_column(String(10), default="system", nullable=False)
    enterprise_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # 同上：迁移种子 INSERT 不写 enabled（2026-09-19 演练发现空库会违反非空约束）
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
