from app.models.enterprise_org import EnterpriseMember
from unittest.mock import MagicMock
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
