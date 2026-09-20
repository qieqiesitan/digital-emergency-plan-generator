from typing import Literal
from pydantic import BaseModel, Field, field_validator


class OrgMember(BaseModel):
    name: str
    user_id: str | None = None
    position: str | None = None
    # 透传 onboarding 等来源的扩展字段（如 role/phone），整树保存时不静默丢弃
    model_config = {"extra": "allow"}


class OrgNode(BaseModel):
    id: str
    type: Literal["dept", "team", "position"]
    name: str
    parent_id: str | None = None
    members: list[OrgMember] = Field(default_factory=list)
    # 透传扩展字段（如 description），避免整树保存后清除下游数据
    model_config = {"extra": "allow"}


class OrgTreeUpdate(BaseModel):
    nodes: list[OrgNode]


class OrgSuggestRequest(BaseModel):
    """AI 建树补充要求（可选，供用户补充企业特殊信息辅助分析）。"""

    extra_requirements: str = ""


class MemberCreate(BaseModel):
    user_id: str | None = None
    name: str = ""
    phone: str | None = None
    email: str | None = None
    org_node_id: str | None = None
    # 兼岗节点：主岗仍用 org_node_id，额外任职放这里（写 member_positions）
    extra_node_ids: list[str] = Field(default_factory=list)
    position: str | None = None
    # 特种作业证照：[{"type": "...", "no": "...", "valid_to": "YYYY-MM-DD"}]
    # 开票时用于自动拼接「动火人及证书编号」「电工及证书编号」
    certificates: list[dict] = Field(default_factory=list)
    role: Literal["enterprise_admin", "team_leader", "member"] = "member"


class MemberUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    org_node_id: str | None = None
    # None 语义 = 不改任职；传数组则整体替换兼岗（主岗仍由 org_node_id 决定）
    extra_node_ids: list[str] | None = None
    position: str | None = None
    # None 语义 = 不改证照；传数组则整体替换
    certificates: list[dict] | None = None
    role: Literal["enterprise_admin", "team_leader", "member"] | None = None
    enabled: bool | None = None


class MemberResponse(BaseModel):
    id: str
    enterprise_id: str
    user_id: str | None = None
    email: str | None = None
    name: str | None = None
    phone: str | None = None
    org_node_id: str | None = None
    # 全部任职（主岗 + 兼岗），由 member_positions 提供，按主岗优先排序
    positions: list[dict] = Field(default_factory=list)
    position: str | None = None
    certificates: list[dict] = Field(default_factory=list)
    role: str
    enabled: bool
    model_config = {"from_attributes": True}

    @field_validator("certificates", mode="before")
    @classmethod
    def _certificates_default_empty(cls, value):
        """证书列在库里是 NOT NULL DEFAULT '[]'，但容错 None（老对象/未刷新实例）。"""
        return value or []
