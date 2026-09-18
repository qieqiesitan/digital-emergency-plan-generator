"""作业票出入参。"""

from datetime import datetime
from typing import Any, Optional

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


class TicketOut(BaseModel):
    id: str
    code: str
    ticket_type: str
    level: Optional[str] = None
    status: str
    current_node_key: Optional[str] = None
    values: dict = Field(default_factory=dict)
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
