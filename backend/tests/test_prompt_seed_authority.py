"""test_prompt_seed_authority.py"""
from app.services.report_data_authority import RULE_MARKER
from app.services import report_system_prompts as rsp
from seed_prompts_full import SEEDS


def test_report_system_prompts_contain_rule():
    assert RULE_MARKER in rsp.RA_REPORT_SYSTEM_PROMPT
    assert RULE_MARKER in rsp.RI_REPORT_SYSTEM_PROMPT


def test_emergency_system_seeds_contain_rule():
    rows = [s for s in SEEDS if s.get("category") == "emergency_system"]
    assert len(rows) == 4
    assert all(RULE_MARKER in (s.get("system_prompt") or "") for s in rows)
