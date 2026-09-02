from pydantic import BaseModel, EmailStr, Field, field_validator

class RegisterRequest(BaseModel):
    email: str
    # 安全加固（S9）：注册/重置密码统一最小长度校验
    password: str = Field(min_length=6)
    password_confirm: str = Field(min_length=6)
    name: str

    @field_validator("password_confirm")
    @classmethod
    def passwords_match(cls, v, info):
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("两次输入的密码不一致")
        return v

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class RefreshRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=6)
