import logging
import os
import secrets

from pydantic_settings import BaseSettings
from pydantic import field_validator

logger = logging.getLogger(__name__)


# 已知弱默认密钥黑名单（docker-compose 历史默认值 / 代码开发默认值）
WEAK_SECRET_KEYS = {
    "",
    "dev-secret-key-change-in-production",
    "emergency-plan-docker-secret-key-2026",
}


def is_weak_secret_key(key: str) -> bool:
    """JWT 密钥安全性检查：拒绝空值、已知弱默认值、长度 < 32 字节。"""
    return key in WEAK_SECRET_KEYS or len(key.encode("utf-8")) < 32


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/emergency_plan"
    # 安全加固（QA P0-3）：默认值置空，由模块底部在缺少显式环境变量时
    # 自动生成每次启动唯一的强随机密钥；显式配置的弱值直接拒绝。
    SECRET_KEY: str = ""
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

    @field_validator("SECRET_KEY")
    @classmethod
    def _reject_weak_secret(cls, v: str) -> str:
        if v and is_weak_secret_key(v):
            raise ValueError(
                "SECRET_KEY 过弱（已知默认值或少于 32 字节）。"
                "请通过环境变量注入强随机密钥，例如："
                "python -c \"import secrets; print(secrets.token_hex(48))\""
            )
        return v


settings = Settings()

if not os.environ.get("SECRET_KEY"):
    # 开发/测试环境未显式注入时：生成每次启动唯一的强随机密钥。
    # 副作用：每次重启旧 JWT 全部失效（本地开发可接受；生产必须显式注入）。
    settings.SECRET_KEY = secrets.token_hex(48)
    logger.warning(
        "SECRET_KEY 未通过环境变量显式设置，已自动生成随机密钥（进程重启后旧 token 失效）。"
        "生产部署必须显式配置 SECRET_KEY。"
    )
