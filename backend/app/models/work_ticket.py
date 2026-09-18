"""作业票模板层 ORM：票面字段、措施库、审批流程。

设计要点：
- **模板驱动**——8 类票的差异落在数据里，不落在代码里；
- `is_statutory` 标记法定审批环节，服务层据此拒绝删除（视觉走查确认的"可加不可删"）；
- 每条安全措施带 `article_anchor`，可点开看 GB 30871 原文条款。
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WorkTicketTemplate(Base):
    """作业票模板。一个作业类型可有多条（如动火票按特级/一级/二级分）。"""

    __tablename__ = "work_ticket_templates"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    code: Mapped[str] = mapped_column(String(20), nullable=False)  # DHZY/YXKJ/MBCD/GCZY/QZDZ/LSYD/PTZY/DLZY
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    level: Mapped[Optional[str]] = mapped_column(String(20))  # 特级/一级/二级 或 Ⅰ级/Ⅱ级…；不分级票为空
    is_graded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    standard_ref: Mapped[str] = mapped_column(String(80), nullable=False, default="GB 30871-2022")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    fields = relationship(
        "WorkTicketTemplateField", back_populates="template", cascade="all, delete-orphan", lazy="selectin"
    )
    measures = relationship(
        "WorkTicketTemplateMeasure", back_populates="template", cascade="all, delete-orphan", lazy="selectin"
    )


class WorkTicketTemplateField(Base):
    """票面字段定义。"""

    __tablename__ = "work_ticket_template_fields"
    __table_args__ = (
        UniqueConstraint("template_id", "field_key", name="uq_wttf_template_key"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    template_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_templates.id", ondelete="CASCADE"), nullable=False
    )
    field_key: Mapped[str] = mapped_column(String(60), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    field_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    group_name: Mapped[str] = mapped_column(String(40), nullable=False, default="基本信息")
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    options: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    validation: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    allow_ai_prefill: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    template = relationship("WorkTicketTemplate", back_populates="fields", lazy="selectin")


class WorkTicketTemplateMeasure(Base):
    """该模板的必备安全措施，逐条来自 GB 30871 第 5~12 章。"""

    __tablename__ = "work_ticket_template_measures"
    __table_args__ = (Index("idx_wttm_template_order", "template_id", "sort_order"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    template_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_templates.id", ondelete="CASCADE"), nullable=False
    )
    measure_text: Mapped[str] = mapped_column(Text, nullable=False)
    article_anchor: Mapped[str] = mapped_column(String(120), nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    template = relationship("WorkTicketTemplate", back_populates="measures", lazy="selectin")


class WorkTicketFlowTemplate(Base):
    """审批流程模板。企业可对同一作业票类型配多条流程。"""

    __tablename__ = "work_ticket_flow_templates"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    template_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_templates.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    nodes = relationship(
        "WorkTicketFlowNode",
        back_populates="flow_template",
        cascade="all, delete-orphan",
        order_by="WorkTicketFlowNode.sort_order",
        lazy="selectin",
    )


class WorkTicketFlowNode(Base):
    """审批节点。

    `is_statutory=True` 表示该节点由 GB 30871 附录B 表B.1 法定要求，
    企业可以改绑定的角色、可以在其前后插入自有节点，**但不能删除**。
    """

    __tablename__ = "work_ticket_flow_nodes"
    __table_args__ = (
        UniqueConstraint("flow_template_id", "sort_order", name="uq_wtfn_flow_order"),
        UniqueConstraint("flow_template_id", "node_key", name="uq_wtfn_flow_key"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    flow_template_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_flow_templates.id", ondelete="CASCADE"), nullable=False
    )
    node_key: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    role_code: Mapped[Optional[str]] = mapped_column(String(30))  # 绑定既有 Role.code
    sign_policy: Mapped[str] = mapped_column(String(10), nullable=False, default="any")  # any|all
    condition_expr: Mapped[Optional[str]] = mapped_column(String(200))  # 受限表达式
    reject_to: Mapped[str] = mapped_column(String(20), nullable=False, default="previous")  # previous|submitter
    is_statutory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timeout_hours: Mapped[Optional[int]] = mapped_column(Integer)

    flow_template = relationship("WorkTicketFlowTemplate", back_populates="nodes", lazy="selectin")
