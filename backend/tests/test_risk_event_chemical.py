from app.schemas.risk_management import RiskEventCreate, RiskEventUpdate
from unittest.mock import MagicMock


def test_risk_event_create_accepts_chemical_id():
    data = RiskEventCreate(
        object_id="o1", accident_type="火灾",
        chemical_id="c1",
    )
    assert data.chemical_id == "c1"


def test_risk_event_update_accepts_chemical_id():
    data = RiskEventUpdate(chemical_id="c2")
    assert data.chemical_id == "c2"


def test_risk_event_model_has_chemical_id_column():
    from app.models.risk_management import RiskEvent
    cols = {c.name for c in RiskEvent.__table__.columns}
    assert "chemical_id" in cols


def test_collect_enterprise_data_injects_chemicals():
    from app.routers.generation import _collect_enterprise_data
    ent = MagicMock()
    ent.name = "甲公司"; ent.address = "地址"; ent.industry = "化工"
    ent.business_scope = None; ent.employee_count = None; ent.building_overview = None
    ent.org_structure = []; ent.surrounding_info = None
    ent.legal_representative = None; ent.credit_code = None; ent.economic_type = None
    ent.established_date = None; ent.registered_capital = None; ent.phone = None
    ent.land_area = None; ent.building_area = None; ent.safety_officer = None
    ent.safety_standardization = None; ent.fire_approval = None
    ent.main_products = None; ent.hazardous_chemicals = None; ent.special_equipment = None
    ent.risk_method_config = None
    ent.last_plan_filing_date = None; ent.last_plan_filing_authority = None
    chem = MagicMock()
    chem.id = "c1"; chem.name = "甲醇"; chem.cas_no = "67-56-1"
    chem.flash_point = "11℃"; chem.explosion_limit = "6-36%"
    chem.location = "储罐区"; chem.max_storage = "50t"
    data = _collect_enterprise_data(ent, {"risk_sources": [{"chemical_id": "c1"}]}, [], {"c1": chem})
    assert data["chemicals"][0]["name"] == "甲醇"
    assert data["risk_sources"][0]["chemical"]["flash_point"] == "11℃"
