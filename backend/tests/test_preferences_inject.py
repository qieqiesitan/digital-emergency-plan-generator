"""test_preferences_inject.py — 偏好注入 system prompt + 工作流/偏好工具注册（阶段3 任务6）。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.chat import (
    CHAT_SYSTEM_PROMPT,
    CHAT_TOOLS,
    build_system_prompt_with_prefs,
)


def test_prefs_injected_into_system_prompt():
    prefs = {"style_preference": "practical", "detail_level": "concise"}
    sp = build_system_prompt_with_prefs(prefs)
    assert "practical" in sp or "实用" in sp
    assert "concise" in sp or "简洁" in sp


def test_no_prefs_returns_base_prompt_unchanged():
    """保守：无有效偏好时原样返回，不追加任何偏好段。"""
    assert build_system_prompt_with_prefs({}) == CHAT_SYSTEM_PROMPT
    assert build_system_prompt_with_prefs(None) == CHAT_SYSTEM_PROMPT
    assert build_system_prompt_with_prefs(
        {"style_preference": None, "detail_level": "", "report_topics": []}
    ) == CHAT_SYSTEM_PROMPT


def test_workflow_tools_registered():
    names = {t["function"]["name"] for t in CHAT_TOOLS}
    assert {"run_workflow", "get_workflow_progress",
            "get_preferences", "set_preferences"} <= names


@pytest.mark.asyncio
async def test_chat_endpoint_injects_prefs_into_system_prompt():
    """chat 端点：_rebuild 历史后、截断前把偏好段注入第一条 system 消息。"""
    from app.routers.chat import chat
    from app.schemas.chat import ChatRequest

    db = AsyncMock()
    user = MagicMock(id="u1")
    body = ChatRequest(conversation_id="c1", message="帮我开始")
    llm_plain = {"choices": [{"message": {"content": "好的", "tool_calls": []}}]}

    with patch("app.services.ai_config_service.get_system_ai_config",
               return_value=MagicMock()), \
         patch("app.routers.chat._load_history_rows",
               new=AsyncMock(return_value=([], []))), \
         patch("app.routers.chat.get_preferences",
               new=AsyncMock(return_value={"style_preference": "practical"})), \
         patch("app.routers.chat._call_llm",
               new=AsyncMock(return_value=llm_plain)) as llm_mock, \
         patch("app.routers.chat._save_messages", new=AsyncMock()):
        resp = await chat(body, user, db)
        raw = "".join([chunk async for chunk in resp.body_iterator])

    assert "done" in raw
    sent = llm_mock.await_args.args[0]
    assert sent[0]["role"] == "system"
    assert "practical" in sent[0]["content"] or "实用" in sent[0]["content"]


@pytest.mark.asyncio
async def test_chat_endpoint_prefs_survive_truncation():
    """长历史触发截断压缩后，偏好段仍在第一条 system 消息（截断保留 system）。"""
    from app.routers.chat import chat
    from app.schemas.chat import ChatRequest

    db = AsyncMock()
    user = MagicMock(id="u1")
    body = ChatRequest(conversation_id="c1", message="继续")
    row = MagicMock(role="user", content="很长的历史" * 4000)
    llm_plain = {"choices": [{"message": {"content": "ok", "tool_calls": []}}]}

    with patch("app.services.ai_config_service.get_system_ai_config",
               return_value=MagicMock()), \
         patch("app.routers.chat._load_history_rows",
               new=AsyncMock(return_value=([row], []))), \
         patch("app.routers.chat.get_preferences",
               new=AsyncMock(return_value={"detail_level": "concise"})), \
         patch("app.routers.chat._call_llm",
               new=AsyncMock(return_value=llm_plain)) as llm_mock, \
         patch("app.routers.chat._save_messages", new=AsyncMock()):
        resp = await chat(body, user, db)
        raw = "".join([chunk async for chunk in resp.body_iterator])

    sent = llm_mock.await_args.args[0]
    systems = [m for m in sent if m["role"] == "system"]
    assert len(systems) >= 2  # 截断产生了历史摘要
    assert "concise" in systems[0]["content"] or "简洁" in systems[0]["content"]
