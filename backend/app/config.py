from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/emergency_plan"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENCRYPTION_KEY: str = "a" * 32
    EXPORT_DIR: str = "./exports"

    # 外部系统接入（PROTEGO 商城）
    EXTERNAL_API_HMAC_SECRET: str = ""
    PROTEGO_CALLBACK_URL: str = ""

    # 企查查智能体平台
    QCC_API_KEY: str = ""
    QCC_API_KEY_FALLBACK: str = ""
    QCC_ENDPOINT: str = "https://agent.qcc.com/mcp/company/stream"

    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()
