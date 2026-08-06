"""智能引导（smart-guide）导入相关测试：AI 层级归一化与去重 prompt 注入。"""

import pytest

from app.services.risk_ai_service import _normalize_smart_guide_hierarchy, smart_guide


def test_normalize_smart_guide_forces_risk_point_false():
    data = {
        "zones": [
            {
                "name": "储罐区",
                "objects": [
                    {"name": "1号储罐", "is_risk_point": True, "units": [], "events": []},
                    {"name": "2号储罐", "units": [], "events": []},
                ],
            }
        ]
    }
    result = _normalize_smart_guide_hierarchy(data)
    objs = result["zones"][0]["objects"]
    assert objs[0]["is_risk_point"] is False
    assert objs[1]["is_risk_point"] is False


@pytest.mark.asyncio
async def test_smart_guide_prompt_includes_existing_names():
    captured = {}

    async def fake_llm(messages, ai_config, timeout=120):
        captured["messages"] = messages
        return '{"zones": [], "summary": {}}'

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.services.risk_ai_service.llm_text_completion",
            fake_llm,
        )
        await smart_guide(
            "描述",
            {"name": "测试企业"},
            ai_config=object(),
            existing_names={"zones": ["储罐区"], "objects": ["1号储罐"]},
        )

    prompt = captured["messages"][-1]["content"]
    assert "储罐区" in prompt
    assert "1号储罐" in prompt
    assert "不得生成与现有分区" in prompt
