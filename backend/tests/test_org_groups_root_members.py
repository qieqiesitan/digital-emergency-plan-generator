"""N-38：挂在「根单元」上的角色/成员不得被静默丢弃。

来源：2026-09-20 组织架构升级后的定向冒烟——`build_groups_for_consumers` 无条件跳过
没有 parent_id 的单元，导致"只在最外层页面里配了人"的用户：导出 docx 签署页为空、
质检的组织类规则整段跳过（假阴性）。
"""

from unittest.mock import MagicMock

from app.services.emergency_org_service import build_groups_for_consumers
from app.services.plan_quality_service import check_plan


def _section(key="sec_1", title="总则", content="<p>正文</p>"):
    s = MagicMock()
    s.section_key = key
    s.title = title
    s.content = content
    return s


def _unit(uid, name, parent_id, members):
    return {
        "id": uid, "name": name, "parent_id": parent_id, "duties": "",
        "roles": [{"id": f"{uid}-r", "name": "总指挥", "duties": "", "members": members}],
    }


def test_root_unit_with_members_is_emitted():
    units = [_unit("root", "应急指挥部", None, [{"name": "张三", "phone": "13800000000"}])]
    groups = build_groups_for_consumers(units)
    assert [g["group_name"] for g in groups] == ["应急指挥部"]
    assert [m["name"] for m in groups[0]["members"]] == ["张三"]


def test_root_unit_without_members_still_skipped():
    """没人挂在根上时维持原语义：只输出子单元，不产生空分组噪音。"""
    units = [
        _unit("root", "应急指挥部", None, []),
        _unit("child", "抢险救援组", "root", [{"name": "李四", "phone": "13900000000"}]),
    ]
    groups = build_groups_for_consumers(units)
    assert [g["group_name"] for g in groups] == ["抢险救援组"]


def test_child_members_not_lost_when_root_has_people_too():
    units = [
        _unit("root", "应急指挥部", None, [{"name": "张三", "phone": "13800000000"}]),
        _unit("child", "抢险救援组", "root", [{"name": "李四", "phone": "13900000000"}]),
    ]
    groups = build_groups_for_consumers(units)
    assert [g["group_name"] for g in groups] == ["应急指挥部", "抢险救援组"]
    assert sum(len(g["members"]) for g in groups) == 2


def test_quality_check_warns_when_no_org_groups():
    """应急组织为空时必须显式提示"组织类检查已跳过"，而不是装作没问题。"""
    result = check_plan(MagicMock(), MagicMock(), [_section()], emergency_groups=[])
    text = " ".join(w["warning"] for w in result["warnings"])
    assert "应急组织" in text and "跳过" in text


def test_quality_check_no_such_warning_when_groups_present():
    groups = build_groups_for_consumers(
        [_unit("root", "应急指挥部", None, [{"name": "张三", "phone": "13800000000"}])]
    )
    result = check_plan(MagicMock(), MagicMock(), [_section()], emergency_groups=groups)
    assert not any("已跳过" in w["warning"] for w in result["warnings"])
