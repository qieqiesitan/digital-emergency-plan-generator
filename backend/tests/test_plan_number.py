from app.models.enterprise import PlanProject


def test_plan_project_has_number_columns():
    cols = {c.name for c in PlanProject.__table__.columns}
    assert {"plan_number", "version_number"} <= cols


def test_plan_number_generator():
    from app.routers.plans import _generate_plan_number
    assert _generate_plan_number("陕西宝岳科技有限公司", "comprehensive", 1) == "陕西宝岳-ZH-001"
    assert _generate_plan_number("甲公司", "special", 12) == "甲公司-ZX-012"
    assert _generate_plan_number("", "onsite", 3) == "企业-XC-003"
