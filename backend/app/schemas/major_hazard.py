"""重大危险源 API 出入参。"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class UnitIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    unit_type: str = Field(pattern="^(production|storage)$")
    boundary_desc: Optional[str] = None
    floor_id: Optional[str] = None
    polygon: Optional[dict] = None
    address: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    department: Optional[str] = None
    responsible_person: Optional[str] = None
    responsible_phone: Optional[str] = None
    risk_object_id: Optional[str] = None
    is_active: bool = True


class UnitOut(BaseModel):
    id: str
    enterprise_id: str
    name: str
    unit_type: str
    address: Optional[str] = None
    department: Optional[str] = None
    responsible_person: Optional[str] = None
    responsible_phone: Optional[str] = None
    risk_object_id: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UnitChemicalIn(BaseModel):
    chemical_name: str = Field(min_length=1, max_length=500)
    chemical_id: Optional[str] = None
    physical_state: Optional[str] = None
    storage_location: Optional[str] = None
    q_design_max: Decimal = Field(ge=0)
    q_actual: Optional[Decimal] = Field(default=None, ge=0)
    critical_quantity_t: Decimal = Field(gt=0)
    beta: Decimal = Field(gt=0)
    beta_source: str = Field(default="manual", pattern="^(table3|table4|manual)$")


class UnitChemicalOut(UnitChemicalIn):
    id: str
    unit_id: str

    model_config = {"from_attributes": True}


class ComputeIn(BaseModel):
    exposed_population: int = Field(ge=0)


class CalculationOut(BaseModel):
    id: str
    seq: int
    s_value: Decimal
    r_value: Decimal
    alpha: Decimal
    exposed_population: int
    is_major_hazard: bool
    level: Optional[str] = None
    formula_version: str
    calculated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CriticalQuantityOut(BaseModel):
    chemical_name: str
    alias: Optional[str] = None
    cas_no: Optional[str] = None
    critical_t: Optional[Decimal] = None
    critical_note: Optional[str] = None
    table_no: str
    source_page: Optional[int] = None

    model_config = {"from_attributes": True}


class EvidenceIn(BaseModel):
    """挂载法规依据的请求项。"""

    article_anchor: str = Field(min_length=1, max_length=200)
    regulation_id: Optional[str] = Field(default=None, max_length=64)
    relation: str = Field(default="依据", max_length=20)
    note: Optional[str] = None


class RecordIn(BaseModel):
    """档案与备案入参。未提供的字段保持原值。"""

    hazard_code: Optional[str] = Field(default=None, max_length=64)
    filing_status: Optional[str] = Field(default=None, max_length=20)
    filing_no: Optional[str] = Field(default=None, max_length=100)
    filing_date: Optional[date] = None
    chief_name: Optional[str] = None
    chief_post: Optional[str] = None
    chief_phone: Optional[str] = None
    tech_name: Optional[str] = None
    tech_post: Optional[str] = None
    tech_phone: Optional[str] = None
    oper_name: Optional[str] = None
    oper_post: Optional[str] = None
    oper_phone: Optional[str] = None
    attachments: Optional[dict] = None
    completeness: Optional[dict] = None


class RecordOut(BaseModel):
    id: str
    unit_id: str
    enterprise_id: str
    hazard_code: Optional[str] = None
    filing_status: str
    filing_no: Optional[str] = None
    filing_date: Optional[date] = None
    chief_name: Optional[str] = None
    chief_post: Optional[str] = None
    chief_phone: Optional[str] = None
    tech_name: Optional[str] = None
    tech_post: Optional[str] = None
    tech_phone: Optional[str] = None
    oper_name: Optional[str] = None
    oper_post: Optional[str] = None
    oper_phone: Optional[str] = None
    attachments: dict = Field(default_factory=dict)
    completeness: dict = Field(default_factory=dict)

    model_config = {"from_attributes": True}
