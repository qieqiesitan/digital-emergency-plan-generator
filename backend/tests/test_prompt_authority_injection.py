"""test_prompt_authority_injection.py"""
from app.services import risk_assessment_service as ra
from app.services import resource_investigation_service as ri
from app.services.report_data_authority import RULE_MARKER
from app.routers import generation as gen


def test_ra_chapter_prompt_contains_rule_once(monkeypatch):
    monkeypatch.setattr(
        ra.RegulationContextBuilder, "get_chapter_context", lambda self, **kw: ""
    )
    context = {"enterprise": {"name": "甲企业"}, "risk_sources": []}
    prompt = ra.build_chapter_prompt("ch1_hazard_id", context)
    assert prompt.count(RULE_MARKER) == 1


def test_ri_chapter_prompt_contains_rule_once():
    context = {
        "enterprise": {"name": "甲企业"},
        "internal_resources": [], "external_resources": [],
        "risk_conclusion": None, "top_risks": [], "org_members": [],
        "chemicals": [], "risk_overview": [], "top_risk_sources": [],
        "total_events": 0,
    }
    prompt = ri.build_chapter_prompt("ch1_purpose", context)
    assert prompt.count(RULE_MARKER) == 1


def test_plan_system_prompt_contains_rule_once():
    text = gen._build_system_prompt("onsite", None, None)
    assert text.count(RULE_MARKER) == 1
