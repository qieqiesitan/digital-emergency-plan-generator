from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/emergency_plan"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENCRYPTION_KEY: str = "a" * 32
    EXPORT_DIR: str = "./exports"

    # 业务中台接入配置
    YWT_GATEWAY_URL: str = "http://localhost:8088"
    YWT_API_KEY: str = ""
    YWT_SYS_CODE: str = "emergency-plan"
    YWT_JWT_SECRET: str = "yewuzhongtai-jwt-secret-key-2024-min-256-bits!!"
    YWT_AUTH_WHITELIST: str = "/api/v1/auth/register,/api/v1/auth/login,/api/health"

    # 外部系统接入（PROTEGO 商城）
    EXTERNAL_API_HMAC_SECRET: str = ""
    PROTEGO_CALLBACK_URL: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()
