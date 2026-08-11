import math
from datetime import datetime, date
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from app.schemas.common import DatetimeStr

class MethodCreate(BaseModel): method_type: str; name: str; description: str = ""; config: dict = {}
class MethodUpdate(BaseModel): name: str | None = None; description: str | None = None; config: dict | None = None; is_active: bool | None = None
class MethodResponse(BaseModel): id: str; enterprise_id: str | None; method_type: str; name: str; description: str = ""; config: dict; is_active: bool; is_system: bool; created_at: DatetimeStr; model_config = {"from_attributes": True}

class FloorCreate(BaseModel): name: str; sort_order: int = 0; floor_plan_url: str | None = None; description: str | None = None; canvas_width: int | None = None; canvas_height: int | None = None; canvas_texts: list[dict] = []; is_default: bool = False
class FloorUpdate(BaseModel): name: str | None = None; sort_order: int | None = None; floor_plan_url: str | None = None; description: str | None = None; canvas_width: int | None = None; canvas_height: int | None = None; canvas_texts: list[dict] | None = None; is_default: bool | None = None
class FloorResponse(BaseModel): id: str; enterprise_id: str; name: str; sort_order: int; floor_plan_url: str | None; description: str | None; canvas_width: int | None; canvas_height: int | None; canvas_texts: list[dict]; is_default: bool; zone_count: int = 0; risk_point_count: int = 0; created_at: DatetimeStr; updated_at: DatetimeStr; model_config = {"from_attributes": True}

class RiskPolygonPoint(BaseModel):
    x: float
    y: float

    @field_validator("x", "y")
    @classmethod
    def check_range(cls, v: float):
        if not (0 <= v <= 100):
            raise ValueError("坐标范围 0-100")
        return v

class RiskPolygon(BaseModel):
    id: str
    label: str | None = None
    points: list[RiskPolygonPoint] = Field(min_length=3)

class RiskZoneFloorPlanPolygon(BaseModel):
    version: Literal[2] = 2
    color_source: Literal["auto", "manual"]
    color: str | None = None
    polygons: list[RiskPolygon] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy(cls, data: Any):
        """兼容旧前端 {points: [...]} 结构，自动归一化为 v2。"""
        if isinstance(data, dict) and data.get("points") is not None and data.get("polygons") is None:
            return {
                "version": 2,
                "color_source": "auto",
                "color": None,
                "polygons": [{
                    "id": data.get("id") or "legacy-polygon",
                    "label": data.get("label"),
                    "points": data.get("points"),
                }],
            }
        return data

    @model_validator(mode="after")
    def validate_v2_rules(self):
        if self.color_source == "manual" and not isinstance(self.color, str):
            raise ValueError("manual 模式必须提供 color")
        ids = [p.id for p in self.polygons]
        if len(ids) != len(set(ids)):
            raise ValueError("polygons.id 不能重复")
        return self
class RiskCanvasText(BaseModel): id: str; content: str; x: float; y: float; font_size: int = 14; color: str = "#333333"; rotation: int = 0; sort_order: int = 0

class RiskZoneCreate(BaseModel): floor_id: str | None = None; name: str; description: str | None = None; sort_order: int = 0; floor_plan_polygon: RiskZoneFloorPlanPolygon | None = None
class RiskZoneUpdate(BaseModel): floor_id: str | None = None; name: str | None = None; description: str | None = None; sort_order: int | None = None; floor_plan_polygon: RiskZoneFloorPlanPolygon | None = None
class RiskZoneResponse(BaseModel): id: str; enterprise_id: str; floor_id: str | None; floor_name: str | None = None; name: str; description: str | None; sort_order: int; floor_plan_polygon: RiskZoneFloorPlanPolygon | None; max_risk_level: str | None = None; effective_color: str | None = None; object_count: int = 0; created_at: DatetimeStr; updated_at: DatetimeStr; model_config = {"from_attributes": True}

class RiskObjectCreate(BaseModel):
    zone_id: str | None = None
    floor_id: str | None = None
    name: str
    category: str | None = None
    location: str | None = None
    location_x: float | None = None
    location_y: float | None = None
    description: str | None = None
    image_url: str | None = None
    responsible_unit: str | None = None
    responsible_person: str | None = None
    contact_phone: str | None = None
    is_risk_point: bool = False
    sort_order: int = 0

    @model_validator(mode="after")
    def validate_risk_point(self):
        if self.is_risk_point and (not self.zone_id or self.location_x is None or self.location_y is None):
            raise ValueError("风险点必须绑定分区和坐标")
        return self

class RiskObjectUpdate(BaseModel):
    zone_id: str | None = None
    floor_id: str | None = None
    name: str | None = None
    category: str | None = None
    location: str | None = None
    location_x: float | None = None
    location_y: float | None = None
    description: str | None = None
    image_url: str | None = None
    responsible_unit: str | None = None
    responsible_person: str | None = None
    contact_phone: str | None = None
    is_risk_point: bool | None = None
    sort_order: int | None = None

    @model_validator(mode="after")
    def validate_risk_point(self):
        if self.is_risk_point is True and (not self.zone_id or self.location_x is None or self.location_y is None):
            raise ValueError("风险点必须绑定分区和坐标")
        return self
class RiskObjectResponse(BaseModel): id: str; enterprise_id: str; zone_id: str | None; floor_id: str | None; name: str; category: str | None; location: str | None; location_x: float | None; location_y: float | None; description: str | None; image_url: str | None; responsible_unit: str | None = None; responsible_person: str | None = None; contact_phone: str | None = None; is_risk_point: bool; sort_order: int; created_at: DatetimeStr; updated_at: DatetimeStr; unit_count: int = 0; model_config = {"from_attributes": True}

class BatchSaveZoneItem(BaseModel): client_id: str | None = None; zone_id: str | None = None; name: str | None = None; description: str | None = None; sort_order: int = 0; updated_at: DatetimeStr | None = None; floor_plan_polygon: RiskZoneFloorPlanPolygon
class BatchSaveRiskPointItem(BaseModel):
    client_id: str | None = None
    id: str | None = None
    name: str | None = None
    category: str | None = None
    description: str | None = None
    zone_id: str | None = None
    zone_client_id: str | None = None
    floor_id: str | None = None
    location_x: float
    location_y: float
    updated_at: DatetimeStr | None = None

    @field_validator("location_x", "location_y")
    @classmethod
    def check_point_coordinate(cls, v: float):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v):
            raise ValueError("坐标必须是 0-100 范围内的有限数值")
        if not (0 <= v <= 100):
            raise ValueError("坐标必须是 0-100 范围内的有限数值")
        return v

class BatchSaveRequest(BaseModel): floor_id: str; floor_updated_at: DatetimeStr; zones: list[BatchSaveZoneItem]; risk_points: list[BatchSaveRiskPointItem] = []; deleted_risk_point_ids: list[str] = []; deleted_zone_ids: list[str] = []; confirm_cascade_zone_ids: list[str] = []; texts: list[RiskCanvasText] = []
class BatchSaveResponse(BaseModel): floor: FloorResponse; zones: list[RiskZoneResponse]; risk_points: list[RiskObjectResponse]; texts: list[RiskCanvasText]; created_zone_map: dict[str, str] = {}; created_risk_point_map: dict[str, str] = {}

class WorkbenchZone(RiskZoneResponse): objects: list[RiskObjectResponse] = []
class WorkbenchResponse(BaseModel): floors: list[FloorResponse]; current_floor_id: str; zones: list[WorkbenchZone]; risk_points: list[RiskObjectResponse]; texts: list[RiskCanvasText]
class OverviewResponse(BaseModel): floor: FloorResponse; zones: list[WorkbenchZone]; risk_points: list[RiskObjectResponse]

class RiskUnitCreate(BaseModel): object_id: str | None = None; name: str; unit_type: str | None = None; description: str | None = None; location: str | None = None; sort_order: int = 0
class RiskUnitUpdate(BaseModel): name: str | None = None; unit_type: str | None = None; description: str | None = None; location: str | None = None; sort_order: int | None = None
class RiskUnitResponse(BaseModel): id: str; object_id: str; name: str; unit_type: str | None; description: str | None; location: str | None; sort_order: int; created_at: DatetimeStr; event_count: int = 0; model_config = {"from_attributes": True}

class RiskEventCreate(BaseModel): unit_id: str | None = None; object_id: str | None = None; accident_type: str; description: str | None = None; trigger_conditions: str | None = None; consequences: str | None = None; method_type: str = "LS"; method_params: dict = {}; chemical_id: str | None = None
class RiskEventUpdate(BaseModel): accident_type: str | None = None; description: str | None = None; trigger_conditions: str | None = None; consequences: str | None = None; method_type: str | None = None; method_params: dict | None = None; chemical_id: str | None = None
class RiskEventResponse(BaseModel): id: str; unit_id: str | None; object_id: str | None; chemical_id: str | None = None; accident_type: str; description: str | None; trigger_conditions: str | None; consequences: str | None; method_type: str; method_params: dict; risk_level: str | None; risk_score: str | None; sort_order: int; created_at: DatetimeStr; measure_count: int = 0; model_config = {"from_attributes": True}

class RiskMeasureCreate(BaseModel): event_id: str | None = None; measure_category: str; measure_type: str | None = None; description: str; responsible_person: str | None = None; deadline: date | None = None; check_items: list[dict] = []; sort_order: int = 0
class RiskMeasureUpdate(BaseModel): measure_category: str | None = None; measure_type: str | None = None; description: str | None = None; responsible_person: str | None = None; deadline: date | None = None; check_items: list[dict] | None = None; status: str | None = None; sort_order: int | None = None
class RiskMeasureResponse(BaseModel): id: str; event_id: str; measure_category: str; measure_type: str | None; description: str; responsible_person: str | None; deadline: date | None; check_items: list[dict]; status: str; sort_order: int; created_at: DatetimeStr; model_config = {"from_attributes": True}

class HierarchyMeasureResponse(BaseModel): id: str; measure_category: str; measure_type: str | None; description: str; status: str; check_items: list[dict]; model_config = {"from_attributes": True}
class HierarchyEventResponse(BaseModel):
    id: str
    accident_type: str
    description: str | None
    risk_level: str | None
    risk_score: str | None
    method_type: str
    method_params: dict
    chemical_id: str | None = None
    measures: list[HierarchyMeasureResponse] = []
    model_config = {"from_attributes": True}
class HierarchyUnitResponse(BaseModel): id: str; name: str; unit_type: str | None; description: str | None; events: list[HierarchyEventResponse] = []; model_config = {"from_attributes": True}
class HierarchyObjectResponse(BaseModel): id: str; name: str; category: str | None; is_risk_point: bool; floor_id: str | None = None; location_x: float | None = None; location_y: float | None = None; units: list[HierarchyUnitResponse] = []; events: list[HierarchyEventResponse] = []; model_config = {"from_attributes": True}
class HierarchyZoneResponse(BaseModel): id: str; floor_id: str | None = None; floor_name: str | None = None; name: str; description: str | None; floor_plan_polygon: RiskZoneFloorPlanPolygon | None = None; max_risk_level: str | None = None; effective_color: str | None = None; objects: list[HierarchyObjectResponse] = []; model_config = {"from_attributes": True}

class MigrationPreviewItem(BaseModel):
    source_id: str
    source_name: str
    source_location: str | None = None
    source_categories: list[str] = []
    suggested_zone: str = "历史风险源"
    suggested_object: str = ""
    suggested_event: str = "安全生产事故"
    suggested_params: dict[str, int] = {"l": 3, "s": 3}
    control_measures: str | None = None


class MigrationPreviewResponse(BaseModel):
    items: list[MigrationPreviewItem]
    total: int
    migrated_total: int = 0


class MigrationExecuteItem(BaseModel):
    source_id: str
    zone_name: str = Field(min_length=1)
    object_name: str = Field(min_length=1)
    accident_type: str = Field(min_length=1)
    method_params: dict[str, int] = {"l": 3, "s": 3}

    @field_validator("method_params", mode="before")
    @classmethod
    def _validate_method_params(cls, v: dict) -> dict:
        if not isinstance(v, dict):
            raise ValueError("method_params must be a dict")
        for key in ("l", "s"):
            if v.get(key) is not None:
                value = v[key]
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not (1 <= value <= 5)
                ):
                    raise ValueError(f"{key} must be a number between 1 and 5")
        return v


class MigrationExecuteRequest(BaseModel):
    mappings: list[MigrationExecuteItem]


class MigrationExecuteResponse(BaseModel):
    migrated: int = 0
    skipped: int = 0
    created: dict[str, int] = {}

class SmartGuideMeasure(BaseModel):
    description: str
    measure_category: str = ""
    measure_type: str | None = None
    check_items: list[dict] = []
    model_config = {"extra": "allow"}

class SmartGuideEvent(BaseModel):
    accident_type: str
    description: str | None = None
    risk_level: str | None = None
    risk_score: str | None = None
    method_type: str = "LS"
    method_params: dict = {}
    measures: list[SmartGuideMeasure] = []
    model_config = {"extra": "allow"}

class SmartGuideUnit(BaseModel):
    name: str
    unit_type: str | None = None
    description: str | None = None
    events: list[SmartGuideEvent] = []
    model_config = {"extra": "allow"}

class SmartGuideObject(BaseModel):
    name: str
    category: str | None = None
    is_risk_point: bool = False
    units: list[SmartGuideUnit] = []
    events: list[SmartGuideEvent] = []
    model_config = {"extra": "allow"}

class SmartGuideZone(BaseModel):
    name: str
    description: str | None = None
    objects: list[SmartGuideObject] = []
    model_config = {"extra": "allow"}

class SmartGuideRequest(BaseModel): description: str
class SmartGuideResponse(BaseModel): hierarchy: list[SmartGuideZone]; summary: dict = {}
class MethodPreviewRequest(BaseModel): method_id: str; params: dict
class MethodPreviewResponse(BaseModel): risk_level: str; risk_score: str; action: str; deadline: str


class FourColorDraftPolygon(BaseModel):
    id: str
    label: str | None = None
    points: list[RiskPolygonPoint] = Field(min_length=3)


class FourColorDraftZone(BaseModel):
    client_id: str
    name: str
    risk_level: Literal["重大", "较大", "一般", "低"]
    color: str
    suspected: bool = False
    suggested_name: str | None = None
    ai_hint: str | None = None
    polygons: list[FourColorDraftPolygon] = Field(min_length=1)


class FourColorExcludedItem(BaseModel):
    color: str
    reason: Literal["legend", "thin", "border_frame", "tiny"]
    polygons: list[FourColorDraftPolygon]


class FourColorTextItem(BaseModel):
    points: list[RiskPolygonPoint]
    text: str
    confidence: float


class FourColorAnalyzeResponse(BaseModel):
    preview_url: str
    canvas_width: int
    canvas_height: int
    zones: list[FourColorDraftZone]
    warnings: list[str] = []
    excluded: list[FourColorExcludedItem] = []
    texts: list[FourColorTextItem] = []


class FourColorCommitPolygon(BaseModel):
    points: list[RiskPolygonPoint] = Field(min_length=3)


class FourColorCommitZone(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    risk_level: Literal["重大", "较大", "一般", "低"]
    polygons: list[FourColorCommitPolygon] = Field(min_length=1)


class FourColorCommitRequest(BaseModel):
    file_token: str
    zones: list[FourColorCommitZone] = Field(min_length=1, max_length=200)
    replace_existing: bool = True


class FourColorCommitResponse(BaseModel):
    floor: FloorResponse
    zones: list[RiskZoneResponse]
