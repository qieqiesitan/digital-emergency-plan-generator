from datetime import datetime
from uuid import uuid4
from sqlalchemy import JSON, String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class ChatToolCall(Base):
    __tablename__ = "chat_tool_calls"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False, index=True)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False)
    fn_name: Mapped[str] = mapped_column(String(100), nullable=False)
    fn_args: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
