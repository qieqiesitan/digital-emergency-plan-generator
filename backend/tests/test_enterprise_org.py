from app.models.enterprise_org import EnterpriseMember


def test_enterprise_member_metadata():
    assert EnterpriseMember.__tablename__ == "enterprise_members"
    cols = EnterpriseMember.__table__.columns
    assert {"id", "enterprise_id", "user_id", "org_node_id", "position", "role", "enabled"} <= set(cols.keys())


def test_enterprise_member_construct():
    m = EnterpriseMember(enterprise_id="e1", user_id="u1", role="team_leader", position="班组长")
    assert m.role == "team_leader"
    assert m.enabled is True
