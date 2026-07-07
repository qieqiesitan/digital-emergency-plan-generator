from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.common import DatetimeStr

class PermissionResponse(BaseModel):
    id: str; code: str; name: str; resource: str; action: str; category: str = "action"
    model_config = {"from_attributes": True}

class RoleResponse(BaseModel):
    id: str; name: str; code: str; description: Optional[str] = None
    is_system: bool = False
    permissions: list[PermissionResponse] = []
    model_config = {"from_attributes": True}

class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    code: str = Field(..., min_length=1, max_length=30, pattern=r'^[a-z_]+$')
    description: Optional[str] = Field(default=None, max_length=200)
    permission_ids: list[str] = []

class RoleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=200)
    permission_ids: Optional[list[str]] = None

class AdminUserCreate(BaseModel):
    email: str = Field(..., max_length=255)
    name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=6)
    role: str = Field(default="user", max_length=30)

class AdminUserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    role: Optional[str] = Field(default=None, max_length=30)

class AdminUserResponse(BaseModel):
    id: str; email: str; name: str; role: str; created_at: Optional[DatetimeStr] = None
    model_config = {"from_attributes": True}
