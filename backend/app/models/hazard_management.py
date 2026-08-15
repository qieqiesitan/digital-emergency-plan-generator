"""隐患排查治理模型（B 规格 §5.1-5.10）。

10 张 hazard_* 表：排查计划/任务/项、隐患记录、整改、复查、审批、审计日志、
通知、检查表模板。UUID 字符串主键、显式 FK、JSONB；
enabled/is_system/status/result 默认值在 __init__ 中 setdefault（PlanSection 先例）。
"""

from datetime import datetime, date
from uuid import uuid4
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, Date, Text, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class HazardChecklistTemplate(Base):
    """检查表模板：enterprise_id NULL 表示系统默认模板。"""

    __tablename__ = "hazard_checklist_templates"

    def __init__(self, **kwargs):
        kwargs.setdefault("is_system", False)
        kwargs.setdefault("items", [])
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class HazardInspectionPlan(Base):
    """隐患排查计划。"""

    __tablename__ = "hazard_inspection_plans"

    def __init__(self, **kwargs):
        kwargs.setdefault("enabled", True)
        kwargs.setdefault("zone_ids", [])
        kwargs.setdefault("weekdays", None)
        kwargs.setdefault("ai_suggestion", None)
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    weekdays: Mapped[Optional[list]] = mapped_column(JSONB)
    zone_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    template_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("hazard_checklist_templates.id", ondelete="SET NULL"), nullable=True, index=True)
    responsible_user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ai_suggestion: Mapped[Optional[dict]] = mapped_column(JSONB)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class HazardInspectionTask(Base):
    """排查任务。"""

    __tablename__ = "hazard_inspection_tasks"

    def __init__(self, **kwargs):
        kwargs.setdefault("status", "pending")
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    plan_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("hazard_inspection_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    responsible_user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    overdue_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reminder_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class HazardInspectionItem(Base):
    """排查项。"""

    __tablename__ = "hazard_inspection_items"

    def __init__(self, **kwargs):
        kwargs.setdefault("result", "pending")
        kwargs.setdefault("photo_urls", [])
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("hazard_inspection_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    object_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("risk_objects.id", ondelete="SET NULL"), nullable=True)
    measure_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("risk_measures.id", ondelete="SET NULL"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    expected_note: Mapped[Optional[str]] = mapped_column(Text)
    result: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    remark: Mapped[Optional[str]] = mapped_column(Text)
    photo_urls: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class HazardRecord(Base):
    """隐患记录：code 企业内唯一。"""

    __tablename__ = "hazard_records"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "code", name="uq_hazard_records_ent_code"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("status", "registered")
        kwargs.setdefault("photo_urls", [])
        kwargs.setdefault("rectification_plan", {})
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_task_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    source_item_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    object_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("risk_objects.id", ondelete="SET NULL"), nullable=True)
    measure_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("risk_measures.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    photo_urls: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    location: Mapped[Optional[str]] = mapped_column(String(500))
    hazard_type: Mapped[Optional[str]] = mapped_column(String(20))
    cause_analysis: Mapped[Optional[str]] = mapped_column(Text)
    level: Mapped[Optional[str]] = mapped_column(String(10))
    level_source: Mapped[Optional[str]] = mapped_column(String(10))
    grading_basis: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="registered")
    rectification_plan: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    deadline: Mapped[Optional[date]] = mapped_column(Date)
    rectification_user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewer_user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class HazardRectification(Base):
    """隐患整改记录。"""

    __tablename__ = "hazard_rectifications"

    def __init__(self, **kwargs):
        kwargs.setdefault("evidence", [])
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    record_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("hazard_records.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class HazardReview(Base):
    """隐患复查（首次复查/二次复核/销号）。"""

    __tablename__ = "hazard_reviews"

    def __init__(self, **kwargs):
        kwargs.setdefault("evidence", [])
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    record_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("hazard_records.id", ondelete="CASCADE"), nullable=False, index=True)
    review_type: Mapped[str] = mapped_column(String(20), nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    result: Mapped[str] = mapped_column(String(10), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    evidence: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class HazardApproval(Base):
    """隐患分级/销号审批。"""

    __tablename__ = "hazard_approvals"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    record_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("hazard_records.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class HazardAuditLog(Base):
    """隐患全流程审计日志。"""

    __tablename__ = "hazard_audit_logs"

    def __init__(self, **kwargs):
        kwargs.setdefault("detail", {})
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True)
    record_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    detail: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class HazardNotification(Base):
    """隐患提醒通知。"""

    __tablename__ = "hazard_notifications"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    record_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(String(500))
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
