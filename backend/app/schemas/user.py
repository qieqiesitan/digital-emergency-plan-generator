from app.schemas.common import DatetimeStr
from typing import Optional
from pydantic import BaseModel, field_validator
from app.schemas.auth import validate_password_strength

class UserResponse(BaseModel):
    id: str; email: str; name: str; role: str; created_at: DatetimeStr
    model_config = {"from_attributes": True}

class UpdateProfileRequest(BaseModel):
    name: str

class ChangePasswordRequest(BaseModel):
    old_password: str; new_password: str; new_password_confirm: str

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v):
        return validate_password_strength(v)
