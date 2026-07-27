from app.schemas.common import DatetimeStr
from typing import Optional
from pydantic import BaseModel

class PlanCreate(BaseModel):
    enterprise_id: str; plan_type: str; title: str; accident_type: str | None = None

class PlanUpdate(BaseModel):
    title: str | None = None

class PlanResponse(BaseModel):
    id: str; enterprise_id: str; enterprise_name: str = ""; plan_type: str; title: str
    accident_type: str | None; status: str; current_version: int
    sections_count: int = 0; completed_sections: int = 0; created_at: DatetimeStr; updated_at: DatetimeStr
    model_config = {"from_attributes": True}

class SectionResponse(BaseModel):
    id: str; section_key: str; title: str; level: int; sort_order: int
    content: str | None; ai_generated: bool; updated_at: DatetimeStr
    model_config = {"from_attributes": True}

class SectionUpdate(BaseModel):
    content: str

class EnterprisePlanSummary(BaseModel):
    enterprise_id: str; enterprise_name: str
    industry: str = ""
    total: int = 0
    comprehensive_count: int = 0
    special_count: int = 0
    onsite_count: int = 0
    last_updated: DatetimeStr | None = None

class RegenerateRequest(BaseModel):
    selected_text: str
    surrounding_context_before: str | None = None
    surrounding_context_after: str | None = None
    custom_instruction: str | None = None
