from app.schemas.common import DatetimeStr
from typing import Optional
from pydantic import BaseModel, Field

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

class EnterpriseBase(BaseModel):
    """企业共享字段。Create/Update/Response 继承此基类，消除字段重复定义。"""
    # P1 加固：max_length 与 enterprises 表列宽一致，超长输入在 schema 层即 422，
    # 不再等到 asyncpg 抛 DataError 500。
    name: str = Field(min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    industry: str | None = Field(default=None, max_length=255)
    business_scope: str | None = Field(default=None, max_length=1000)
    employee_count: int | None = Field(default=None, ge=0)
    credit_code: str | None = Field(default=None, max_length=50)
    legal_representative: str | None = Field(default=None, max_length=100)
    economic_type: str | None = Field(default=None, max_length=50)
    established_date: str | None = None
    registered_capital: float | None = None
    phone: str | None = Field(default=None, max_length=50)
    fax: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=10)
    land_area: float | None = None
    building_area: float | None = None
    safety_officer: str | None = Field(default=None, max_length=100)
    safety_officer_phone: str | None = Field(default=None, max_length=50)
    safety_staff_count: int | None = Field(default=None, ge=0)
    safety_standardization: str | None = Field(default=None, max_length=20)
    fire_approval: str | None = Field(default=None, max_length=50)
    fire_approval_date: str | None = None
    last_plan_filing_date: str | None = None
    last_plan_filing_authority: str | None = Field(default=None, max_length=200)
    main_products: str | None = Field(default=None, max_length=2000)
    annual_capacity: str | None = Field(default=None, max_length=500)
    hazardous_chemicals: str | None = Field(default=None, max_length=2000)
    special_equipment: str | None = Field(default=None, max_length=2000)
    building_overview: str | None = Field(default=None, max_length=4000)
    floor_plan_url: str | None = Field(default=None, max_length=500)
    gis_lat: float | None = None
    gis_lng: float | None = None


class EnterpriseCreate(EnterpriseBase):
    """创建企业。name 从 EnterpriseBase 继承为必填。"""
    pass


class EnterpriseUpdate(EnterpriseBase):
    """更新企业。所有字段均为可选，包括 name。"""
    name: str | None = None  # 覆盖为可选

class EnterpriseResponse(EnterpriseBase):
    """企业响应。包含 EnterpriseBase 所有字段 + 额外响应字段。

    注意：established_date / fire_approval_date / last_plan_filing_date 在
    Base 中为 str（输入态），此处覆盖为 DatetimeStr（输出序列化格式），
    二者类型不同，不可合并，必须保留覆盖。
    """
    id: str
    established_date: DatetimeStr | None = None
    fire_approval_date: DatetimeStr | None = None
    last_plan_filing_date: DatetimeStr | None = None
    org_structure: list = []
    surrounding_info: dict | None = None
    risk_sources_count: int = 0
    risk_events_count: int = 0
    resources_count: int = 0
    plans_count: int = 0
    completion: dict | None = None
    created_at: DatetimeStr
    updated_at: DatetimeStr

    model_config = {"from_attributes": True}

class AutofillRequest(BaseModel):
    name: str

class AutofillResponse(BaseModel):
    name: str | None = None
    fields: dict = {}
    error: str | None = None  # "rate_limited" | "credits_exhausted" | "not_found" | "network_error"
