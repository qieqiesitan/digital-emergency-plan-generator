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


from unittest.mock import AsyncMock
from types import SimpleNamespace
from app.models.enterprise import PlanProject, PlanSection
from app.routers.plans import duplicate_plan


def test_duplicate_plan_copies_section_metadata(monkeypatch):
    """duplicate_plan 复制章节时应保留 4 个元数据字段，并生成编号与版本号。"""
    # 构造带元数据的原预案与章节
    src = PlanProject(
        id="src", user_id="u1", enterprise_id="e1", plan_type="onsite",
        title="原预案", version_number="B-2026-02",
    )
    sec = PlanSection(
        id="s1", plan_project_id="src", section_key="sec_3_4", title="紧急联系电话",
        level=2, sort_order=0, content="<p>x</p>", ai_generated=False,
        ai_generatable=False, auto_fill=True, auto_fill_source="org_structure",
        data_dependencies=["org_structure"],
    )
    src.sections = [sec]

    # 模拟 db：flush 后给 dup 赋 id；query 返回原预案
    db = MagicMock()
    dup_holder = {}

    async def fake_flush():
        dup_holder["dup"] = db.add.call_args.args[0]
        dup_holder["dup"].id = "dup-id"
        dup_holder["dup"].status = "draft"
        dup_holder["dup"].current_version = 1

    db.flush.side_effect = fake_flush

    # execute：第 1 次查原预案，第 2 次查企业，第 3 次统计同企业同类型数量
    plan_result = MagicMock()
    plan_result.scalar_one_or_none.return_value = src
    ent_result = MagicMock()
    ent_result.scalar_one_or_none.return_value = SimpleNamespace(name="测试企业")
    count_result = MagicMock()
    count_result.scalar.return_value = 2
    db.execute = AsyncMock(side_effect=[plan_result, ent_result, count_result])
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    import asyncio
    asyncio.run(duplicate_plan("src", current_user=MagicMock(), db=db))

    dup = dup_holder["dup"]
    added_sections = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], PlanSection)]
    contact = next(s for s in added_sections if s.section_key == "sec_3_4")
    assert contact.ai_generatable is False
    assert contact.auto_fill is True
    assert contact.auto_fill_source == "org_structure"
    assert contact.data_dependencies == ["org_structure"]
    assert dup.plan_number == "测试企业-XC-003"
    assert dup.version_number == "B-2026-02"


from app.schemas.plan import SectionResponse


def test_section_response_has_metadata_fields():
    resp = SectionResponse(
        id="s1", section_key="sec_3_4", title="紧急联系电话", level=2,
        sort_order=0, content="", ai_generated=False,
        updated_at="2026-08-08T00:00:00",
        ai_generatable=False, auto_fill=True,
        auto_fill_source="org_structure", data_dependencies=["org_structure"],
    )
    assert resp.ai_generatable is False
    assert resp.auto_fill is True
    assert resp.auto_fill_source == "org_structure"
    assert resp.data_dependencies == ["org_structure"]
