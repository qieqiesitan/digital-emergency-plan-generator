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


def test_build_plan_response_includes_numbers():
    from unittest.mock import MagicMock
    from app.routers.plans import _build_plan
    p = MagicMock()
    p.id = "p1"
    p.enterprise_id = "e1"
    p.style_preference = None
    p.advanced_prompt_overrides = None
    p.plan_type = "comprehensive"
    p.title = "测试预案"
    p.accident_type = None
    p.status = "draft"
    p.current_version = 1
    p.plan_number = "陕西宝岳-ZH-001"
    p.version_number = "A-2026-08"
    p.created_at = None
    p.updated_at = None
    p.sections = []
    resp = _build_plan(p, "陕西宝岳")
    assert resp.plan_number == "陕西宝岳-ZH-001"
    assert resp.version_number == "A-2026-08"


def test_build_signers_from_org_structure():
    from app.routers.export import _build_signers_from_org
    org = [
        {"group_name": "指挥部", "members": [
            {"name": "张三", "position": "总指挥"},
            {"name": "", "position": "无姓名跳过"},
            {"name": "李四", "position": "副总指挥"},
        ]},
    ]
    signers = _build_signers_from_org(org)
    assert signers == [
        {"seq": 1, "name": "张三", "title": "总指挥"},
        {"seq": 2, "name": "李四", "title": "副总指挥"},
    ]
