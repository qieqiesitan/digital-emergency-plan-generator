from datetime import datetime
from uuid import uuid4
from sqlalchemy import BigInteger, Sequence, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

# 会话消息序号序列：必须用 Sequence 声明，create_all 才会先建序列再建表。
# 2026-09-19 演练发现：此前写成 server_default=text("nextval('chat_messages_seq')")，
# 而没有任何地方创建该序列 —— **空库全新安装会直接启动失败**
# （UndefinedTableError: relation "chat_messages_seq" does not exist）。
chat_messages_seq = Sequence("chat_messages_seq")


class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), default="新对话")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "assistant" | "function"
    content: Mapped[str] = mapped_column(Text, default="")
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    seq: Mapped[int] = mapped_column(
        BigInteger, chat_messages_seq, nullable=False,
        server_default=chat_messages_seq.next_value(),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
