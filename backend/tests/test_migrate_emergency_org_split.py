"""存量应急组织搬迁脚本的纯函数部分：形态识别、树格式拆分、旧分组拆分（任务 7）。"""

import importlib.util
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "migrate_emergency_org_split.py"
    spec = importlib.util.spec_from_file_location("migrate_emergency_org_split", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_classify_tree_shape():
    m = _load_module()
    nodes = [{"id": "preset-org-root", "type": "dept", "name": "应急组织机构", "parent_id": None}]
    assert m.classify_shape(nodes) == "tree"


def test_classify_group_shape():
    m = _load_module()
    nodes = [{"group_key": "headquarters", "group_name": "应急指挥部", "members": []}]
    assert m.classify_shape(nodes) == "groups"


def test_classify_none_for_company_only_tree():
    m = _load_module()
    nodes = [{"id": "node-1", "type": "dept", "name": "安全部", "parent_id": None}]
    assert m.classify_shape(nodes) == "none"


def test_classify_both_when_mixed():
    """同时存在旧分组与组织树时不能只按其中一种处理，否则会丢公司架构。"""
    m = _load_module()
    nodes = [
        {"group_key": "cmd", "group_name": "应急救援指挥部", "members": []},
        {"id": "preset-org-root", "type": "dept", "name": "应急组织机构", "parent_id": None},
        {"id": "node-1", "type": "dept", "name": "安全部", "parent_id": None},
    ]
    assert m.classify_shape(nodes) == "both"


def test_split_tree_separates_emergency_and_company_nodes():
    m = _load_module()
    nodes = [
        {"id": "preset-org-root", "type": "dept", "name": "应急组织机构", "parent_id": None},
        {"id": "preset-headquarters", "type": "team", "name": "应急指挥部", "parent_id": "preset-org-root"},
        {"id": "preset-headquarters-0", "type": "position", "name": "总指挥", "parent_id": "preset-headquarters"},
        {"id": "node-1", "type": "dept", "name": "公司", "parent_id": None},
        {"id": "node-2", "type": "dept", "name": "安全部", "parent_id": "node-1"},
    ]
    emergency_nodes, company_nodes = m.split_tree(nodes)
    assert {n["id"] for n in emergency_nodes} == {
        "preset-org-root", "preset-headquarters", "preset-headquarters-0"
    }
    assert {n["id"] for n in company_nodes} == {"node-1", "node-2"}


def test_split_tree_keeps_company_parent_links_intact():
    """公司节点保持原 parent_id，不因摘除应急子树而改写层级。"""
    m = _load_module()
    nodes = [
        {"id": "preset-org-root", "type": "dept", "name": "应急组织机构", "parent_id": None},
        {"id": "node-1", "type": "dept", "name": "公司", "parent_id": None},
        {"id": "node-2", "type": "team", "name": "技术开发", "parent_id": "node-1"},
    ]
    _, company_nodes = m.split_tree(nodes)
    assert [n["id"] for n in company_nodes] == ["node-1", "node-2"]
    assert company_nodes[1]["parent_id"] == "node-1"


def test_tree_to_units_keeps_dept_typed_child_as_group():
    """实测存在 type=dept 但语义是应急小组的子节点，按 parent 关系而非 type 判定分组。"""
    m = _load_module()
    emergency_nodes = [
        {"id": "preset-org-root", "type": "dept", "name": "应急组织机构", "parent_id": None},
        {"id": "node-5", "type": "dept", "name": "应急指挥部", "parent_id": "preset-org-root"},
        {"id": "preset-rescue", "type": "team", "name": "抢险救灾组", "parent_id": "preset-org-root"},
        {"id": "preset-rescue-0", "type": "position", "name": "组长", "parent_id": "preset-rescue"},
    ]
    units = m.tree_to_units(emergency_nodes)
    assert [u["name"] for u in units] == ["应急组织机构", "应急指挥部", "抢险救灾组"]
    assert units[0]["parent_id"] is None
    assert units[1]["parent_id"] == units[0]["id"]
    assert units[2]["roles"][0]["name"] == "组长"
    assert units[2]["roles"][0]["is_required"] is False


def test_tree_to_units_marks_required_commander_roles():
    m = _load_module()
    units = m.tree_to_units([
        {"id": "root", "type": "dept", "name": "应急组织机构", "parent_id": None},
        {"id": "hq", "type": "team", "name": "应急指挥部", "parent_id": "root"},
        {"id": "hq-0", "type": "position", "name": "总指挥", "parent_id": "hq"},
        {"id": "hq-1", "type": "position", "name": "副总指挥", "parent_id": "hq"},
        {"id": "hq-2", "type": "position", "name": "成员", "parent_id": "hq"},
    ])
    roles = {r["name"]: r["is_required"] for r in units[1]["roles"]}
    assert roles == {"总指挥": True, "副总指挥": True, "成员": False}


def test_groups_to_units_derives_roles_from_role_codes():
    m = _load_module()
    groups = [
        {"group_key": "headquarters", "group_name": "应急指挥部", "members": [
            {"name": "辛华", "role": "chief", "position": "总经理", "phone": "133"},
            {"name": "苏小芳", "role": "deputy", "position": "行政主管", "phone": "183"},
            {"name": "樊悦", "role": "member", "position": "前端开发", "phone": "183"},
        ]},
    ]
    units = m.groups_to_units(groups)
    assert units[0]["name"] == "应急组织机构"
    hq = units[1]
    assert hq["name"] == "应急指挥部"
    roles = {r["name"]: r for r in hq["roles"]}
    assert set(roles) == {"总指挥", "副总指挥", "组员"}
    assert roles["总指挥"]["is_required"] is True
    assert roles["总指挥"]["members"] == [
        {"name": "辛华", "position": "总经理", "phone": "133"}
    ]
