from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ThirdPartyConfig(Base):
    """Third-party (vendor) configuration stored in the database.

    Values are stored encrypted via ``app.services.secret_utils`` by default.
    """

    __tablename__ = "third_party_config"

    config_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    config_type: Mapped[str] = mapped_column(String(16), default="secret", nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(512))
    updated_by: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
