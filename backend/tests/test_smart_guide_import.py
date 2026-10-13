"""智能引导（smart-guide）导入相关测试：AI 层级归一化与去重 prompt 注入。"""

import pytest

from app.services.risk_ai_service import (
    _normalize_smart_guide_hierarchy,
    build_existing_tree_dict,
    serialize_existing_tree,
    smart_guide,
)


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

    async def fake_llm(messages, ai_config, timeout=120, **kwargs):
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


def _sample_tree():
    return [{
        "name": "储罐区",
        "objects": [{
            "name": "1号储罐",
            "category": "储罐",
            "units": [{
                "name": "罐体",
                "unit_type": "设备",
                "events": [{
                    "accident_type": "泄漏",
                    "measures": [{"measure_category": "engineering",
                                  "description": "设置液位监控报警"}],
                }],
            }],
            "events": [],
        }],
    }]


def test_serialize_existing_tree_keeps_measure_description_when_small():
    text, truncated = serialize_existing_tree(_sample_tree())
    assert truncated is False
    for token in ("储罐区", "1号储罐", "罐体", "泄漏", "设置液位监控报警"):
        assert token in text


def test_serialize_existing_tree_empty_returns_brackets():
    text, truncated = serialize_existing_tree([])
    assert text == "[]"
    assert truncated is False


def test_serialize_existing_tree_degrades_measures_when_too_long():
    long_desc = "措" * 60
    tree = [{
        "name": "储罐区",
        "objects": [{
            "name": "1号储罐",
            "category": None,
            "units": [],
            "events": [{
                "accident_type": "火灾",
                "measures": [{"measure_category": "engineering",
                              "description": long_desc} for _ in range(10)],
            }],
        }],
    }]
    text, truncated = serialize_existing_tree(tree, max_chars=600)
    assert truncated is False
    assert long_desc not in text          # 降级为数量
    assert '"measures":10' in text        # 紧凑分隔符，无空格


def test_serialize_existing_tree_truncated_when_even_skeleton_too_long():
    tree = [{"name": f"分区{i:03d}", "objects": []} for i in range(300)]
    text, truncated = serialize_existing_tree(tree, max_chars=300)
    assert truncated is True
    assert len(text) <= 300
    assert "分区000" in text
    assert "分区299" not in text
