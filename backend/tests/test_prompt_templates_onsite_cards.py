"""现场处置方案「应急处置卡」系列提示词约束测试。

背景：4 个 onsite sec_3 模板原本内容雷同（都要求"围绕事故特点、风险源、致灾机理…
撰写正文"），导致各章节重复生成风险分析。重写后每个章节职责差异化、禁止重复、
限制字数，且 previous_context 变量说明与实现（注入摘要）一致。
"""

import pytest

from seed_prompts_full import SEEDS


def _onsite_card_templates():
    return [
        s for s in SEEDS
        if s["template_code"].startswith("emergency_section_onsite_sec_3")
        and s["template_code"].endswith("_general")
    ]


@pytest.fixture()
def card_templates():
    templates = _onsite_card_templates()
    assert len(templates) == 4, "应有 4 个 onsite sec_3 模板（sec_3/3_1/3_2/3_3）"
    return {t["template_code"]: t for t in templates}


def test_all_card_templates_have_distinct_roles(card_templates):
    """每个章节职责必须差异化：卡片总览/第一响应/处置步骤/疏散路线。"""
    assert "速查" in card_templates["emergency_section_onsite_sec_3_general"]["user_prompt_template"]
    assert "报警" in card_templates["emergency_section_onsite_sec_3_1_general"]["user_prompt_template"]
    assert "步骤" in card_templates["emergency_section_onsite_sec_3_2_general"]["user_prompt_template"]
    assert "疏散" in card_templates["emergency_section_onsite_sec_3_3_general"]["user_prompt_template"]


def test_all_card_templates_forbid_duplication(card_templates):
    """每个模板必须显式禁止重复前文已写内容。"""
    for code, t in card_templates.items():
        assert any(
            kw in t["user_prompt_template"]
            for kw in ("禁止重复", "不得重复", "不要重复已写", "不得复述")
        ), f"{code} 缺少内容去重约束"


def test_all_card_templates_restrict_word_count(card_templates):
    """每个模板必须限制字数（卡片应简洁）。"""
    for code, t in card_templates.items():
        assert "字" in t["user_prompt_template"], f"{code} 缺少字数约束"


def test_all_card_templates_drop_long_risk_analysis_instruction(card_templates):
    """模板不得再要求写"致灾机理/典型后果"等长篇风险分析（那是 sec_1 的职责）。"""
    for code, t in card_templates.items():
        assert "致灾机理" not in t["user_prompt_template"], f"{code} 仍要求致灾机理分析"
        assert "围绕{{accident_type}}事故的特点、风险源" not in t["user_prompt_template"], f"{code} 仍要求通用风险分析"


def test_all_card_templates_previous_context_description_matches_summary(card_templates):
    """previous_context 变量说明必须与实现一致：注入的是摘要，不是全文。"""
    for code, t in card_templates.items():
        assert "摘要" in t["user_prompt_template"], f"{code} previous_context 说明未更新为摘要"


def test_all_card_templates_no_stale_placeholders(card_templates):
    """模板不得残留已不注入的占位符（如 {{first_chapter_hint}}）。"""
    for code, t in card_templates.items():
        assert "{{first_chapter_hint}}" not in t["user_prompt_template"], f"{code} 残留 first_chapter_hint"
