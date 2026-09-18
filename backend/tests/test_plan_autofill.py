from app.routers.sections import _render_org_structure_html
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import sections


def _autofill_client(db):
    app = FastAPI()
    app.include_router(sections.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    return TestClient(app)


def _plan_section_ent():
    plan = SimpleNamespace(id="p1", enterprise_id="e1", user_id="u1")
    # 需要覆盖 SectionResponse 的全部必填字段，否则成功路径会在响应校验处报错
    section = SimpleNamespace(
        id="s1", section_key="sec_3", title="应急组织机构及职责", level=1, sort_order=3,
        content="", ai_generated=False, updated_at="2026-09-19T00:00:00+08:00",
        diagram_svgs={}, auto_fill=True, auto_fill_source="org_structure",
    )
    return plan, section, SimpleNamespace(id="e1")


def test_autofill_org_section_requires_emergency_org():
    """应急组织为空 → 400，文案为「请先维护应急组织」。"""
    plan, section, ent = _plan_section_ent()
    db = AsyncMock()
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: plan),
        MagicMock(scalar_one_or_none=lambda: section),
        MagicMock(scalar_one_or_none=lambda: ent),
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),  # units
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),  # roles
        MagicMock(all=lambda: []),                             # assignments
    ]
    resp = _autofill_client(db).post("/api/v1/plans/p1/sections/sec_3/autofill")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "请先维护应急组织"


def test_autofill_org_section_renders_emergency_members():
    """有应急组织 → 渲染 HTML 表格，含小组名与成员姓名（职务列用公司职位）。"""
    plan, section, ent = _plan_section_ent()
    unit = SimpleNamespace(id="u2", parent_id="u1", name="应急指挥部", duties="统一指挥", sort_order=0)
    role = SimpleNamespace(id="r1", unit_id="u2", name="总指挥", duties="全面负责",
                           sort_order=0, is_required=True)
    member = SimpleNamespace(id="m1", name="刘昕野", phone="13800000000", position="总经理",
                             email=None, org_node_id=None)
    assignment = SimpleNamespace(id="a1", role_id="r1", member_id="m1", sort_order=0)
    db = AsyncMock()
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: plan),
        MagicMock(scalar_one_or_none=lambda: section),
        MagicMock(scalar_one_or_none=lambda: ent),
        MagicMock(scalars=lambda: MagicMock(all=lambda: [unit])),
        MagicMock(scalars=lambda: MagicMock(all=lambda: [role])),
        MagicMock(all=lambda: [(assignment, member)]),
    ]
    resp = _autofill_client(db).post("/api/v1/plans/p1/sections/sec_3/autofill")
    assert resp.status_code == 200
    content = resp.json()["data"]["content"]
    assert "<h4>应急指挥部</h4>" in content
    assert "刘昕野" in content
    # 职务列显示应急角色（总指挥），不是公司职位（总经理）
    assert "<td>总指挥</td>" in content
    assert "<td>总经理</td>" not in content
    assert "13800000000" in content


def test_render_org_structure_html_creates_tables():
    org = [{
        "group_name": "应急救援指挥部",
        "members": [
            {"name": "张三", "position": "总指挥", "phone": "13800000000", "responsibilities": "全面指挥"},
            {"name": "李四", "position": "副总指挥", "phone": "13900000000", "responsibilities": "协助指挥"},
        ],
    }]
    html = _render_org_structure_html(org)
    assert "应急救援指挥部" in html
    assert "张三" in html and "13800000000" in html
    assert "总指挥" in html
    assert "<table" in html


def test_render_org_structure_html_empty_members_skipped():
    org = [{"group_name": "空组", "members": []}]
    assert _render_org_structure_html(org) == ""


def test_render_org_structure_html_prefers_emergency_role_over_company_position():
    """职务列优先显示应急角色（总指挥），公司职位只作回落。"""
    org = [
        {"group_name": "应急指挥部", "members": [
            {"name": "刘昕野", "role": "chief", "role_name": "总指挥", "position": "总经理",
             "phone": "13800000000"},
            {"name": "程磊", "position": "项目经理", "phone": "13900000000"},
        ]},
    ]
    html = _render_org_structure_html(org)
    assert "<td>总指挥</td>" in html
    assert "<td>总经理</td>" not in html
    assert "<td>项目经理</td>" in html


def test_render_org_structure_html_escapes_user_data():
    org = [{
        "group_name": "<script>alert(1)</script>",
        "members": [
            {"name": "<img src=x onerror=alert(2)>", "position": "总指挥",
             "phone": "13800000000", "responsibilities": "负责<应急>工作"},
        ],
    }]
    html = _render_org_structure_html(org)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<img" not in html
    assert "&lt;img" in html
