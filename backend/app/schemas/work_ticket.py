"""作业票出入参。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OpenTicketIn(BaseModel):
    enterprise_id: str
    enterprise_code: str = Field(min_length=1, max_length=20)
    ticket_type: str = Field(
        pattern="^(DHZY|YXKJ|MBCD|GCZY|QZDZ|LSYD|PTZY|DLZY)$",
        description="GB 30871-2022 附录A 的 8 类特殊作业票",
    )
    template_id: str
    level: Optional[str] = None
    values: dict = Field(default_factory=dict)


class GasTestIn(BaseModel):
    sampled_at: datetime
    location: Optional[str] = None
    gas_type: Optional[str] = None
    result: Optional[str] = None
    tester: Optional[str] = None
    conclusion: Optional[str] = None


class NodeActionIn(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    opinion: Optional[str] = None


class TicketTransitionIn(BaseModel):
    """生命周期动作：开始作业 / 完工 / 归档 / 作废（审批节点动作用 NodeActionIn）。"""

    action: str = Field(pattern="^(start|finish|close|cancel)$")
    opinion: Optional[str] = None


class TicketOut(BaseModel):
    id: str
    code: str
    ticket_type: str
    level: Optional[str] = None
    status: str
    current_node_key: Optional[str] = None
    values: dict = Field(default_factory=dict)
    values_meta: dict = Field(default_factory=dict)
    measures_meta: dict = Field(default_factory=dict)
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DraftSaveIn(BaseModel):
    """草稿保存：票面值 + 来源留痕 + 措施三态。"""

    values: dict = Field(default_factory=dict)
    values_meta: dict = Field(default_factory=dict)
    measures_meta: dict = Field(default_factory=dict)


class AiPrefillIn(BaseModel):
    """AI 预填请求。work_content 可空（列表页直接点 AI 生成时）。"""

    enterprise_id: str
    ticket_type: str
    level: Optional[str] = None
    work_content: Optional[str] = None


class BatchCreateIn(BaseModel):
    """新建作业包：一次检修（同地点 + 同一时段）的共享信息。"""

    enterprise_id: str
    title: str = Field(min_length=1, max_length=200)
    floor_id: Optional[str] = None
    zone_id: Optional[str] = None
    risk_object_id: Optional[str] = None
    location_text: Optional[str] = None
    work_period_start: Optional[datetime] = None
    work_period_end: Optional[datetime] = None
    shared_values: dict = Field(default_factory=dict)
    content_base: Optional[str] = None
    risk_basis: Optional[str] = None


class BatchUpdateIn(BaseModel):
    """改共享信息：None 表示不改；只回写未提交的票。"""

    title: Optional[str] = None
    location_text: Optional[str] = None
    work_period_start: Optional[datetime] = None
    work_period_end: Optional[datetime] = None
    content_base: Optional[str] = None
    risk_basis: Optional[str] = None
    shared_values: Optional[dict] = None


class BatchTicketSpec(BaseModel):
    ticket_type: str
    level: Optional[str] = None
    template_id: str


class BatchTicketsIn(BaseModel):
    tickets: list[BatchTicketSpec] = Field(min_length=1)


class BatchOut(BaseModel):
    id: str
    enterprise_id: str
    title: str
    status: str
    floor_id: Optional[str] = None
    zone_id: Optional[str] = None
    risk_object_id: Optional[str] = None
    location_text: Optional[str] = None
    work_period_start: Optional[datetime] = None
    work_period_end: Optional[datetime] = None
    shared_values: dict = Field(default_factory=dict)
    content_base: Optional[str] = None
    risk_basis: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BatchTransitionIn(BaseModel):
    action: str = Field(pattern="^(close|cancel)$")
