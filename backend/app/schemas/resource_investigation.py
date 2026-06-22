from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.schemas.common import DatetimeStr

class ResourceInvestigationGenerateRequest(BaseModel):
    custom_instruction: str | None = None

class ResourceGap(BaseModel):
    category: str = ""
    needed: str = ""
    reason: str = ""
    severity: str = ""

class ResourceInvestigationSummary(BaseModel):
    internal_resource_count: int = 0
    external_resource_count: int = 0
    internal_by_category: dict[str, int] = {}
    external_by_category: dict[str, int] = {}
    resource_gaps: list[ResourceGap] = []
    key_findings: list[str] = []
    overall_assessment: str = ""

class ResourceInvestigationReportResponse(BaseModel):
    id: str
    enterprise_id: str
    title: str
    content: str
    summary: ResourceInvestigationSummary
    status: str
    generated_by: str
    generated_at: DatetimeStr | None
    created_at: DatetimeStr
    updated_at: DatetimeStr
    model_config = {"from_attributes": True}

class ResourceInvestigationPreviewResponse(BaseModel):
    report_id: str
    title: str
    html: str
