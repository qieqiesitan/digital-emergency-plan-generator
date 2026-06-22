from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator

# ── Create ──
class HazardousChemicalCreate(BaseModel):
    name: str
    cas_no: Optional[str] = None
    un_no: Optional[str] = None
    physical_state: Optional[str] = None
    flash_point: Optional[str] = None
    explosion_limit: Optional[str] = None
    ignition_temp: Optional[str] = None
    density: Optional[str] = None
    boiling_point: Optional[str] = None
    health_hazard: Optional[str] = None
    fire_hazard: Optional[str] = None
    leak_response: Optional[str] = None
    storage_transport: Optional[str] = None
    first_aid: Optional[str] = None
    protective_measures: Optional[str] = None
    location: Optional[str] = None
    max_storage: Optional[str] = None

# ── Update ──
class HazardousChemicalUpdate(BaseModel):
    name: Optional[str] = None
    cas_no: Optional[str] = None
    un_no: Optional[str] = None
    physical_state: Optional[str] = None
    flash_point: Optional[str] = None
    explosion_limit: Optional[str] = None
    ignition_temp: Optional[str] = None
    density: Optional[str] = None
    boiling_point: Optional[str] = None
    health_hazard: Optional[str] = None
    fire_hazard: Optional[str] = None
    leak_response: Optional[str] = None
    storage_transport: Optional[str] = None
    first_aid: Optional[str] = None
    protective_measures: Optional[str] = None
    location: Optional[str] = None
    max_storage: Optional[str] = None

# ── Response ──
class HazardousChemicalResponse(BaseModel):
    id: str
    enterprise_id: str
    name: str
    cas_no: Optional[str] = None
    un_no: Optional[str] = None
    physical_state: Optional[str] = None
    flash_point: Optional[str] = None
    explosion_limit: Optional[str] = None
    ignition_temp: Optional[str] = None
    density: Optional[str] = None
    boiling_point: Optional[str] = None
    health_hazard: Optional[str] = None
    fire_hazard: Optional[str] = None
    leak_response: Optional[str] = None
    storage_transport: Optional[str] = None
    first_aid: Optional[str] = None
    protective_measures: Optional[str] = None
    location: Optional[str] = None
    max_storage: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _dt_to_str(cls, v: object) -> str:
        """SQLAlchemy returns datetime; Pydantic v2 model_validate doesn''t auto-coerce to str."""
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v) if v is not None else ""
