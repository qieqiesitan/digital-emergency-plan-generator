from app.models.enterprise_org import EnterpriseMember
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.user import User
from app.routers import enterprise_org
from app.services.enterprise_org_service import validate_org_tree, sync_org_structure, normalize_org_nodes


def test_enterprise_member_metadata():
    assert EnterpriseMember.__tablename__ == "enterprise_members"
    cols = EnterpriseMember.__table__.columns
    assert {"id", "enterprise_id", "user_id", "org_node_id", "position", "role", "enabled"} <= set(cols.keys())


def test_enterprise_member_construct():
    m = EnterpriseMember(enterprise_id="e1", user_id="u1", role="team_leader", position="班组长")
    assert m.role == "team_leader"
    assert m.enabled is True


def test_validate_org_tree_ok():
    nodes = [
        {"id": "d1", "type": "dept", "name": "生产部", "parent_id": None, "members": []},
        {"id": "t1", "type": "team", "name": "甲班", "parent_id": "d1", "members": [{"name": "张三", "user_id": "u1"}]},
    ]
    assert validate_org_tree(nodes) == []


def test_validate_org_tree_rejects_duplicate_ids_and_bad_parent():
    nodes = [
        {"id": "d1", "type": "dept", "name": "A", "parent_id": None, "members": []},
        {"id": "d1", "type": "dept", "name": "B", "parent_id": None, "members": []},
        {"id": "t1", "type": "team", "name": "C", "parent_id": "missing", "members": []},
    ]
    errors = validate_org_tree(nodes)
    assert any("重复" in e for e in errors)
    assert any("parent" in e for e in errors)


def test_validate_org_tree_handles_non_dict_nodes():
    nodes = [None, "oops", 42, {"id": "d1", "type": "dept", "name": "A", "parent_id": None, "members": []}]
    errors = validate_org_tree(nodes)
    assert sum("必须是对象" in e for e in errors) == 3


def test_validate_org_tree_rejects_invalid_type():
    nodes = [{"id": "d1", "type": "boss", "name": "A", "parent_id": None, "members": []}]
    errors = validate_org_tree(nodes)
    assert any("type 非法" in e for e in errors)


def test_validate_org_tree_rejects_non_list_members():
    nodes = [{"id": "d1", "type": "dept", "name": "A", "parent_id": None, "members": "x"}]
    errors = validate_org_tree(nodes)
    assert any("members 必须为数组" in e for e in errors)


def test_validate_org_tree_rejects_empty_member_name():
    nodes = [{"id": "d1", "type": "dept", "name": "A", "parent_id": None, "members": [{"name": ""}]}]
    errors = validate_org_tree(nodes)
    assert any("无姓名成员" in e for e in errors)


def test_validate_org_tree_handles_string_member():
    nodes = [{"id": "d1", "type": "dept", "name": "A", "parent_id": None, "members": ["张三"]}]
    errors = validate_org_tree(nodes)
    assert any("非法成员" in e for e in errors)


def test_normalize_org_nodes_generates_ids_and_defaults_members():
    nodes = [{"type": "dept", "name": "A", "parent_id": None}]
    out = normalize_org_nodes(nodes)
    assert out[0]["id"] == "node-1"
    assert out[0]["members"] == []
    assert nodes[0] == {"type": "dept", "name": "A", "parent_id": None}


def test_normalize_org_nodes_does_not_mutate_input_top_level():
    nodes = [{"id": "d1", "type": "dept", "name": "A", "parent_id": None}]
    out = normalize_org_nodes(nodes)
    out[0]["name"] = "B"
    assert nodes[0]["name"] == "A"


def test_sync_org_structure_writes_mirror():
    ent = MagicMock()
    sync_org_structure(ent, [{"id": "d1", "type": "dept", "name": "生产部", "parent_id": None, "members": []}])
    assert ent.org_structure[0]["name"] == "生产部"


# ── 组织树 + 成员 CRUD 端点测试（FastAPI + dependency_overrides + SQL 文本分发 mock，参照 test_risk_control_list.py） ──

def _org_ent(**kw):
    e = Enterprise(id="e1", user_id="u1", name="甲公司")
    for k, v in kw.items():
        setattr(e, k, v)
    return e


def _org_member(**kw):
    m = EnterpriseMember(
        id=kw.pop("id", "m1"),
        enterprise_id=kw.pop("enterprise_id", "e1"),
        user_id=kw.pop("user_id", "u2"),
        org_node_id=kw.pop("org_node_id", None),
        position=kw.pop("position", None),
        role=kw.pop("role", "member"),
        enabled=kw.pop("enabled", True),
    )
    return m


def _scalar_result(value):
    res = MagicMock()
    res.scalar_one_or_none.return_value = value
    return res


def _org_db(ent, user=None, member=None, member_rows=None):
    """按 SQL 文本特征分发：
    FROM enterprises + enterprises.user_id → 读路径归属（仅当前用户 u1 的企业）；
    FROM enterprises（无 user_id 条件）→ 写路径企业查询（路由内判 403）；
    FROM users → 用户存在性检查；
    enterprise_members + JOIN users → 成员列表 all 行；
    enterprise_members.id = → 按 id 查成员 scalar_one_or_none；
    其余 enterprise_members → 重复检查 first。
    """
    db = AsyncMock()

    def fake_add(obj):
        if isinstance(obj, EnterpriseMember) and not getattr(obj, "id", None):
            obj.id = "m1"

    db.add = MagicMock(side_effect=fake_add)

    def fake_execute(stmt, *params):
        text = str(stmt)
        if "FROM enterprises" in text:
            if "enterprises.user_id =" in text:
                owned = ent if ent and ent.user_id == "u1" else None
                return _scalar_result(owned)
            return _scalar_result(ent)
        if "FROM users" in text:
            return _scalar_result(user)
        if "FROM enterprise_members" in text:
            if "JOIN users" in text:
                res = MagicMock()
                res.all.return_value = member_rows or []
                return res
            if "enterprise_members.id =" in text:
                return _scalar_result(member)
            res = MagicMock()
            res.first.return_value = member
            return res
        return _scalar_result(None)

    db.execute.side_effect = fake_execute
    return db


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(enterprise_org.router)

    def _override_user():
        return User(id="u1", email="a@b.c", name="A", role="admin")

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = lambda: _org_db(_org_ent())
    with TestClient(app) as test_client:
        yield test_client


# ── GET/PUT /nodes ──

def test_org_nodes_get_returns_structure(client):
    tree = [{"id": "d1", "type": "dept", "name": "生产部", "parent_id": None,
             "members": [{"name": "张三", "user_id": "u2", "position": "部长"}]}]
    client.app.dependency_overrides[get_db] = lambda: _org_db(_org_ent(org_structure=tree))
    resp = client.get("/enterprises/e1/org/nodes")
    assert resp.status_code == 200
    assert resp.json()["data"] == tree


def test_org_nodes_get_enterprise_not_found_404(client):
    client.app.dependency_overrides[get_db] = lambda: _org_db(None)
    resp = client.get("/enterprises/e1/org/nodes")
    assert resp.status_code == 404
    assert "企业不存在" in resp.json()["detail"]


def test_org_nodes_put_valid_tree_200(client):
    ent = _org_ent(org_structure=[])
    db = _org_db(ent)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {"nodes": [
        {"id": "d1", "type": "dept", "name": "生产部", "parent_id": None, "members": []},
        {"id": "t1", "type": "team", "name": "甲班", "parent_id": "d1",
         "members": [{"name": "张三", "user_id": "u2", "position": "班组长"}]},
    ]}
    resp = client.put("/enterprises/e1/org/nodes", json=body)
    assert resp.status_code == 200
    assert resp.json()["data"][0]["name"] == "生产部"
    assert ent.org_structure[1]["members"][0]["name"] == "张三"
    db.commit.assert_awaited()


def test_org_nodes_put_invalid_tree_422(client):
    ent = _org_ent()
    db = _org_db(ent)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {"nodes": [
        {"id": "d1", "type": "dept", "name": "A", "parent_id": None, "members": []},
        {"id": "d1", "type": "dept", "name": "B", "parent_id": None, "members": []},
    ]}
    resp = client.put("/enterprises/e1/org/nodes", json=body)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["code"] == "ORG_TREE_INVALID"
    assert any("重复" in e for e in detail["errors"])
    assert "重复" in detail["message"]
    db.commit.assert_not_awaited()


def test_org_nodes_put_non_owner_403(client):
    client.app.dependency_overrides[get_db] = lambda: _org_db(_org_ent(user_id="u2"))
    body = {"nodes": [{"id": "d1", "type": "dept", "name": "A", "parent_id": None, "members": []}]}
    resp = client.put("/enterprises/e1/org/nodes", json=body)
    assert resp.status_code == 403


# ── POST /members ──

def test_members_post_created_with_default_role(client):
    ent = _org_ent()
    user = User(id="u2", email="b@b.c", name="张三", role="user")
    db = _org_db(ent, user=user)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/org/members", json={"user_id": "u2"})
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["role"] == "member"
    assert data["user_id"] == "u2"
    assert data["enterprise_id"] == "e1"
    added = db.add.call_args[0][0]
    assert isinstance(added, EnterpriseMember)
    assert added.role == "member"
    assert added.enabled is True
    db.commit.assert_awaited()


def test_members_post_user_not_found_404(client):
    ent = _org_ent()
    db = _org_db(ent, user=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/org/members", json={"user_id": "nobody"})
    assert resp.status_code == 404
    assert "用户不存在" in resp.json()["detail"]


def test_members_post_duplicate_409(client):
    ent = _org_ent()
    user = User(id="u2", email="b@b.c", name="张三", role="user")
    db = _org_db(ent, user=user, member=_org_member())
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/org/members", json={"user_id": "u2"})
    assert resp.status_code == 409
    assert "已是企业成员" in resp.json()["detail"]


def test_members_post_non_owner_403(client):
    ent = _org_ent(user_id="u2")
    user = User(id="u3", email="c@b.c", name="李四", role="user")
    client.app.dependency_overrides[get_db] = lambda: _org_db(ent, user=user)
    resp = client.post("/enterprises/e1/org/members", json={"user_id": "u3"})
    assert resp.status_code == 403


# ── PUT /members ──

def test_members_put_updates_fields_without_clearing_others(client):
    ent = _org_ent()
    member = _org_member(org_node_id="n1", position="旧岗位", role="member", enabled=True)
    db = _org_db(ent, member=member)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.put("/enterprises/e1/org/members/m1", json={"position": "新岗位"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["position"] == "新岗位"
    assert data["org_node_id"] == "n1"  # exclude_unset：未传字段不误清
    assert member.role == "member"
    assert member.enabled is True
    db.commit.assert_awaited()


def test_members_put_404(client):
    ent = _org_ent()
    db = _org_db(ent, member=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.put("/enterprises/e1/org/members/missing", json={"position": "新岗位"})
    assert resp.status_code == 404
    assert "成员不存在" in resp.json()["detail"]


# ── DELETE /members ──

def test_members_delete_success(client):
    ent = _org_ent()
    member = _org_member()
    db = _org_db(ent, member=member)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.delete("/enterprises/e1/org/members/m1")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0
    db.delete.assert_awaited_with(member)
    db.commit.assert_awaited()


def test_members_delete_404(client):
    ent = _org_ent()
    db = _org_db(ent, member=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.delete("/enterprises/e1/org/members/missing")
    assert resp.status_code == 404
    assert "成员不存在" in resp.json()["detail"]


# ── GET /members ──

def test_members_get_joins_email_and_name(client):
    ent = _org_ent()
    member = _org_member(user_id="u2", org_node_id="n1", position="班组长", role="team_leader")
    user = User(id="u2", email="b@b.c", name="张三", role="user")
    db = _org_db(ent, member_rows=[(member, user)])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/org/members")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) == 1
    item = items[0]
    assert item["id"] == "m1"
    assert item["enterprise_id"] == "e1"
    assert item["user_id"] == "u2"
    assert item["email"] == "b@b.c"
    assert item["name"] == "张三"
    assert item["org_node_id"] == "n1"
    assert item["position"] == "班组长"
    assert item["role"] == "team_leader"
    assert item["enabled"] is True
