"""应急组织三表与成员任职表的模型元数据（任务 1）。

数据行为（整树读写、校验、搬迁）在后续任务中追加用例。
"""

from app.models.emergency_org import (
    EmergencyOrgAssignment,
    EmergencyOrgRole,
    EmergencyOrgUnit,
)
from app.models.enterprise_org import MemberPosition
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from types import SimpleNamespace

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import emergency_org as emergency_org_router

from app.services.emergency_org_service import (
    build_groups_for_consumers,
    build_legacy_groups,
    flatten_units,
    save_emergency_org,
)
from app.services.org_tree_validate import validate_emergency_units, validate_tree


def _api_client(db):
    app = FastAPI()
    app.include_router(emergency_org_router.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    return TestClient(app)


def test_emergency_org_get_returns_404_when_enterprise_missing():
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)
    resp = _api_client(db).get("/api/v1/enterprises/e1/emergency-org")
    assert resp.status_code == 404


def test_emergency_org_get_returns_empty_list_for_new_enterprise():
    """企业存在但尚无应急组织时返回空数组（前端据此显示空态）。"""
    ent = SimpleNamespace(id="e1")
    db = AsyncMock()
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: ent),
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),  # units
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),  # roles
        MagicMock(all=lambda: []),                             # assignments
    ]
    resp = _api_client(db).get("/api/v1/enterprises/e1/emergency-org")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_emergency_org_put_propagates_validation_error(monkeypatch):
    """PUT 契约：body 为 {units:[...]}，服务层 422 原样透出。"""
    ent = SimpleNamespace(id="e1")
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: ent)

    async def boom(db_, enterprise_id, units):
        assert units[0]["name"] == "应急指挥部"
        raise HTTPException(422, "角色 r1 成员不属于本企业或已停用: ghost")

    monkeypatch.setattr(emergency_org_router, "save_emergency_org", boom)
    resp = _api_client(db).put(
        "/api/v1/enterprises/e1/emergency-org",
        json={"units": [{"id": "u1", "name": "应急指挥部", "roles": []}]},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert "不属于本企业" in str(body.get("detail") or body)


def test_emergency_org_routes_registered_in_main():
    from app.main import app as main_app

    paths = {r.path for r in main_app.routes}
    assert "/api/v1/enterprises/{enterprise_id}/emergency-org" in paths


# ── 旧 /org-structure 接口：写下线、读兼容 ──

def _sub_client(db):
    from app.routers import enterprise_sub as sub_router

    app = FastAPI()
    app.include_router(sub_router.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    return TestClient(app)


def test_put_org_structure_is_gone():
    """PUT 已下线：它与 /org/nodes 写同一字段但格式不同，是数据互相覆盖的根源。"""
    resp = _sub_client(AsyncMock()).put("/api/v1/enterprises/e1/org-structure", json=[])
    assert resp.status_code == 410
    assert "应急组织" in resp.json()["detail"]


def test_get_org_structure_returns_legacy_groups_from_emergency_org():
    """GET 保留兼容视图：读应急组织并转成旧分组格式。"""
    ent = SimpleNamespace(id="e1", user_id="u1")
    unit_root = SimpleNamespace(id="u1", parent_id=None, name="应急组织机构", duties="", sort_order=0)
    unit_hq = SimpleNamespace(id="u2", parent_id="u1", name="应急指挥部", duties="统一指挥", sort_order=0)
    role = SimpleNamespace(id="r1", unit_id="u2", name="总指挥", duties="全面负责",
                           sort_order=0, is_required=True)
    member = SimpleNamespace(id="m1", name="刘昕野", phone="138", position="总经理",
                             email=None, org_node_id=None)
    assignment = SimpleNamespace(id="a1", role_id="r1", member_id="m1", sort_order=0)
    db = AsyncMock()
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: ent),
        MagicMock(scalars=lambda: MagicMock(all=lambda: [unit_root, unit_hq])),
        MagicMock(scalars=lambda: MagicMock(all=lambda: [role])),
        MagicMock(all=lambda: [(assignment, member)]),
    ]
    resp = _sub_client(db).get("/api/v1/enterprises/e1/org-structure")
    assert resp.status_code == 200
    assert resp.json()["data"] == [{
        "group_key": "headquarters",
        "group_name": "应急指挥部",
        "responsibilities": "统一指挥",
        "members": [{
            "name": "刘昕野",
            "role": "chief",
            "position": "总经理",
            "phone": "138",
            "responsibilities": "全面负责",
        }],
    }]


def test_flatten_units_remaps_ids_and_parents():
    units = [
        {"id": "u1", "name": "应急组织机构", "roles": []},
        {"id": "u2", "parent_id": "u1", "name": "应急指挥部", "roles": [
            {"id": "r1", "name": "总指挥", "is_required": True, "member_ids": ["m1", "m2"]}]},
    ]
    unit_rows, role_rows, assignment_rows = flatten_units(units)
    assert len(unit_rows) == 2
    assert len(role_rows) == 1
    assert len(assignment_rows) == 2
    # 入参 id 不是 UUID，落库必须换成新 UUID 并重挂 parent
    assert unit_rows[0]["id"] != "u1"
    assert unit_rows[1]["parent_id"] == unit_rows[0]["id"]
    assert role_rows[0]["unit_id"] == unit_rows[1]["id"]
    assert role_rows[0]["is_required"] is True
    assert assignment_rows[0]["role_id"] == role_rows[0]["id"]
    assert assignment_rows[0]["member_id"] == "m1"
    assert assignment_rows[1]["sort_order"] == 1


def test_flatten_units_root_parent_is_none():
    unit_rows, role_rows, assignment_rows = flatten_units([{"id": "u1", "name": "应急组织机构"}])
    assert unit_rows[0]["parent_id"] is None
    assert unit_rows[0]["name"] == "应急组织机构"
    assert unit_rows[0]["sort_order"] == 0
    assert role_rows == []
    assert assignment_rows == []


def test_build_legacy_groups_maps_names_and_roles():
    units = [
        {"id": "u1", "parent_id": None, "name": "应急组织机构", "roles": []},
        {"id": "u2", "parent_id": "u1", "name": "应急指挥部", "duties": "统一指挥现场处置",
         "roles": [{"name": "总指挥", "duties": "全面负责", "members": [
             {"name": "刘昕野", "position": "总经理", "phone": "13800000000"}]}]},
        {"id": "u3", "parent_id": "u1", "name": "抢险救灾组",
         "roles": [{"name": "组长", "members": [{"name": "赵志龙", "position": "项目总监"}]}]},
    ]
    groups = build_legacy_groups(units)
    assert [g["group_name"] for g in groups] == ["应急指挥部", "抢险救灾组"]
    assert groups[0]["group_key"] == "headquarters"
    assert groups[0]["responsibilities"] == "统一指挥现场处置"
    assert groups[0]["members"][0]["role"] == "chief"
    assert groups[0]["members"][0]["name"] == "刘昕野"
    assert groups[0]["members"][0]["responsibilities"] == "全面负责"
    assert groups[1]["group_key"] == "rescue"
    assert groups[1]["members"][0]["role"] == "leader"


def test_build_groups_for_consumers_shape():
    units = [
        {"id": "u1", "parent_id": None, "name": "应急组织机构", "roles": []},
        {"id": "u2", "parent_id": "u1", "name": "应急指挥部", "duties": "统一指挥",
         "roles": [{"name": "总指挥", "duties": "全面负责", "members": [
             {"name": "刘昕野", "position": "总经理", "phone": "13800000000", "email": None}]}]},
    ]
    groups = build_groups_for_consumers(units)
    assert len(groups) == 1
    assert groups[0]["group_name"] == "应急指挥部"
    assert groups[0]["responsibilities"] == "统一指挥"
    assert groups[0]["members"] == [{
        "name": "刘昕野",
        "role": "chief",
        "role_name": "总指挥",
        "position": "总经理",
        "phone": "13800000000",
        "email": None,
        "responsibilities": "全面负责",
    }]


@pytest.mark.asyncio
async def test_save_emergency_org_rejects_unknown_member():
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalars=lambda: MagicMock(all=lambda: ["m1"]))
    units = [{"id": "u1", "name": "应急指挥部", "roles": [
        {"id": "r1", "name": "总指挥", "member_ids": ["ghost"]}]}]
    with pytest.raises(HTTPException) as ei:
        await save_emergency_org(db, "e1", units)
    assert ei.value.status_code == 422
    assert "不属于本企业" in ei.value.detail


def test_validate_tree_rejects_cycle():
    nodes = [
        {"id": "a", "type": "dept", "name": "A", "parent_id": "b", "members": []},
        {"id": "b", "type": "dept", "name": "B", "parent_id": "a", "members": []},
    ]
    errors = validate_tree(
        nodes, allow_types={"dept", "team", "position"}, id_field="id", parent_field="parent_id"
    )
    assert any("循环引用" in e for e in errors)


def test_validate_tree_rejects_missing_parent_and_empty_name():
    nodes = [{"id": "a", "type": "dept", "name": "  ", "parent_id": "ghost", "members": []}]
    errors = validate_tree(nodes, allow_types={"dept"}, id_field="id", parent_field="parent_id")
    assert any("名称不能为空" in e for e in errors)
    assert any("parent 不存在" in e for e in errors)


def test_validate_tree_skips_members_when_not_required():
    """应急单元用 roles 承载成员，校验时跳过 members 规则。"""
    nodes = [{"id": "u1", "name": "应急指挥部", "parent_id": None}]
    assert validate_tree(nodes, allow_types=None, require_members=False) == []


def test_validate_emergency_units_rejects_duplicate_role_name_and_bad_member():
    units = [
        {"id": "u1", "parent_id": None, "name": "应急指挥部", "roles": [
            {"id": "r1", "name": "总指挥", "member_ids": ["m1"]},
            {"id": "r2", "name": "总指挥", "member_ids": []},
        ]},
        {"id": "u2", "parent_id": "u1", "name": "抢险救灾组", "roles": [
            {"id": "r3", "name": "组长", "member_ids": ["m1", "m1", "outsider"]},
        ]},
    ]
    errors = validate_emergency_units(units, known_member_ids={"m1"})
    assert any("角色名重复" in e for e in errors)
    assert any("重复指派" in e for e in errors)
    assert any("不属于本企业" in e for e in errors)


def test_emergency_org_unit_metadata():
    assert EmergencyOrgUnit.__tablename__ == "emergency_org_units"
    cols = set(EmergencyOrgUnit.__table__.columns.keys())
    assert {"id", "enterprise_id", "parent_id", "name", "duties", "sort_order"} <= cols


def test_emergency_org_role_metadata():
    assert EmergencyOrgRole.__tablename__ == "emergency_org_roles"
    cols = set(EmergencyOrgRole.__table__.columns.keys())
    assert {"id", "enterprise_id", "unit_id", "name", "duties", "sort_order", "is_required"} <= cols
    assert EmergencyOrgRole.__table__.columns["is_required"].default.arg is False


def test_emergency_org_assignment_metadata():
    assert EmergencyOrgAssignment.__tablename__ == "emergency_org_assignments"
    cols = set(EmergencyOrgAssignment.__table__.columns.keys())
    assert {"id", "enterprise_id", "role_id", "member_id", "sort_order"} <= cols
    unique_idx = [ix for ix in EmergencyOrgAssignment.__table__.indexes if ix.unique]
    assert any({c.name for c in ix.columns} == {"role_id", "member_id"} for ix in unique_idx)


def test_member_position_metadata():
    assert MemberPosition.__tablename__ == "member_positions"
    cols = set(MemberPosition.__table__.columns.keys())
    assert {"id", "enterprise_id", "member_id", "org_node_id", "is_primary"} <= cols
    index_names = {ix.name for ix in MemberPosition.__table__.indexes}
    assert "uq_member_positions_primary" in index_names


def test_new_tables_have_server_side_uuid_default():
    """四张新表都会用裸 SQL 写入，id 必须有数据库端默认值，否则真库报 id 为 NULL。

    2026-09-19 真库实测踩过：ORM 只有 Python 端 default 时，
    `INSERT INTO member_positions (enterprise_id, member_id, org_node_id, is_primary)` 会
    NotNullViolation。此测试锁住 server_default。
    """
    for model in (EmergencyOrgUnit, EmergencyOrgRole, EmergencyOrgAssignment, MemberPosition):
        assert model.__table__.columns["id"].server_default is not None, model.__name__


def test_member_position_foreign_keys_cascade():
    """任职表的成员与企业外键都必须级联删除，避免成员删除后留下孤儿任职。"""
    member_fks = {
        fk.column.table.name: fk.ondelete
        for fk in MemberPosition.__table__.columns["member_id"].foreign_keys
    }
    assert member_fks == {"enterprise_members": "CASCADE"}
    ent_fks = {
        fk.column.table.name: fk.ondelete
        for fk in MemberPosition.__table__.columns["enterprise_id"].foreign_keys
    }
    assert ent_fks == {"enterprises": "CASCADE"}
