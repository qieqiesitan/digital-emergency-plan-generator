"""test_chat_tool_call_model.py — ChatToolCall 模型映射。"""
from app.models.chat_tool_call import ChatToolCall


def test_model_table_and_columns():
    assert ChatToolCall.__tablename__ == "chat_tool_calls"
    for col in ("id", "conversation_id", "round_no", "fn_name", "fn_args",
                "result", "status", "duration_ms", "created_at"):
        assert col in ChatToolCall.__table__.columns


def test_exported_from_models_package():
    from app.models import ChatToolCall as Exported
    assert Exported is ChatToolCall
