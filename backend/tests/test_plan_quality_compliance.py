from unittest.mock import MagicMock, patch
from app.services.plan_quality_service import check_plan, _extract_regulation_refs, _regulation_exists


def _section(key, title, content):
    s = MagicMock()
    s.section_key = key
    s.title = title
    s.content = content
    s.diagram_svgs = {}
    return s


def test_extract_regulation_refs():
    text = "依据《安全生产法》和GB/T 29639-2020，以及（应急管理部令第2号）要求"
    refs = _extract_regulation_refs(text)
    assert any("安全生产法" in r for r in refs)
    assert any("29639" in r for r in refs)


def test_l1_missing_required_section_is_issue():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>x</p>"),
    ], required_sections=["sec_1", "sec_2", "sec_3", "sec_4"])
    assert any("必含章节" in i["issue"] for i in result["issues"])
    assert result["valid"] is False


def test_l2_regulation_ref_not_in_library_warning():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    with patch("app.services.plan_quality_service._load_regulation_index") as mock_load:
        mock_load.return_value = ["安全生产法"]
        result = check_plan(plan, enterprise, [
            _section("sec_1", "事故风险分析", "<p>依据《不存在的法规X》要求。</p>"),
        ])
    assert any("不存在" in w["warning"] for w in result["warnings"])


def test_l3_terminology_mixed():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_2", "应急指挥", "<p>应急救援指挥部负责，应急指挥部协调。</p>"),
    ])
    assert any("术语" in w["warning"] for w in result["warnings"])
