import re

from pydantic import BaseModel, Field, field_validator


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


# P1-9：常见弱密码黑名单（纯键盘序列/纯数字/纯字母/占位）
COMMON_WEAK_PASSWORDS = {
    "123456", "12345678", "123456789", "1234567890", "password",
    "password1", "qwerty", "qwerty123", "abc123", "abc12345",
    "111111", "000000", "123123", "654321", "admin123", "test1234",
    "iloveyou", "monkey", "dragon", "welcome", "sunshine",
}


def validate_password_strength(v: str) -> str:
    """密码复杂度：>=8 位、含字母和数字、非常见弱密码。"""
    if len(v) < 8:
        raise ValueError("密码长度至少 8 位")
    # bcrypt 仅使用前 72 字节：超长密码会被静默截断，等价降级（QA S16）
    if len(v.encode("utf-8")) > 72:
        raise ValueError("密码长度不能超过 72 字节")
    lowered = v.lower()
    if lowered in COMMON_WEAK_PASSWORDS:
        raise ValueError("密码过于常见，请更换更复杂的密码")
    has_letter = any(c.isalpha() for c in v)
    has_digit = any(c.isdigit() for c in v)
    if not (has_letter and has_digit):
        raise ValueError("密码必须同时包含字母和数字")
    return v


class RegisterRequest(BaseModel):
    email: str
    # 安全加固（S9）：注册/重置密码统一最小长度校验
    password: str
    password_confirm: str
    name: str

    @field_validator("email")
    @classmethod
    def email_format(cls, v):
        if not EMAIL_RE.match(v):
            raise ValueError("邮箱格式不正确")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        return validate_password_strength(v)

    @field_validator("password_confirm")
    @classmethod
    def passwords_match(cls, v, info):
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("两次输入的密码不一致")
        if "password" in info.data:
            validate_password_strength(v)
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
    new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v):
        return validate_password_strength(v)
