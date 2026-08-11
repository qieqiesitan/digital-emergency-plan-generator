"""风险告知卡服务测试。"""
from app.models.risk_management import RiskObject


def test_risk_object_has_notice_card_fields():
    cols = {c.name for c in RiskObject.__table__.columns}
    assert {"responsible_unit", "responsible_person", "contact_phone", "public_token"} <= cols
