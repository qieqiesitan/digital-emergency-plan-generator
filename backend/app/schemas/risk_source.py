from app.schemas.common import DatetimeStr
from typing import Optional
from pydantic import BaseModel, field_validator

# 风险可能性/严重性 等级映射（1-5 整数 ↔ 中文标签）
_L_LEVELS = {1: "很低", 2: "低", 3: "中", 4: "高", 5: "很高"}
_S_LEVELS = {1: "很低", 2: "低", 3: "中", 4: "高", 5: "很高"}
_L_REV = {s: i for i, s in _L_LEVELS.items()}
_S_REV = {s: i for i, s in _S_LEVELS.items()}

def _str_to_int(v, rev: dict) -> int | None:
    """前端 str → DB int"""
    if v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        if v in rev:
            return rev[v]
        try:
            return int(v)
        except (ValueError, TypeError):
            return 3
    return 3

def _int_to_str(v, levels: dict) -> str | None:
    """DB int → 前端 str"""
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, int):
        return levels.get(v, str(v))
    return str(v)

class RiskSourceCreate(BaseModel):
    categories: list[str] = []
    name: str
    location: str | None = None
    location_x: float | None = None
    location_y: float | None = None
    description: str | None = None
    likelihood: int | None = None
    severity: int | None = None
    control_measures: str | None = None

    @field_validator("categories", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if isinstance(v, str):
            return [c.strip() for c in v.split(",") if c.strip()]
        return v or []

    @field_validator("likelihood", mode="before")
    @classmethod
    def coerce_likelihood(cls, v):
        return _str_to_int(v, _L_REV)

    @field_validator("severity", mode="before")
    @classmethod
    def coerce_severity(cls, v):
        return _str_to_int(v, _S_REV)

class RiskSourceUpdate(BaseModel):
    categories: list[str] | None = None
    name: str | None = None
    location: str | None = None
    location_x: float | None = None
    location_y: float | None = None
    description: str | None = None
    likelihood: int | None = None
    severity: int | None = None
    control_measures: str | None = None

    @field_validator("likelihood", mode="before")
    @classmethod
    def coerce_likelihood(cls, v):
        return _str_to_int(v, _L_REV)

    @field_validator("severity", mode="before")
    @classmethod
    def coerce_severity(cls, v):
        return _str_to_int(v, _S_REV)

class RiskSourceResponse(BaseModel):
    id: str
    enterprise_id: str
    categories: list[str]
    name: str
    location: str | None
    location_x: float | None
    location_y: float | None
    description: str | None
    likelihood: str | None
    severity: str | None
    risk_level: str | None
    control_measures: str | None
    sort_order: int
    created_at: DatetimeStr
    model_config = {"from_attributes": True}

    @field_validator("categories", mode="before")
    @classmethod
    def parse_categories(cls, v):
        if isinstance(v, str):
            return [c.strip() for c in v.split(",") if c.strip()]
        return v or []

    @field_validator("likelihood", mode="before")
    @classmethod
    def normalize_likelihood(cls, v):
        return _int_to_str(v, _L_LEVELS)

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, v):
        return _int_to_str(v, _S_LEVELS)
