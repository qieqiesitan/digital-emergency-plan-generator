"""LLM 调用留痕 ORM。

一行 = 一次供应商调用。用于回答三个问题：这个月花了多少、哪几次失败了、
用户投诉的那次是不是流被截断了。

为什么现在才建：全库此前 token_usage|llm_call|ai_call_log|usage_log 零命中——
任何 AI 调用都没有记录，出问题只能靠猜。
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LlmCallLog(Base):
    __tablename__ = "llm_call_logs"
    __table_args__ = (Index("idx_llm_log_module_time", "module", "created_at"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    module: Mapped[str] = mapped_column(String(64), nullable=False)
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(120))
    prompt_version: Mapped[Optional[str]] = mapped_column(String(64))
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_code: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 流式响应未收到 [DONE] 即被截断。这类调用 success 可能仍为 True，
    # 但结果是半截的——必须单独标记，否则永远查不出来。
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    enterprise_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
