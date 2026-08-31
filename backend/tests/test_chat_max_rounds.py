"""test_chat_max_rounds.py — 超轮数部分成功总结。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.chat import _build_final_summary_prompt


def test_build_final_summary_prompt_mentions_partial():
    p = _build_final_summary_prompt(completed=["get_dashboard"], remaining=["generate_plan_content"])
    assert "已完成" in p and "未完成" in p
