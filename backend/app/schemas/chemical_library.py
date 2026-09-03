from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


def _strip(v: Optional[str]) -> Optional[str]:
    return v.strip() if isinstance(v, str) else v


class ChemicalLibraryCreate(BaseModel):
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

    @field_validator("name", "cas_no", mode="before")
    @classmethod
    def _clean(cls, v: object) -> object:
        return _strip(v)  # type: ignore[arg-type]


class ChemicalLibraryUpdate(BaseModel):
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

    @field_validator("name", "cas_no", mode="before")
    @classmethod
    def _clean(cls, v: object) -> object:
        return _strip(v)  # type: ignore[arg-type]


class ChemicalLibraryResponse(BaseModel):
    id: str
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
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _dt_to_str(cls, v: object) -> str:
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v) if v is not None else ""


class ChemicalLibraryCollectRequest(BaseModel):
    enterprise_id: str
    chemical_id: str
