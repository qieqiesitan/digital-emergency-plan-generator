"""DataHub 出入参。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SourceIn(BaseModel):
    source_type: str = Field(pattern="^(file|sheet|api_push|api_pull|manual)$")
    name: str = Field(min_length=1, max_length=200)
    config: dict = Field(default_factory=dict)
    secret_ref: Optional[str] = Field(default=None, max_length=120)
    target_entity: Optional[str] = Field(default=None, max_length=60)
    is_active: bool = True


class SourceOut(SourceIn):
    id: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: str
    source_id: Optional[str] = None
    trigger: str
    status: str
    total: int
    imported: int
    skipped: int
    failed: int
    pending_review: int
    error_summary: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ItemOut(BaseModel):
    id: str
    job_id: str
    target_entity: str
    status: str
    confidence: str
    source_locator: Optional[str] = None
    raw_payload: dict
    error: Optional[str] = None
    """前端用于决定复选框默认状态：仅 high/medium 默认勾选。"""
    default_checked: bool = True


class ConfirmIn(BaseModel):
    item_ids: list[str] = Field(min_length=1)
