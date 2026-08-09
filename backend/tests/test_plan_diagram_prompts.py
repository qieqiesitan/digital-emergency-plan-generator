from app.routers.generation import (
    SECTION_ADDITIONAL_DIAGRAM_MAP,
    _append_additional_diagram_prompt,
)


def test_additional_diagram_map_covers_sections():
    assert SECTION_ADDITIONAL_DIAGRAM_MAP[("comprehensive", "sec_3")] == "org_chart"
    assert SECTION_ADDITIONAL_DIAGRAM_MAP[("comprehensive", "sec_4_2")] == "report_sequence"
    assert SECTION_ADDITIONAL_DIAGRAM_MAP[("comprehensive", "sec_5")] == "response_timeline"
    assert SECTION_ADDITIONAL_DIAGRAM_MAP[("comprehensive", "sec_9_1")] == "drill_gantt"


def test_additional_diagram_map_covers_special_plan():
    assert SECTION_ADDITIONAL_DIAGRAM_MAP[("special", "sec_1")] == "risk_matrix"
    assert SECTION_ADDITIONAL_DIAGRAM_MAP[("special", "sec_2")] == "org_chart"
    assert SECTION_ADDITIONAL_DIAGRAM_MAP[("special", "sec_3")] == "response_timeline"


def test_special_sec3_not_mistaken_for_org_chart():
    # 专项 sec_3 是「处置程序与措施」，不应被注入 org_chart 提示词
    prompt = _append_additional_diagram_prompt("base", "special", "sec_3", {"org_structure": []})
    assert "组织架构图" not in prompt
    assert "时间轴" in prompt


def test_comprehensive_sec3_still_gets_org_chart():
    prompt = _append_additional_diagram_prompt("base", "comprehensive", "sec_3", {"org_structure": []})
    assert "组织架构图" in prompt


from app.services.prompt_cache import get_additional_diagram_prompt


def test_additional_diagram_prompts_exist():
    for key in ("org_chart", "report_sequence", "response_timeline", "drill_gantt"):
        assert get_additional_diagram_prompt(key), f"missing prompt for {key}"
    assert "org_structure" in get_additional_diagram_prompt("org_chart")


def test_org_chart_prompt_has_data_guardrail():
    from app.services.prompt_cache import get_additional_diagram_prompt
    prompt = get_additional_diagram_prompt("org_chart")
    assert "不得编造" in prompt
    assert "数据中不存在" in prompt


from app.routers.generation import _build_org_chart_mermaid


def test_build_org_chart_mermaid_from_structure():
    org = [
        {"group_name": "应急救援指挥部", "members": [
            {"name": "张三", "position": "总指挥", "phone": "138", "responsibilities": "全面指挥"},
        ]},
        {"group_name": "抢险救援组", "members": [
            {"name": "李四", "position": "组长", "phone": "139", "responsibilities": "灭火"},
        ]},
    ]
    md = _build_org_chart_mermaid(org)
    assert "graph TD" in md
    assert "张三-总指挥" in md
    assert "李四-组长" in md


def test_build_org_chart_mermaid_empty_returns_none():
    assert _build_org_chart_mermaid([]) is None
    assert _build_org_chart_mermaid([{"group_name": "空组", "members": []}]) is None
