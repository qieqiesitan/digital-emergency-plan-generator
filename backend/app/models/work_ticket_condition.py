"""措施条件映射与情景项 ORM。

两张表都由 `backend/seed_work_ticket_conditions.py` 从
`backend/app/regulations/data/work_ticket_conditions.yaml` 生成，
**不要手工改动库里的行**——改了会在下次重跑时被覆盖。
锚定键 `measure_ref` = 措施正文规范化后的 sha256 前 32 位（见 work_ticket_condition_loader）。
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WorkTicketMeasureCondition(Base):
    """某票种的某条措施（按正文锚定）依赖哪些现场条件。"""

    __tablename__ = "work_ticket_measure_conditions"
    __table_args__ = (
        UniqueConstraint("ticket_type", "measure_ref", "condition_key", name="uq_wtmc_key"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    ticket_type: Mapped[str] = mapped_column(String(20), nullable=False)
    measure_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    # 仅用于展示排序，不参与匹配（匹配只用 measure_ref）
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    condition_key: Mapped[str] = mapped_column(String(60), nullable=False)


class WorkTicketScenario(Base):
    """某票种要向用户展示的情景区项（只含人工勾选项，auto_rule 非空的不在此表）。"""

    __tablename__ = "work_ticket_scenarios"
    __table_args__ = (
        UniqueConstraint("ticket_type", "condition_key", name="uq_wts_key"),
        Index("idx_wts_type", "ticket_type"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    ticket_type: Mapped[str] = mapped_column(String(20), nullable=False)
    condition_key: Mapped[str] = mapped_column(String(60), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    auto_rule: Mapped[str | None] = mapped_column(String(60))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
