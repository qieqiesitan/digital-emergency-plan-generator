from unittest.mock import MagicMock

from app.routers.generation import _collect_enterprise_data


def test_collect_enterprise_data_uses_hierarchical_risk_context():
    ent = MagicMock()
    ent.name = "测试企业"
    ent.address = "测试地址"
    ent.industry = "化工"
    ent.business_scope = "生产"
    ent.employee_count = 100
    ent.building_overview = ""
    ent.org_structure = []
    ent.surrounding_info = {}
    ent.legal_representative = ""
    ent.credit_code = ""
    ent.economic_type = ""
    ent.established_date = None
    ent.registered_capital = None
    ent.phone = ""
    ent.land_area = None
    ent.building_area = None
    ent.safety_officer = ""
    ent.safety_standardization = ""
    ent.fire_approval = ""
    ent.main_products = ""
    ent.hazardous_chemicals = ""
    ent.special_equipment = ""

    risk_context = {
        "risk_sources": [{
            "zone": "生产区",
            "object": "原料仓",
            "unit": None,
            "name": "原料仓",
            "categories": "火灾",
            "location": "东区",
            "accident_type": "火灾",
            "risk_level": "较大",
            "description": "可燃物",
            "triggers": "明火",
            "consequences": "损失",
            "control_measures": "巡检",
            "measures": [],
        }]
    }
    resources = []

    data = _collect_enterprise_data(ent, risk_context, resources)

    assert data["risk_sources"][0]["name"] == "原料仓"
    assert data["risk_sources"][0]["categories"] == "火灾"
    assert data["risk_sources"][0]["control_measures"] == "巡检"
    assert data["risk_sources"][0]["accident_type"] == "火灾"
