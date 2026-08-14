from typing import Literal
from pydantic import BaseModel, Field


class OrgMember(BaseModel):
    name: str
    user_id: str | None = None
    position: str | None = None


class OrgNode(BaseModel):
    id: str
    type: Literal["dept", "team", "position"]
    name: str
    parent_id: str | None = None
    members: list[OrgMember] = Field(default_factory=list)


class OrgTreeUpdate(BaseModel):
    nodes: list[OrgNode]


class MemberCreate(BaseModel):
    user_id: str
    org_node_id: str | None = None
    position: str | None = None
    role: Literal["enterprise_admin", "team_leader", "member"] = "member"


class MemberUpdate(BaseModel):
    org_node_id: str | None = None
    position: str | None = None
    role: Literal["enterprise_admin", "team_leader", "member"] | None = None
    enabled: bool | None = None


class MemberResponse(BaseModel):
    id: str
    enterprise_id: str
    user_id: str
    email: str | None = None
    name: str | None = None
    org_node_id: str | None = None
    position: str | None = None
    role: str
    enabled: bool
    model_config = {"from_attributes": True}
