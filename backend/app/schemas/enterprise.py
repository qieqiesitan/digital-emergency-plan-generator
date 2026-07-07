from app.schemas.common import DatetimeStr
from typing import Optional
from pydantic import BaseModel

class OrgMember(BaseModel):
    role: str
    name: str
    position: str = ""
    phone: str = ""
    responsibilities: str = ""

class OrgGroup(BaseModel):
    group_key: str
    group_name: str
    members: list[OrgMember] = []

class NearbyUnit(BaseModel):
    name: str
    direction: str = ""
    distance_m: float = 0
    main_risk: str = ""

class SensitiveTarget(BaseModel):
    name: str
    direction: str = ""
    distance_m: float = 0
    type: str = ""

class SurroundingInfo(BaseModel):
    nearby_units: list[NearbyUnit] = []
    sensitive_targets: list[SensitiveTarget] = []
    traffic_info: str = ""

class EnterpriseCreate(BaseModel):
    name: str
    address: str | None = None
    industry: str | None = None
    business_scope: str | None = None
    employee_count: int | None = None
    credit_code: str | None = None
    legal_representative: str | None = None
    economic_type: str | None = None
    established_date: str | None = None
    registered_capital: float | None = None
    phone: str | None = None
    fax: str | None = None
    postal_code: str | None = None
    land_area: float | None = None
    building_area: float | None = None
    safety_officer: str | None = None
    safety_officer_phone: str | None = None
    safety_staff_count: int | None = None
    safety_standardization: str | None = None
    fire_approval: str | None = None
    fire_approval_date: str | None = None
    last_plan_filing_date: str | None = None
    last_plan_filing_authority: str | None = None
    main_products: str | None = None
    annual_capacity: str | None = None
    hazardous_chemicals: str | None = None
    special_equipment: str | None = None
    building_overview: str | None = None
    floor_plan_url: str | None = None
    gis_lat: float | None = None
    gis_lng: float | None = None

class EnterpriseUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    industry: str | None = None
    business_scope: str | None = None
    employee_count: int | None = None
    credit_code: str | None = None
    legal_representative: str | None = None
    economic_type: str | None = None
    established_date: str | None = None
    registered_capital: float | None = None
    phone: str | None = None
    fax: str | None = None
    postal_code: str | None = None
    land_area: float | None = None
    building_area: float | None = None
    safety_officer: str | None = None
    safety_officer_phone: str | None = None
    safety_staff_count: int | None = None
    safety_standardization: str | None = None
    fire_approval: str | None = None
    fire_approval_date: str | None = None
    last_plan_filing_date: str | None = None
    last_plan_filing_authority: str | None = None
    main_products: str | None = None
    annual_capacity: str | None = None
    hazardous_chemicals: str | None = None
    special_equipment: str | None = None
    building_overview: str | None = None
    floor_plan_url: str | None = None
    gis_lat: float | None = None
    gis_lng: float | None = None

class EnterpriseResponse(BaseModel):
    id: str
    name: str
    address: str | None
    industry: str | None
    business_scope: str | None
    employee_count: int | None
    credit_code: str | None = None
    legal_representative: str | None = None
    economic_type: str | None = None
    established_date: DatetimeStr | None = None
    registered_capital: float | None = None
    phone: str | None = None
    fax: str | None = None
    postal_code: str | None = None
    land_area: float | None = None
    building_area: float | None = None
    safety_officer: str | None = None
    safety_officer_phone: str | None = None
    safety_staff_count: int | None = None
    safety_standardization: str | None = None
    fire_approval: str | None = None
    fire_approval_date: DatetimeStr | None = None
    last_plan_filing_date: DatetimeStr | None = None
    last_plan_filing_authority: str | None = None
    main_products: str | None = None
    annual_capacity: str | None = None
    hazardous_chemicals: str | None = None
    special_equipment: str | None = None
    building_overview: str | None
    org_structure: list = []
    surrounding_info: dict | None = None
    floor_plan_url: str | None = None
    gis_lat: float | None = None
    gis_lng: float | None = None
    risk_sources_count: int = 0
    resources_count: int = 0
    plans_count: int = 0
    created_at: DatetimeStr
    updated_at: DatetimeStr

    model_config = {"from_attributes": True}

# ── Autofill ──

class AutofillRequest(BaseModel):
    name: str

class AutofillResponse(BaseModel):
    name: str | None = None
    fields: dict = {}
    error: str | None = None  # "rate_limited" | "credits_exhausted" | "not_found" | "network_error"
