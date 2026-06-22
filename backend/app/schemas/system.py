from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ConfigItem(BaseModel):
    id: int
    config_key: str
    config_value: str
    config_type: str = "string"
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ConfigCreate(BaseModel):
    config_key: str = Field(..., min_length=1, max_length=128)
    config_value: str
    config_type: str = Field(default="string", pattern="^(string|int|float|bool|json)$")
    description: Optional[str] = Field(default=None, max_length=512)


class ConfigUpdate(BaseModel):
    config_value: str
    config_type: Optional[str] = None
    description: Optional[str] = None
