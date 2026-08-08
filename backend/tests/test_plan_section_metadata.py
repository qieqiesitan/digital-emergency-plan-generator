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


from unittest.mock import MagicMock
from app.routers.plans import _create_sections_from_template


def test_create_sections_copies_metadata_recursively():
    db = MagicMock()
    structure = [{
        "key": "sec_3", "title": "应急组织", "level": 1, "sort_order": 0,
        "ai_generatable": True, "auto_fill": False, "auto_fill_source": None,
        "data_dependencies": [],
        "subsections": [{
            "key": "sec_3_4", "title": "紧急联系电话", "level": 2, "sort_order": 0,
            "ai_generatable": False, "auto_fill": True,
            "auto_fill_source": "org_structure", "data_dependencies": ["org_structure"],
            "subsections": [],
        }],
    }]
    _create_sections_from_template(db, "plan-1", structure)
    added = [c.args[0] for c in db.add.call_args_list]
    contact = next(s for s in added if s.section_key == "sec_3_4")
    assert contact.ai_generatable is False
    assert contact.auto_fill is True
    assert contact.auto_fill_source == "org_structure"
    assert contact.data_dependencies == ["org_structure"]
