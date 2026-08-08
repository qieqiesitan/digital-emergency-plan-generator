from app.models.enterprise import PlanSection


def test_plan_section_has_metadata_columns():
    cols = {c.name for c in PlanSection.__table__.columns}
    assert {"ai_generatable", "auto_fill", "auto_fill_source", "data_dependencies"} <= cols


def test_plan_section_metadata_defaults():
    s = PlanSection(
        id="test", plan_project_id="p", section_key="sec_1",
        title="总则", level=1, sort_order=0,
    )
    assert s.ai_generatable is True
    assert s.auto_fill is False
    assert s.auto_fill_source is None
    assert s.data_dependencies == []
