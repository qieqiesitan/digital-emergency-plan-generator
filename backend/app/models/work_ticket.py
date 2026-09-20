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
    text,
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
    # server_default 必须与 ORM default 一致：迁移里的种子 INSERT 不写该列，
    # 只有 ORM default → 空库上会违反非空约束（2026-09-19 演练发现）
    validation: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False, server_default=text("'{}'::jsonb")
    )
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
    # 会签单位清单（如动土的"水/电/汽/工艺/设备/消防/安全管理"）。
    # 用于"按部门会签"场景——部门是组织概念，不该塞进 Role（角色是权限概念）。
    countersign_units: Mapped[Optional[list]] = mapped_column(JSONB)
    sign_policy: Mapped[str] = mapped_column(String(10), nullable=False, default="any")  # any|all
    condition_expr: Mapped[Optional[str]] = mapped_column(String(200))  # 受限表达式
    reject_to: Mapped[str] = mapped_column(String(20), nullable=False, default="previous")  # previous|submitter
    is_statutory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timeout_hours: Mapped[Optional[int]] = mapped_column(Integer)

    flow_template = relationship("WorkTicketFlowTemplate", back_populates="nodes", lazy="selectin")


class WorkTicketBatch(Base):
    """作业包：一次检修（同企业 + 同地点 + 同一时段）下的多张作业票。

    共享信息按"语义槽位"存在 `shared_values`，落到各票的 field_key 由
    `services.work_ticket_batch.SLOT_TARGETS` 决定（不同票种的地点字段名不同）。
    """

    __tablename__ = "work_ticket_batches"
    __table_args__ = (Index("idx_wtb_enterprise_status", "enterprise_id", "status"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    floor_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprise_floors.id", ondelete="SET NULL")
    )
    zone_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("risk_zones.id", ondelete="SET NULL")
    )
    risk_object_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("risk_objects.id", ondelete="SET NULL")
    )
    location_text: Mapped[Optional[str]] = mapped_column(String(500))
    work_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    work_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    shared_values: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False, server_default=text("'{}'::jsonb")
    )
    content_base: Mapped[Optional[str]] = mapped_column(Text)
    risk_basis: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkTicketInstance(Base):
    """作业票实例。编号规则 {类型}-{企业码}-{YYYYMMDD}-{4位序号}。"""

    __tablename__ = "work_ticket_instances"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "code", name="uq_wti_ent_code"),
        Index("idx_wti_enterprise_status", "enterprise_id", "status"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False
    )
    # 所属作业包（一次检修的多张票共享信息 / 票号互相关联）
    batch_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("work_ticket_batches.id", ondelete="SET NULL"),
        index=True,
    )
    template_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_templates.id", ondelete="RESTRICT"), nullable=False
    )
    flow_template_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_flow_templates.id", ondelete="SET NULL")
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    ticket_type: Mapped[str] = mapped_column(String(20), nullable=False)
    level: Mapped[Optional[str]] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    current_node_key: Mapped[Optional[str]] = mapped_column(String(60))
    current_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    values: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # 每个票面字段的来源留痕（source/source_ref/prefilled_at/confirmed_at/confirmed_by/edited）。
    # 老票该列为 '{}'：一律按人工填写处理，不新增任何提交阻断。
    values_meta: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False, server_default=text("'{}'::jsonb")
    )
    # 每条措施的三态（pending/confirmed/not_applicable）与"不适用"理由、操作人、时间。
    measures_meta: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False, server_default=text("'{}'::jsonb")
    )
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    extend_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancel_reason: Mapped[Optional[str]] = mapped_column(Text)
    submitted_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkTicketNodeRecord(Base):
    """节点办理记录。"""

    __tablename__ = "work_ticket_node_records"
    __table_args__ = (Index("idx_wtnr_instance", "instance_id", "created_at"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    instance_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_instances.id", ondelete="CASCADE"), nullable=False
    )
    node_key: Mapped[str] = mapped_column(String(60), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    opinion: Mapped[Optional[str]] = mapped_column(Text)
    acted_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkTicketGasTest(Base):
    """气体检测记录。动火/受限空间类为提交前必填，一次作业可多次取样。

    归属二选一：某张票（`instance_id`）或某个作业包（`batch_id`）。
    包级记录由同包内的动火/受限空间票共享（同一地点同一时段一次检测），
    **但不豁免 30 分钟时效**——超过 `GAS_TEST_MAX_AGE` 一样阻断提交。
    """

    __tablename__ = "work_ticket_gas_tests"
    __table_args__ = (Index("idx_wtgt_instance", "instance_id", "sampled_at"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    instance_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_instances.id", ondelete="CASCADE")
    )
    batch_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("work_ticket_batches.id", ondelete="CASCADE"),
        index=True,
    )
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(200))
    gas_type: Mapped[Optional[str]] = mapped_column(String(100))
    result: Mapped[Optional[str]] = mapped_column(String(100))
    tester: Mapped[Optional[str]] = mapped_column(String(100))
    conclusion: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkTicketAuditLog(Base):
    """全状态变更留痕（对齐 HazardAuditLog）。"""

    __tablename__ = "work_ticket_audit_logs"
    __table_args__ = (Index("idx_wtal_instance", "instance_id", "created_at"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    instance_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_instances.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(20))
    to_status: Mapped[Optional[str]] = mapped_column(String(20))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    acted_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkTicketPrintSnapshot(Base):
    """打印快照。打印即固化，之后只能新建版本。"""

    __tablename__ = "work_ticket_print_snapshots"
    __table_args__ = (UniqueConstraint("instance_id", "version", name="uq_wtps_instance_version"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    instance_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_instances.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    printed_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
