from pydantic import BaseModel, Field


class DataDictCreate(BaseModel):
    dict_type: str
    code: str
    label: str
    value: dict = Field(default_factory=dict)
    sort_order: int = 0
    enabled: bool = True
    description: str | None = None


class DataDictUpdate(BaseModel):
    label: str | None = None
    value: dict | None = None
    sort_order: int | None = None
    enabled: bool | None = None
    description: str | None = None


class DataDictResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    dict_type: str
    code: str
    label: str
    value: dict = Field(default_factory=dict)
    scope: str
    enterprise_id: str | None = None
    sort_order: int = 0
    enabled: bool = True
    is_system: bool = False
    description: str | None = None
