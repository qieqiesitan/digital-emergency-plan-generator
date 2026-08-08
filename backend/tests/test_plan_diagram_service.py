from app.models.enterprise import PlanSection


def test_plan_section_has_diagram_svgs_column():
    cols = {c.name for c in PlanSection.__table__.columns}
    assert "diagram_svgs" in cols


def test_diagram_svgs_default():
    s = PlanSection(id="t", plan_project_id="p", section_key="s", title="t", level=1, sort_order=0)
    assert s.diagram_svgs == {}
