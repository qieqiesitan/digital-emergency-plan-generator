from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReportVersionBase(Base):
    """报告版本基类：风险评估报告/资源调查报告共用（快照 content+summary）。"""
    __abstract__ = True

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    version_number: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RiskAssessmentVersion(ReportVersionBase):
    __tablename__ = "risk_assessment_versions"
    report_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("risk_assessment_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class ResourceInvestigationVersion(ReportVersionBase):
    __tablename__ = "resource_investigation_versions"
    report_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("resource_investigation_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
