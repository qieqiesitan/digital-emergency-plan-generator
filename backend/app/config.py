import logging
import os

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/emergency_plan"
    # 安全加固（S5）：生产必须通过环境变量显式提供；缺失时保留开发默认值并告警，
    # 避免破坏本地开发与测试环境（详见模块底部校验）。
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENCRYPTION_KEY: str = "a" * 32
    EXPORT_DIR: str = "./exports"
    # CORS 白名单（逗号分隔）；未配置时 main.py 回退本地开发源
    CORS_ORIGINS: str = ""

    # 外部系统接入（PROTEGO 商城）
    EXTERNAL_API_HMAC_SECRET: str = ""
    PROTEGO_CALLBACK_URL: str = ""

    # 企查查智能体平台
    QCC_API_KEY: str = ""
    QCC_API_KEY_FALLBACK: str = ""
    QCC_ENDPOINT: str = "https://agent.qcc.com/mcp/company/stream"

    # 高德开放平台
    AMAP_KEY: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()

if not os.environ.get("SECRET_KEY"):
    logger.warning(
        "SECRET_KEY 未通过环境变量显式设置，将使用开发默认值"
        "（仅限本地/测试环境；生产部署必须配置 SECRET_KEY，否则存在 JWT 伪造风险）"
    )
