from pydantic import BaseModel


class DataDictCreate(BaseModel):
    dict_type: str
    code: str
    label: str
    value: dict = {}
    sort_order: int = 0
    enabled: bool = True
    description: str | None = None


class DataDictUpdate(BaseModel):
    label: str | None = None
    value: dict | None = None
    sort_order: int | None = None
    enabled: bool | None = None
    description: str | None = None
