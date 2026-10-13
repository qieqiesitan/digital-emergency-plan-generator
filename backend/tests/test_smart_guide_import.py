"""智能引导（smart-guide）导入相关测试：AI 层级归一化与去重 prompt 注入。"""

import pytest

from app.services.risk_ai_service import (
    _normalize_smart_guide_hierarchy,
    build_smart_guide_enterprise_info,
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
async def test_smart_guide_prompt_includes_existing_tree():
    from types import SimpleNamespace

    captured = {}

    async def fake_llm(messages, ai_config, timeout=120, **kwargs):
        captured["messages"] = messages
        captured["timeout"] = timeout
        captured["kwargs"] = kwargs
        return '{"zones": [], "summary": {}}'

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.services.risk_ai_service.llm_text_completion",
            fake_llm,
        )
        await smart_guide(
            "储罐区要补充泄漏事件",
            {"name": "测试企业"},
            ai_config=SimpleNamespace(max_tokens=4096, model_name="deepseek-flash"),
            existing_tree_text='[{"name":"储罐区","objects":[{"name":"1号储罐","units":[]}]}]',
        )

    prompt = captured["messages"][-1]["content"]
    assert "储罐区" in prompt
    assert "1号储罐" in prompt
    assert "查漏补缺" in prompt
    assert "不得生成与现有分区" not in prompt
    # 同名多分区（如四色图识别出的 4 个「加油机」）必须逐段分别补充，而不是合并成一段
    assert "多个同名分区" in prompt
    assert "分别输出" in prompt
    # 输出预算下限：系统配置偏小（如 deepseek-flash 4096）时完整层级 JSON 会被截断
    # （reasoning 吃满预算、content 为空，2026-10-13 实测 500），必须抬高下限
    assert captured["kwargs"]["payload_overrides"]["max_tokens"] >= 16384
    # reasoning 型模型必须关闭思考，否则 reasoning 会把整份预算吃光（实测）
    assert captured["kwargs"]["payload_overrides"]["thinking"] == {"type": "disabled"}
    # 推理模型生成慢：超时必须大于 60s 才能容纳完整输出
    assert captured["timeout"] >= 120


@pytest.mark.asyncio
async def test_smart_guide_does_not_disable_thinking_for_non_deepseek():
    """非 deepseek 供应商不传 thinking 参数，避免严格网关 400。"""
    from types import SimpleNamespace

    captured = {}

    async def fake_llm(messages, ai_config, timeout=120, **kwargs):
        captured["kwargs"] = kwargs
        return '{"zones": [], "summary": {}}'

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.services.risk_ai_service.llm_text_completion",
            fake_llm,
        )
        await smart_guide(
            "",
            {"name": "甲"},
            ai_config=SimpleNamespace(max_tokens=4096, model_name="mock-json"),
        )

    assert "thinking" not in captured["kwargs"]["payload_overrides"]
    assert captured["kwargs"]["payload_overrides"]["max_tokens"] >= 16384


@pytest.mark.asyncio
async def test_smart_guide_prompt_handles_empty_description_and_extended_fields():
    from types import SimpleNamespace

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
            "",
            {"name": "甲", "main_equipment_list": "1号储罐、2号储罐",
             "surrounding_info": {"traffic_info": "东侧国道"}},
            ai_config=SimpleNamespace(max_tokens=4096),
        )

    prompt = captured["messages"][-1]["content"]
    assert "未填写补充说明" in prompt
    assert "1号储罐、2号储罐" in prompt
    assert "东侧国道" in prompt


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


def test_build_smart_guide_enterprise_info_filters_empty_and_merges_ledger():
    from types import SimpleNamespace

    ent = SimpleNamespace(
        name="测试企业", industry="加油站", business_scope=None, address="XX路1号",
        employee_count=None, building_overview="", main_products="汽油、柴油",
        annual_capacity=None, hazardous_chemicals="汽油", special_equipment=None,
        special_equipment_detail=None, main_equipment_list="1号储罐、2号储罐",
        natural_conditions=None, fire_protection_summary="消防栓8个",
        surrounding_info={"nearby_units": [], "sensitive_targets": [],
                          "traffic_info": "东侧国道"},
    )
    info = build_smart_guide_enterprise_info(
        ent, [{"name": "汽油", "cas_no": "86290-81-5", "location": "罐区"}]
    )
    assert info["name"] == "测试企业"
    assert info["address"] == "XX路1号"
    assert info["main_products"] == "汽油、柴油"
    assert info["main_equipment_list"] == "1号储罐、2号储罐"
    assert info["fire_protection_summary"] == "消防栓8个"
    assert info["hazardous_chemicals"] == "汽油"
    assert info["surrounding_info"]["traffic_info"] == "东侧国道"
    assert info["chemicals_ledger"][0]["name"] == "汽油"
    for empty_key in ("business_scope", "employee_count", "annual_capacity",
                      "building_overview", "special_equipment",
                      "special_equipment_detail", "natural_conditions"):
        assert empty_key not in info


def test_build_smart_guide_enterprise_info_without_ledger_skips_key():
    from types import SimpleNamespace

    ent = SimpleNamespace(
        name="乙", industry=None, business_scope=None, address=None,
        employee_count=None, building_overview=None, main_products=None,
        annual_capacity=None, hazardous_chemicals=None, special_equipment=None,
        special_equipment_detail=None, main_equipment_list=None,
        natural_conditions=None, fire_protection_summary=None, surrounding_info=None,
    )
    info = build_smart_guide_enterprise_info(ent, [])
    assert info == {"name": "乙"}


def test_build_existing_tree_dict_compact_shape():
    from types import SimpleNamespace as NS

    zones = [NS(name="储罐区", objects=[NS(
        name="1号储罐", category="储罐",
        units=[NS(name="罐体", unit_type="设备", events=[NS(
            accident_type="泄漏",
            measures=[NS(measure_category="engineering", description="设置液位监控报警")],
        )])],
        events=[],
    )])]
    assert build_existing_tree_dict(zones) == [{
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
