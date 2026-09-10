"""回归：风险评估 ch1/ch2 不得夹带 L×S 计算表（该表只在第三章输出）。"""

from app.services.report_system_prompts import RA_REPORT_SYSTEM_PROMPT
from app.services.risk_assessment_service import (
    CHAPTER_DEFINITIONS as RA_CHAPTERS,
    build_chapter_prompt,
)


RA_CTX = {
    "enterprise": {"name": "测试企业", "industry": "商贸服务"},
    "risk_sources": [],
}


def test_system_prompt_limits_ls_table_to_chapter3():
    assert "只有「三、风险等级评估」章节输出「L×S 风险评估计算表」" in RA_REPORT_SYSTEM_PROMPT
    assert "其余章节（辨识、汇总、措施、结论）一律不得输出 L×S 计算表" in RA_REPORT_SYSTEM_PROMPT


def test_ch1_ch2_instructions_ban_ls_table():
    by_key = {c["key"]: c["instruction"] for c in RA_CHAPTERS}
    assert "禁止输出 L×S 风险评估计算表" in by_key["ch1_hazard_id"]
    assert "禁止输出 L×S 风险评估计算表" in by_key["ch2_summary"]


def test_ch1_prompt_contains_boundary_note():
    prompt = build_chapter_prompt("ch1_hazard_id", RA_CTX)
    assert "【边界约束】" in prompt
    assert "禁止输出 L×S 风险评估计算表" in prompt
