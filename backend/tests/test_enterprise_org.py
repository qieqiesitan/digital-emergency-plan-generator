from app.models.enterprise_org import EnterpriseMember
from unittest.mock import MagicMock
from app.services.enterprise_org_service import validate_org_tree, sync_org_structure


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


def test_sync_org_structure_writes_mirror():
    ent = MagicMock()
    sync_org_structure(ent, [{"id": "d1", "type": "dept", "name": "生产部", "parent_id": None, "members": []}])
    assert ent.org_structure[0]["name"] == "生产部"
