import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.services.risk_context_builder import _risk_source_item, build_risk_management_context


def test_risk_source_item_keeps_legacy_prompt_fields():
    zone = MagicMock(); zone.name = "生产区"
    obj = MagicMock(); obj.name = "原料仓库"; obj.category = "火灾"; obj.location = "东区"
    unit = MagicMock(); unit.name = "一号仓"
    event = MagicMock()
    event.accident_type = "火灾"
    event.risk_level = "较大"
    event.risk_score = "R=15"
    event.description = "可燃物堆积"
    event.trigger_conditions = "明火"
    event.consequences = "财产损失"
    event.method_params = {"l": 4, "s": 5}
    measure = MagicMock()
    measure.measure_category = "management"
    measure.description = "定期巡检"
    event.measures = [measure]

    item = _risk_source_item(zone, obj, unit, event)

    assert item["name"] == "原料仓库"
    assert item["categories"] == "火灾"
    assert item["location"] == "东区"
    assert item["control_measures"] == "定期巡检"
    assert item["zone"] == "生产区"
    assert item["unit"] == "一号仓"
    assert item["likelihood"] == 4
    assert item["severity"] == 5


def test_risk_source_item_without_unit_and_empty_values():
    zone = MagicMock(); zone.name = "生产区"
    obj = MagicMock(); obj.name = "原料仓库"; obj.category = None; obj.location = None
    unit = None
    event = MagicMock()
    event.accident_type = "火灾"
    event.risk_level = "较大"
    event.risk_score = "R=15"
    event.description = "可燃物堆积"
    event.trigger_conditions = "明火"
    event.consequences = "财产损失"
    event.method_params = {}
    event.measures = []

    item = _risk_source_item(zone, obj, unit, event)

    assert item["unit"] is None
    assert item["categories"] == ""
    assert item["location"] == ""
    assert item["control_measures"] == ""


def test_build_context_keeps_enterprise_legacy_keys():
    class FakeResult:
        def __init__(self):
            self.ent = MagicMock()
            self.ent.name = "测试企业"
            self.ent.established_date = None

        def __await__(self):
            yield
            return self

        def scalar_one_or_none(self):
            return self.ent

        def scalars(self):
            return self

        def all(self):
            return []

    db = MagicMock()
    db.execute = AsyncMock(return_value=FakeResult())

    ctx = asyncio.run(build_risk_management_context("ent-1", db))

    enterprise = ctx["enterprise"]
    for key in [
        "legal_representative",
        "credit_code",
        "economic_type",
        "established_date",
        "registered_capital",
        "phone",
        "land_area",
        "building_area",
        "safety_officer",
        "safety_standardization",
        "fire_approval",
        "main_products",
        "hazardous_chemicals",
        "special_equipment",
    ]:
        assert key in enterprise
