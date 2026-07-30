from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, field_validator
from app.schemas.common import DatetimeStr

class MethodCreate(BaseModel): method_type: str; name: str; description: str = ""; config: dict = {}
class MethodUpdate(BaseModel): name: str | None = None; description: str | None = None; config: dict | None = None; is_active: bool | None = None
class MethodResponse(BaseModel): id: str; enterprise_id: str | None; method_type: str; name: str; description: str = ""; config: dict; is_active: bool; is_system: bool; created_at: DatetimeStr; model_config = {"from_attributes": True}

class RiskZoneCreate(BaseModel): name: str; description: str | None = None; sort_order: int = 0; floor_plan_polygon: dict | None = None
class RiskZoneUpdate(BaseModel): name: str | None = None; description: str | None = None; sort_order: int | None = None; floor_plan_polygon: dict | None = None
class RiskZoneResponse(BaseModel): id: str; enterprise_id: str; name: str; description: str | None; sort_order: int; floor_plan_polygon: dict | None; created_at: DatetimeStr; object_count: int = 0; model_config = {"from_attributes": True}

class RiskObjectCreate(BaseModel): zone_id: str | None = None; name: str; category: str | None = None; location: str | None = None; location_x: float | None = None; location_y: float | None = None; description: str | None = None; image_url: str | None = None; is_risk_point: bool = False; sort_order: int = 0
class RiskObjectUpdate(BaseModel): zone_id: str | None = None; name: str | None = None; category: str | None = None; location: str | None = None; location_x: float | None = None; location_y: float | None = None; description: str | None = None; image_url: str | None = None; is_risk_point: bool | None = None; sort_order: int | None = None
class RiskObjectResponse(BaseModel): id: str; enterprise_id: str; zone_id: str | None; name: str; category: str | None; location: str | None; location_x: float | None; location_y: float | None; description: str | None; image_url: str | None; is_risk_point: bool; sort_order: int; created_at: DatetimeStr; unit_count: int = 0; model_config = {"from_attributes": True}

class RiskUnitCreate(BaseModel): object_id: str; name: str; unit_type: str | None = None; description: str | None = None; location: str | None = None; sort_order: int = 0
class RiskUnitUpdate(BaseModel): name: str | None = None; unit_type: str | None = None; description: str | None = None; location: str | None = None; sort_order: int | None = None
class RiskUnitResponse(BaseModel): id: str; object_id: str; name: str; unit_type: str | None; description: str | None; location: str | None; sort_order: int; created_at: DatetimeStr; event_count: int = 0; model_config = {"from_attributes": True}

class RiskEventCreate(BaseModel): unit_id: str | None = None; object_id: str | None = None; accident_type: str; description: str | None = None; trigger_conditions: str | None = None; consequences: str | None = None; method_type: str = "LS"; method_params: dict = {}
class RiskEventUpdate(BaseModel): accident_type: str | None = None; description: str | None = None; trigger_conditions: str | None = None; consequences: str | None = None; method_type: str | None = None; method_params: dict | None = None
class RiskEventResponse(BaseModel): id: str; unit_id: str | None; object_id: str | None; accident_type: str; description: str | None; trigger_conditions: str | None; consequences: str | None; method_type: str; method_params: dict; risk_level: str | None; risk_score: str | None; sort_order: int; created_at: DatetimeStr; measure_count: int = 0; model_config = {"from_attributes": True}

class RiskMeasureCreate(BaseModel): event_id: str; measure_category: str; measure_type: str | None = None; description: str; responsible_person: str | None = None; deadline: date | None = None; check_items: list[dict] = []; sort_order: int = 0
class RiskMeasureUpdate(BaseModel): measure_category: str | None = None; measure_type: str | None = None; description: str | None = None; responsible_person: str | None = None; deadline: date | None = None; check_items: list[dict] | None = None; status: str | None = None; sort_order: int | None = None
class RiskMeasureResponse(BaseModel): id: str; event_id: str; measure_category: str; measure_type: str | None; description: str; responsible_person: str | None; deadline: date | None; check_items: list[dict]; status: str; sort_order: int; created_at: DatetimeStr; model_config = {"from_attributes": True}

class HierarchyMeasureResponse(BaseModel): id: str; measure_category: str; measure_type: str | None; description: str; status: str; check_items: list[dict]; model_config = {"from_attributes": True}
class HierarchyEventResponse(BaseModel): id: str; accident_type: str; description: str | None; risk_level: str | None; risk_score: str | None; method_type: str; method_params: dict; measures: list[HierarchyMeasureResponse] = []; model_config = {"from_attributes": True}
class HierarchyUnitResponse(BaseModel): id: str; name: str; unit_type: str | None; description: str | None; events: list[HierarchyEventResponse] = []; model_config = {"from_attributes": True}
class HierarchyObjectResponse(BaseModel): id: str; name: str; category: str | None; is_risk_point: bool; units: list[HierarchyUnitResponse] = []; events: list[HierarchyEventResponse] = []; model_config = {"from_attributes": True}
class HierarchyZoneResponse(BaseModel): id: str; name: str; description: str | None; objects: list[HierarchyObjectResponse] = []; model_config = {"from_attributes": True}

class MigrationPreviewItem(BaseModel): source_id: str; source_name: str; suggested_zone: str = ""; suggested_object: str = ""; suggested_events: list[dict] = []
class MigrationPreviewResponse(BaseModel): items: list[MigrationPreviewItem]; total: int
class MigrationExecuteRequest(BaseModel): mappings: list[dict]
class SmartGuideRequest(BaseModel): description: str
class SmartGuideResponse(BaseModel): hierarchy: list[HierarchyZoneResponse]; summary: dict = {}
class MethodPreviewRequest(BaseModel): method_id: str; params: dict
class MethodPreviewResponse(BaseModel): risk_level: str; risk_score: str; action: str; deadline: str
