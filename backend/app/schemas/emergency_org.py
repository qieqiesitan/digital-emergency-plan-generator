"""应急组织接口契约。字段名与前端 types/emergencyOrg.ts 一一对应。"""

from pydantic import BaseModel, Field


class EmergencyRoleIn(BaseModel):
    id: str | None = None
    name: str
    duties: str | None = None
    sort_order: int = 0
    is_required: bool = False
    member_ids: list[str] = Field(default_factory=list)


class EmergencyUnitIn(BaseModel):
    id: str | None = None
    parent_id: str | None = None
    name: str
    duties: str | None = None
    sort_order: int = 0
    roles: list[EmergencyRoleIn] = Field(default_factory=list)


class EmergencyOrgUpdate(BaseModel):
    units: list[EmergencyUnitIn] = Field(default_factory=list)


class EmergencyMemberBrief(BaseModel):
    id: str
    name: str | None = None
    phone: str | None = None
    position: str | None = None
    email: str | None = None
    org_node_id: str | None = None


class EmergencyRoleOut(EmergencyRoleIn):
    id: str
    member_ids: list[str] = Field(default_factory=list)
    members: list[EmergencyMemberBrief] = Field(default_factory=list)


class EmergencyUnitOut(EmergencyUnitIn):
    id: str
    roles: list[EmergencyRoleOut] = Field(default_factory=list)
