from app.models.enterprise import PlanSection


def test_plan_section_has_diagram_svgs_column():
    cols = {c.name for c in PlanSection.__table__.columns}
    assert "diagram_svgs" in cols


def test_diagram_svgs_default():
    s = PlanSection(id="t", plan_project_id="p", section_key="s", title="t", level=1, sort_order=0)
    assert s.diagram_svgs == {}


from app.services.plan_diagram_service import (
    build_risk_matrix_svg, build_evacuation_svg, make_placeholder,
)


def test_make_placeholder_structure():
    p = make_placeholder("risk_matrix", "missing_risk_events")
    assert p["placeholder"] is True
    assert p["key"] == "risk_matrix"
    assert p["reason"] == "missing_risk_events"


def test_build_risk_matrix_svg():
    events = [
        {"name": "储罐泄漏", "likelihood": 3, "severity": 4, "risk_level": "较大"},
        {"name": "电气火灾", "likelihood": 2, "severity": 3, "risk_level": "一般"},
    ]
    out = build_risk_matrix_svg(events)
    assert out["placeholder"] is False
    assert "<svg" in out["svg"]
    assert "储罐泄漏" in out["svg"]


def test_build_risk_matrix_svg_no_data():
    assert build_risk_matrix_svg([])["placeholder"] is True


def test_build_evacuation_svg_with_points():
    out = build_evacuation_svg(
        floor_plan_url=None,
        zones=[{"name": "生产区", "polygon": {"version": 2, "polygons": [
            {"points": [[10, 10], [90, 10], [90, 90], [10, 90]]}
        ]}}],
        objects=[{"name": "储罐", "location_x": 50, "location_y": 50}],
        resources=[{"name": "灭火器", "category": "消防", "location": "东墙"}],
    )
    assert out["placeholder"] is False
    assert "<svg" in out["svg"]
    assert "储罐" in out["svg"]


def test_build_evacuation_svg_no_data():
    out = build_evacuation_svg(None, [], [], [])
    assert out["placeholder"] is True


def test_risk_matrix_svg_escapes_names():
    events = [{"name": "<script>alert(1)</script>", "likelihood": 3, "severity": 4, "risk_level": "较大"}]
    out = build_risk_matrix_svg(events)
    assert "<script>" not in out["svg"]
    assert "&lt;script&gt;" in out["svg"]


def test_build_evacuation_svg_accepts_real_zone_shape():
    out = build_evacuation_svg(
        floor_plan_url=None,
        zones=[{"name": "生产区", "floor_plan_polygon": {"version": 2, "polygons": [
            {"points": [[10, 10], [90, 10], [90, 90], [10, 90]]}
        ]}}],
        objects=[{"name": "储罐", "location_x": None, "location_y": None}],
        resources=[],
    )
    assert out["placeholder"] is False


def test_risk_matrix_svg_chinese_likelihood_tolerated():
    events = [{"name": "火灾", "likelihood": "较大", "severity": 4, "risk_level": "较大"}]
    out = build_risk_matrix_svg(events)
    assert out["placeholder"] is False


def test_evacuation_svg_accepts_dict_points():
    out = build_evacuation_svg(
        floor_plan_url=None,
        zones=[{"name": "生产区", "floor_plan_polygon": {"version": 2, "polygons": [
            {"id": "p1", "points": [
                {"x": 10, "y": 10}, {"x": 90, "y": 10},
                {"x": 90, "y": 90}, {"x": 10, "y": 90},
            ]}
        ]}}],
        objects=[],
        resources=[],
    )
    assert out["placeholder"] is False
    assert "生产区" in out["svg"]


def test_risk_matrix_svg_chinese_levels_mapped():
    events = [
        {"name": "低风险", "likelihood": "低", "severity": 2, "risk_level": "低"},
        {"name": "重大风险", "likelihood": "重大", "severity": 5, "risk_level": "重大"},
    ]
    out = build_risk_matrix_svg(events)
    assert out["placeholder"] is False


from unittest.mock import MagicMock
from app.routers.generation import _attach_diagrams


def test_attach_diagrams_writes_risk_matrix_for_sec2():
    s = MagicMock()
    s.section_key = "sec_2"
    s.diagram_svgs = None
    ent_data = {"risk_events": [
        {"name": "火灾", "likelihood": 3, "severity": 4, "risk_level": "较大"}
    ]}
    _attach_diagrams(s, "comprehensive", ent_data)
    assert s.diagram_svgs.get("risk_matrix", {}).get("placeholder") is False


def test_attach_diagrams_placeholder_when_no_data():
    s = MagicMock()
    s.section_key = "sec_2"
    s.diagram_svgs = None
    _attach_diagrams(s, "comprehensive", {})
    assert s.diagram_svgs.get("risk_matrix", {}).get("placeholder") is True
