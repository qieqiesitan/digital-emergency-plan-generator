"""test_report_data_authority.py"""
from app.services.report_data_authority import (
    RULE_MARKER, apply_data_conflicts, compute_conflicts,
    merge_conflicts, sanitize_model_conflicts, with_rule,
)

SOURCES = [
    {"name": "燃气灶台", "risk_level": "较大", "categories": "火灾"},
    {"name": "机柜及服务器", "risk_level": "一般", "categories": "火灾"},
    {"name": "办公电脑", "risk_level": "低", "categories": ""},
]
GOOD_SUMMARY = {
    "risk_source_count": 3,
    "risk_level_distribution": {"重大": 0, "较大": 1, "一般": 1, "低": 1},
    "risk_by_category": {"火灾": 2},
    "top_risks": [{"name": "燃气灶台", "risk_level": "较大"}],
}


def test_with_rule_appends_once():
    text = with_rule("原始提示词")
    assert RULE_MARKER in text and text.startswith("原始提示词")
    assert with_rule(text) == text


def test_compute_conflicts_clean_summary_is_empty():
    assert compute_conflicts(SOURCES, GOOD_SUMMARY) == []


def test_compute_conflicts_detects_excluded_larger_risk():
    summary = dict(GOOD_SUMMARY)
    summary["risk_source_count"] = 2
    summary["risk_level_distribution"] = {"重大": 0, "较大": 0, "一般": 1, "低": 1}
    conflicts = compute_conflicts(SOURCES, summary)
    types = {c["type"] for c in conflicts}
    assert "count_mismatch" in types
    assert "level_mismatch" in types
    assert all(c["source"] == "code" for c in conflicts)


def test_compute_conflicts_reports_missing_summary():
    conflicts = compute_conflicts(SOURCES, {})
    assert len(conflicts) == 1
    assert conflicts[0]["type"] == "coverage"


def test_compute_conflicts_detects_top_risk_level_change():
    summary = dict(GOOD_SUMMARY)
    summary["top_risks"] = [{"name": "燃气灶台", "risk_level": "一般"}]
    conflicts = compute_conflicts(SOURCES, summary)
    assert any(c["type"] == "level_mismatch" and "燃气灶台" in c["item"] for c in conflicts)


def test_sanitize_model_conflicts_normalizes_and_drops_invalid():
    raw = [
        {"type": "narrative", "item": "厨房与企业档案描述不符", "note": "待核实"},
        {"type": "unknown", "item": "x"},
        {"item": ""},
        "not-a-dict",
    ]
    out = sanitize_model_conflicts(raw)
    assert len(out) == 2
    assert out[0]["source"] == "model"
    assert out[1]["type"] == "narrative"


def test_merge_conflicts_dedupes():
    code = [{"type": "coverage", "item": "x", "expected": "a", "actual": "b"}]
    model = [{"type": "coverage", "item": "x", "expected": "a", "actual": "b"}]
    assert len(merge_conflicts(code, model)) == 1


def test_apply_data_conflicts_keeps_other_keys():
    summary = dict(GOOD_SUMMARY)
    summary["data_conflicts"] = [{"type": "narrative", "item": "厨房与档案不符"}]
    out = apply_data_conflicts(summary, SOURCES)
    assert out["risk_source_count"] == 3
    assert out["data_conflicts"][0]["source"] == "model"
    assert "data_conflicts" in apply_data_conflicts(GOOD_SUMMARY, SOURCES)
