from pydantic import BaseModel
from datetime import datetime


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "function"
    content: str | None = None
    name: str | None = None  # function name when role=function


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    conversation_id: str | None = None  # 关联已有对话，不传则自动创建


class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime
