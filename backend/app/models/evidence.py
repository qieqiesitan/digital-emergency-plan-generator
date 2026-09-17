"""依据层：把任何一条业务数据挂到具体法规条文上。

多态设计（owner_type + owner_id）避免给每个业务表加外键，
条文原文不冗余存储——实时按 article_anchor 从法规体系取，
避免法规修订后引用内容过期。
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EvidenceRef(Base):
    __tablename__ = "evidence_refs"
    __table_args__ = (
        UniqueConstraint(
            "owner_type", "owner_id", "article_anchor", "relation", name="uq_evidence_owner_anchor"
        ),
        Index("idx_evidence_owner", "owner_type", "owner_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    owner_type: Mapped[str] = mapped_column(String(40), nullable=False)
    owner_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    regulation_id: Mapped[Optional[str]] = mapped_column(String(64))
    article_anchor: Mapped[str] = mapped_column(String(200), nullable=False)
    relation: Mapped[str] = mapped_column(String(20), nullable=False, default="依据")
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
