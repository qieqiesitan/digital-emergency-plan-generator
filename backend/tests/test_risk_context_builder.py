from unittest.mock import MagicMock

from app.services.risk_context_builder import _risk_source_item


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
