from unittest.mock import MagicMock, patch
from app.services.plan_quality_service import check_plan, _extract_regulation_refs


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


def test_extract_regulation_refs_order_number_1digit():
    refs = _extract_regulation_refs("依据（应急管理部令第2号）要求")
    assert any("第2号" in r for r in refs)


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
        mock_load.return_value = {"安全生产法": "effective"}
        result = check_plan(plan, enterprise, [
            _section("sec_1", "事故风险分析", "<p>依据《不存在的法规X》要求。</p>"),
        ])
    assert any("不存在" in w["warning"] for w in result["warnings"])


def test_l2_abolished_regulation_warning():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    with patch("app.services.plan_quality_service._load_regulation_index") as mock_load:
        mock_load.return_value = {"安全生产法": "abolished"}
        result = check_plan(plan, enterprise, [
            _section("sec_1", "事故风险分析", "<p>依据《安全生产法》要求。</p>"),
        ])
    assert any("废止" in w["warning"] for w in result["warnings"])


def test_l2_empty_full_name_nodes_do_not_make_refs_exist():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    with patch("app.services.plan_quality_service._load_regulation_index") as mock_load:
        mock_load.return_value = {"": "effective", "安全生产法": "effective"}
        result = check_plan(plan, enterprise, [
            _section("sec_1", "事故风险分析", "<p>依据《不存在的法规X》要求。</p>"),
        ])
    assert any("不存在" in w["warning"] for w in result["warnings"])


def test_l2_law_nodes_included_in_index():
    from app.services.plan_quality_service import _REG_NODE_TYPES
    assert "law" in _REG_NODE_TYPES
    assert "policy" in _REG_NODE_TYPES
    assert "standard" in _REG_NODE_TYPES
    assert "article" not in _REG_NODE_TYPES
    assert "topic" not in _REG_NODE_TYPES


def test_l2_real_graph_law_nodes_in_index():
    """不 mock：读真实 graph.json，断言 law 节点进入法规索引（含《安全生产法》）。"""
    import json
    from pathlib import Path

    from app.services.plan_quality_service import _load_regulation_index

    index = _load_regulation_index()
    assert index is not None
    # 真实 law 节点：中华人民共和国安全生产法 (2021修正)
    assert "中华人民共和国安全生产法 (2021修正)" in index
    # 正文引用《安全生产法》应能被子串匹配命中
    assert any("安全生产法" in full for full in index)
    # graph.json 中所有带 full_name 的 law 节点都应进入索引
    p = Path(__file__).resolve().parent.parent / "app" / "regulations" / "data" / "graph.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    law_names = {
        n["full_name"]
        for n in data.get("nodes", [])
        if n.get("node_type") == "law" and n.get("full_name")
    }
    assert law_names, "graph.json 应包含 law 节点"
    assert law_names <= set(index)


def test_l3_terminology_mixed():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_2", "应急指挥", "<p>应急救援指挥部负责，应急指挥部协调。</p>"),
    ])
    assert any("术语" in w["warning"] for w in result["warnings"])


def test_l3_more_term_pairs():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_2", "应急指挥", "<p>抢险救援组负责，抢险组协调。</p>"),
    ])
    assert any("术语" in w["warning"] for w in result["warnings"])
