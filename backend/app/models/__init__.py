"""模型包转出口：导入本包即完成全部 ORM 表注册（外键/关系按名解析依赖它）。

这些导入是**有意的转出口**（`app.models.ChatToolCall` 等被路由/测试直接引用），
因此显式声明 `__all__`，避免被 F401 当作无用导入删除。
"""

from app.models.prompt import PromptTemplate
from app.models.chat import ChatConversation, ChatMessage
from app.models.password_reset import PasswordResetToken
from app.models.third_party_config import ThirdPartyConfig
from app.models.schema_migration import SchemaMigration
from app.models.chat_tool_call import ChatToolCall

__all__ = [
    "PromptTemplate",
    "ChatConversation",
    "ChatMessage",
    "PasswordResetToken",
    "ThirdPartyConfig",
    "SchemaMigration",
    "ChatToolCall",
]
