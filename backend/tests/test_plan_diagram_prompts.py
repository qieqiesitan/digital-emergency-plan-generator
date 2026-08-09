from app.routers.generation import (
    SECTION_ADDITIONAL_DIAGRAM_MAP,
)


def test_additional_diagram_map_covers_sections():
    assert SECTION_ADDITIONAL_DIAGRAM_MAP["sec_3"] == "org_chart"
    assert SECTION_ADDITIONAL_DIAGRAM_MAP["sec_4_2"] == "report_sequence"
    assert SECTION_ADDITIONAL_DIAGRAM_MAP["sec_5"] == "response_timeline"
    assert SECTION_ADDITIONAL_DIAGRAM_MAP["sec_9_1"] == "drill_gantt"


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
