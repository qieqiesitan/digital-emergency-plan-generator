from app.models.enterprise import PlanProject


def test_plan_project_has_number_columns():
    cols = {c.name for c in PlanProject.__table__.columns}
    assert {"plan_number", "version_number"} <= cols


def test_plan_number_generator():
    from app.routers.plans import _generate_plan_number
    assert _generate_plan_number("陕西宝岳科技有限公司", "comprehensive", 1) == "陕西宝岳-ZH-001"
    assert _generate_plan_number("甲公司", "special", 12) == "甲公司-ZX-012"
    assert _generate_plan_number("", "onsite", 3) == "企业-XC-003"


def test_create_plan_schema_accepts_numbers():
    from app.schemas.plan import PlanCreate
    p = PlanCreate(
        enterprise_id="e1", plan_type="special", title="测试",
        accident_type="火灾", plan_number="自定义-001", version_number="A-2026-08",
    )
    assert p.plan_number == "自定义-001"
    assert p.version_number == "A-2026-08"
