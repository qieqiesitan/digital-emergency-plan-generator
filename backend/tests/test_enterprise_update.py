import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from app.routers.enterprises import update_enterprise
from app.schemas.enterprise import EnterpriseUpdate


def _ent():
    ent = MagicMock()
    ent.id = "e1"
    ent.user_id = "u1"
    ent.name = "甲公司"
    ent.address = "地址"
    ent.industry = "化工"
    ent.business_scope = None
    ent.employee_count = None
    ent.building_overview = None
    ent.org_structure = []
    ent.surrounding_info = None
    ent.risk_method_config = {}
    ent.floor_plan_url = "http://example.com/floor.png"
    ent.gis_lat = 30.5
    ent.gis_lng = 120.1
    ent.credit_code = None
    ent.legal_representative = None
    ent.economic_type = None
    ent.established_date = None
    ent.registered_capital = None
    ent.phone = None
    ent.fax = None
    ent.postal_code = None
    ent.land_area = None
    ent.building_area = None
    ent.safety_officer = None
    ent.safety_officer_phone = None
    ent.safety_staff_count = None
    ent.safety_standardization = None
    ent.fire_approval = None
    ent.fire_approval_date = None
    ent.last_plan_filing_date = None
    ent.last_plan_filing_authority = None
    ent.main_products = None
    ent.annual_capacity = None
    ent.hazardous_chemicals = None
    ent.special_equipment = None
    ent.risk_sources = []
    ent.resources = []
    ent.plans = []
    ent.created_at = datetime.now()
    ent.updated_at = datetime.now()
    return ent


def _db_with(ent):
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: ent)
    return db


def test_update_explicit_null_clears_gis_and_floor_plan():
    ent = _ent()
    db = _db_with(ent)
    data = EnterpriseUpdate(gis_lat=None, gis_lng=None, floor_plan_url=None)
    asyncio.run(update_enterprise("e1", data, MagicMock(), db))
    assert ent.gis_lat is None
    assert ent.gis_lng is None
    assert ent.floor_plan_url is None
    assert ent.name == "甲公司"  # 未传字段不受影响


def test_update_missing_fields_keep_old_values():
    ent = _ent()
    db = _db_with(ent)
    data = EnterpriseUpdate(name="乙公司")
    asyncio.run(update_enterprise("e1", data, MagicMock(), db))
    assert ent.name == "乙公司"
    assert ent.gis_lat == 30.5
    assert ent.gis_lng == 120.1
    assert ent.floor_plan_url == "http://example.com/floor.png"


def test_update_explicit_null_name_keeps_old_name():
    ent = _ent()
    db = _db_with(ent)
    data = EnterpriseUpdate(name=None)
    asyncio.run(update_enterprise("e1", data, MagicMock(), db))
    assert ent.name == "甲公司"
