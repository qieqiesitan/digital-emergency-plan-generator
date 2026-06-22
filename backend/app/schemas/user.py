from app.schemas.common import DatetimeStr
from typing import Optional
from pydantic import BaseModel

class UserResponse(BaseModel):
    id: str; email: str; name: str; role: str; created_at: DatetimeStr
    model_config = {"from_attributes": True}

class UpdateProfileRequest(BaseModel):
    name: str

class ChangePasswordRequest(BaseModel):
    old_password: str; new_password: str; new_password_confirm: str
