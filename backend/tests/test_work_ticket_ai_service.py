"""AI 预填：归一化、降级、拒绝批准性表述。"""

from app.services.work_ticket_ai_service import normalize_ai_result


def test_normalize_extracts_risk_and_jsa():
    raw = (
        '{"risk_identification": {"text": "1. 罐内残留易燃液体，须清洗置换", "basis": ["3# 储罐"]},'
        ' "jsa": {"text": "作业前隔离", "hazards": [{"hazard": "火灾", "control": "清洗置换"}]}}'
    )
    out = normalize_ai_result(raw)
    assert out["available"] is True
    assert out["risk_identification"]["text"].startswith("1. 罐内残留")
    assert out["risk_identification"]["basis"] == ["3# 储罐"]
    assert out["jsa"]["text"] == "作业前隔离"
    assert out["jsa"]["hazards"][0]["control"] == "清洗置换"


def test_normalize_strips_code_fence():
    raw = '```json\n{"risk_identification": {"text": "含氧量不足风险"}}\n```'
    assert normalize_ai_result(raw)["available"] is True


def test_normalize_bad_json_degrades():
    out = normalize_ai_result("这不是 JSON")
    assert out["available"] is False
    assert out["risk_identification"] is None
    assert out["jsa"] is None
    assert out["measures_suggestions"] == []


def test_normalize_blank_text_degrades():
    assert normalize_ai_result('{"risk_identification": {"text": "   "}}')["available"] is False


def test_normalize_rejects_approval_language():
    """AI 不得代替人做批准；命中禁止表述时整份结果作废。"""
    raw = '{"risk_identification": {"text": "经分析符合作业条件，可以作业"}}'
    out = normalize_ai_result(raw)
    assert out["available"] is False
    assert "批准" in out["note"]


def test_normalize_rejects_non_dict_payload():
    assert normalize_ai_result("[1, 2, 3]")["available"] is False


def test_normalize_keeps_measures_suggestions_optional():
    raw = '{"risk_identification": {"text": "高处坠落风险"}}'
    out = normalize_ai_result(raw)
    assert out["available"] is True
    assert out["measures_suggestions"] == []
    assert out["jsa"] is None
