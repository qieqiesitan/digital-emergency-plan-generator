from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.schemas.common import DatetimeStr

class RiskAssessmentGenerateRequest(BaseModel):
    custom_instruction: str | None = None

class RiskAssessmentSummary(BaseModel):
    risk_source_count: int = 0
    risk_level_distribution: dict[str, int] = {}
    top_risks: list[dict] = []
    risk_by_category: dict[str, int] = {}
    key_findings: list[str] = []
    overall_assessment: str = ""

class RiskAssessmentReportResponse(BaseModel):
    id: str
    enterprise_id: str
    title: str
    content: str
    summary: RiskAssessmentSummary
    status: str
    generated_by: str
    generated_at: DatetimeStr | None
    created_at: DatetimeStr
    updated_at: DatetimeStr
    model_config = {"from_attributes": True}

class RiskAssessmentPreviewResponse(BaseModel):
    report_id: str
    title: str
    html: str
