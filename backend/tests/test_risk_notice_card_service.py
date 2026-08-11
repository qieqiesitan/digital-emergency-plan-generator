"""风险告知卡服务测试。"""
import asyncio
from datetime import datetime, timezone
from app.models.risk_management import RiskObject
from app.models.risk_notice_card import RiskNoticeCard
from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent, RiskMeasure
from app.models.enterprise import Enterprise
from app.services.risk_notice_card_data import LEVEL_ORDER
from app.services.risk_notice_card_service import (
    compute_level, resolve_responsible, build_right_column, match_signs, compute_code,
)


def test_risk_object_has_notice_card_fields():
    cols = {c.name for c in RiskObject.__table__.columns}
    assert {"responsible_unit", "responsible_person", "contact_phone", "public_token"} <= cols


def test_snapshot_model_columns():
    cols = {c.name for c in RiskNoticeCard.__table__.columns}
    assert {"object_id", "version", "content", "source"} <= cols


def _event(accident_type: str, level: str, trigger: str, consequences: str) -> RiskEvent:
    return RiskEvent(accident_type=accident_type, risk_level=level,
                     trigger_conditions=trigger, consequences=consequences,
                     method_type="LS", method_params={"l": 3, "s": 3})


def test_compute_level_takes_highest():
    events = [_event("火灾", "一般", "", ""), _event("爆炸", "重大", "", "")]
    assert compute_level(events) == "重大"
    assert compute_level([]) == "未评估"


def test_resolve_responsible_fallback():
    ent = Enterprise(name="测试公司", safety_officer="李四", safety_officer_phone="13900000000")
    obj = RiskObject(name="配电室", responsible_unit=None, responsible_person=None, contact_phone=None)
    unit, person, phone, fallback = resolve_responsible(obj, ent)
    assert (unit, person, phone) == ("测试公司", "李四", "13900000000")
    assert fallback is True

    obj2 = RiskObject(name="配电室", responsible_unit="动力车间", responsible_person="王五", contact_phone="13800000000")
    unit2, person2, phone2, fallback2 = resolve_responsible(obj2, ent)
    assert (unit2, person2, phone2) == ("动力车间", "王五", "13800000000")
    assert fallback2 is False


def test_build_right_column_emergency_then_template():
    events = [_event("火灾", "重大", "泄漏遇明火", "火灾爆炸")]
    measures = [
        RiskMeasure(measure_category="engineering", description="防静电接地"),
        RiskMeasure(measure_category="management", description="动火审批"),
        RiskMeasure(measure_category="emergency", description="切断气源"),
    ]
    col = build_right_column(events, [measures[0], measures[1], measures[2]])
    assert "泄漏遇明火" in col.hazard_description
    assert col.accident_types == ["火灾"]
    assert "防静电接地" in col.control_measures[0]
    assert "切断气源" in col.emergency_measures[0]
    assert len(col.emergency_measures) >= 2  # 模板兜底


def test_match_signs_merges_and_orders():
    signs = match_signs(["火灾", "触电"])
    cats = [s["category"] for s in signs]
    assert cats[:2] == ["warning", "warning"]
    assert "prohibition" in cats and "instruction" in cats


def test_compute_code_increments():
    objs = [RiskObject(name="A"), RiskObject(name="B")]
    assert compute_code(objs, objs[1]) == "FX-002"
