"""DataHub 接入层 ORM：来源、字段映射、任务、条目、对账。

设计要点：
- `ingest_items.raw_payload` 永久保留，任何时候能回答"这条数据当初长什么样、来自哪一行"；
- `idempotency_key` 是数据库级唯一约束，重复推送不产生重复条目；
- 密钥只存 `secret_ref`（指向 third_party_config 的键名），本表绝不存明文。
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IngestSource(Base):
    """数据来源：文件 / 表格 / 系统推送 / 系统拉取 / 手工录入。"""

    __tablename__ = "ingest_sources"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    secret_ref: Mapped[Optional[str]] = mapped_column(String(120))
    target_entity: Mapped[Optional[str]] = mapped_column(String(60))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FieldMapping(Base):
    """来源字段 → 目标实体字段的映射与转换规则。"""

    __tablename__ = "field_mappings"
    __table_args__ = (
        UniqueConstraint("source_id", "target_entity", name="uq_fm_source_entity"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("ingest_sources.id", ondelete="CASCADE"), nullable=False
    )
    target_entity: Mapped[str] = mapped_column(String(60), nullable=False)
    mapping: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    transforms: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    required_fields: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IngestJob(Base):
    """一次接入执行：计数与错误摘要。"""

    __tablename__ = "ingest_jobs"
    __table_args__ = (Index("idx_ingest_jobs_source", "source_id", "created_at"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("ingest_sources.id", ondelete="SET NULL")
    )
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_review: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )


class IngestItem(Base):
    """待确认条目：raw_payload 永久保留，只有 confirm 才写入正式业务表。"""

    __tablename__ = "ingest_items"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ingest_items_idem"),
        Index("idx_ingest_items_job_status", "job_id", "status"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("ingest_jobs.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(300), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    target_entity: Mapped[str] = mapped_column(String(60), nullable=False)
    target_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    source_locator: Mapped[Optional[str]] = mapped_column(String(200))
    confidence: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    review_note: Mapped[Optional[str]] = mapped_column(Text)
    error: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngestReconciliation(Base):
    """对账记录：来源声明条数 vs 实际收到条数。"""

    __tablename__ = "ingest_reconciliations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("ingest_sources.id", ondelete="CASCADE"), nullable=False
    )
    expected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actual_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    diff_note: Mapped[Optional[str]] = mapped_column(Text)
    checksum: Mapped[Optional[str]] = mapped_column(String(80))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
