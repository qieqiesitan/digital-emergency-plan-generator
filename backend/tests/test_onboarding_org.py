import asyncio
from unittest.mock import AsyncMock

from app.services.onboarding_service import generate_org_candidates


def test_generate_org_candidates_parses_llm_json(monkeypatch):
    async def fake_llm(messages, ai_config, timeout=120):
        return '{"groups": [{"group_key": "cmd", "group_name": "应急救援指挥部", "members": [{"role": "总指挥", "name": "", "phone": ""}]}, {"group_key": "rescue", "group_name": "抢险救援组", "members": []}]}'
    monkeypatch.setattr("app.services.onboarding_service.llm_text_completion", fake_llm)
    db = AsyncMock()
    result = asyncio.run(generate_org_candidates({"name": "甲公司", "industry": "化工"}, db))
    assert result[0]["group_key"] == "cmd"
    assert result[0]["members"][0]["name"] == ""  # 姓名必须留空
