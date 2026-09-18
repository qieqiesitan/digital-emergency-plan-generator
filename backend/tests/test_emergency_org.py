"""应急组织三表与成员任职表的模型元数据（任务 1）。

数据行为（整树读写、校验、搬迁）在后续任务中追加用例。
"""

from app.models.emergency_org import (
    EmergencyOrgAssignment,
    EmergencyOrgRole,
    EmergencyOrgUnit,
)
from app.models.enterprise_org import MemberPosition


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
