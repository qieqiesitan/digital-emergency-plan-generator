from app.schemas.common import DatetimeStr
from typing import Optional
from pydantic import BaseModel

class EmergencyResourceCreate(BaseModel):
    category: str; name: str; specification: str | None = None; quantity: int = 0
    unit: str | None = None; location: str | None = None; responsible_person: str | None = None
    contact_phone: str | None = None; is_external: bool = False
    external_address: str | None = None; external_distance_km: float | None = None

class EmergencyResourceUpdate(BaseModel):
    category: str | None = None; name: str | None = None; specification: str | None = None
    quantity: int | None = None; unit: str | None = None; location: str | None = None
    responsible_person: str | None = None; contact_phone: str | None = None
    is_external: bool | None = None; external_address: str | None = None
    external_distance_km: float | None = None

class EmergencyResourceResponse(BaseModel):
    id: str; enterprise_id: str; category: str; name: str; specification: str | None
    quantity: int; unit: str | None; location: str | None; responsible_person: str | None
    contact_phone: str | None; is_external: bool; external_address: str | None
    external_distance_km: float | None; created_at: DatetimeStr
    model_config = {"from_attributes": True}
