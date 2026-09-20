"""企业成员的特种作业证照字段（开票时用于自动拼接"姓名 + 证书号"）。"""


def test_member_create_accepts_certificates():
    from app.schemas.enterprise_org import MemberCreate

    payload = MemberCreate(
        name="张三",
        position="焊工",
        certificates=[
            {"type": "焊接与热切割作业", "no": "T6101", "valid_to": "2027-05-30"}
        ],
    )
    assert payload.certificates[0]["no"] == "T6101"


def test_member_create_certificates_default_empty():
    from app.schemas.enterprise_org import MemberCreate

    assert MemberCreate(name="李四").certificates == []


def test_member_update_certificates_optional():
    from app.schemas.enterprise_org import MemberUpdate

    assert MemberUpdate().certificates is None
    assert MemberUpdate(certificates=[]).certificates == []


def test_member_response_exposes_certificates():
    from app.schemas.enterprise_org import MemberResponse

    response = MemberResponse(
        id="m1",
        enterprise_id="e1",
        name="王五",
        role="member",
        enabled=True,
        certificates=[{"type": "低压电工作业", "no": "D2201"}],
    )
    assert response.certificates[0]["type"] == "低压电工作业"
