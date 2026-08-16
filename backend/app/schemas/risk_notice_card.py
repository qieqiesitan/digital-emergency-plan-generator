from typing import Literal
from pydantic import BaseModel


class SignItem(BaseModel):
    category: Literal["warning", "prohibition", "instruction", "notice"]
    name: str
    svg_name: str


class RightColumn(BaseModel):
    hazard_description: str = ""
    accident_types: list[str] = []
    control_measures: list[str] = []
    emergency_measures: list[str] = []
    signs: list[SignItem] = []
    signs_source: str | None = None


class CardData(RightColumn):
    object_id: str
    enterprise_name: str
    name: str
    code: str
    level: str
    inherent_risk_level: str | None = None
    level_color: str
    responsible_unit: str
    responsible_person: str
    contact_phone: str
    fallback_used: bool = False
    has_open_hazard: bool = False
    signs: list[SignItem] = []
    snapshot: dict | None = None
    stale: bool = False
    public_url: str
    generated_at: str


class CardSummary(BaseModel):
    object_id: str
    name: str
    zone_name: str = ""
    level: str
    level_color: str
    accident_types: list[str] = []
    signs: list[SignItem] = []
    responsible_unit: str = ""
    has_open_hazard: bool = False
    snapshot: dict | None = None
    stale: bool = False
    public_url: str


class ExportRequest(BaseModel):
    object_ids: list[str]


class ExportResponse(BaseModel):
    file_key: str
    warnings: list[str] = []


class AiOptimizeResponse(BaseModel):
    original: RightColumn
    optimized: RightColumn


class SignSuggestion(BaseModel):
    remove: list[str] = []
    add: list[str] = []
    reasons: list[dict] = []


class AiSignReviewResponse(BaseModel):
    original_signs: list[SignItem] = []
    suggestion: SignSuggestion
    # 候选库（端点已组装的去重全量标志，供前端人工微调/中文名映射复用）
    catalog: list[SignItem] = []


class SnapshotSaveRequest(BaseModel):
    content: RightColumn


class SnapshotResponse(BaseModel):
    version: int
    source: str


class TokenResetResponse(BaseModel):
    public_url: str
