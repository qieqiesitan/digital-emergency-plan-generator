"""风险告知卡服务测试。"""
from datetime import datetime, timedelta, timezone
from app.models.risk_notice_card import RiskNoticeCard
from app.models.risk_management import RiskObject, RiskUnit, RiskEvent, RiskMeasure
from app.models.enterprise import Enterprise
from app.services.risk_notice_card_service import (
    compute_level, resolve_responsible, build_right_column, match_signs, compute_code,
    is_stale, merge_object_events, collect_measures,
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


def test_build_right_column_uses_snapshot():
    col = build_right_column([], [], snapshot={
        "hazard_description": "快照：配电室高温",
        "accident_types": ["火灾"],
        "control_measures": ["快照控制措施"],
        "emergency_measures": ["快照应急措施"],
    })
    assert col.hazard_description == "快照：配电室高温"
    assert col.accident_types == ["火灾"]
    assert col.control_measures == ["快照控制措施"]
    assert col.emergency_measures == ["快照应急措施"]


def test_is_stale_timezone():
    """naive 与 aware 时间统一换算 UTC 后正确比较。"""
    snap = RiskNoticeCard(updated_at=datetime(2026, 1, 1, 12, 0, 0))
    tz8 = timezone(timedelta(hours=8))
    equal_aware = datetime(2026, 1, 1, 20, 0, 0, tzinfo=tz8)   # 12:00 UTC，与快照同时刻
    later_aware = datetime(2026, 1, 1, 21, 0, 0, tzinfo=tz8)   # 13:00 UTC，晚于快照
    earlier_aware = datetime(2026, 1, 1, 19, 0, 0, tzinfo=tz8)  # 11:00 UTC，早于快照
    assert is_stale(snap, equal_aware) is False
    assert is_stale(snap, later_aware) is True
    assert is_stale(snap, earlier_aware) is False
    assert is_stale(snap, None) is False


def test_match_signs_merges_and_orders():
    signs = match_signs(["火灾", "触电"])
    cats = [s["category"] for s in signs]
    assert cats[:2] == ["warning", "warning"]
    assert "prohibition" in cats and "instruction" in cats


def test_compute_code_increments():
    objs = [RiskObject(name="A"), RiskObject(name="B")]
    assert compute_code(objs, objs[1]) == "FX-002"


def test_merge_object_events_dedupes_object_and_unit_events():
    obj = RiskObject(name="配电室")
    unit = RiskUnit(name="动力车间")
    obj.units.append(unit)
    shared = RiskEvent(accident_type="火灾", risk_level="重大", method_type="LS")
    obj.events.append(shared)
    unit.events.append(shared)
    own = RiskEvent(accident_type="触电", risk_level="一般", method_type="LS")
    unit.events.append(own)

    events = merge_object_events(obj)
    assert len(events) == 2
    assert events[0] is shared
    assert events[1] is own


def test_collect_measures_preserves_event_order():
    obj = RiskObject(name="配电室")
    e1 = RiskEvent(accident_type="火灾", risk_level="重大", method_type="LS")
    e2 = RiskEvent(accident_type="触电", risk_level="一般", method_type="LS")
    obj.events.extend([e1, e2])
    m1 = RiskMeasure(measure_category="engineering", description="防静电接地")
    m2 = RiskMeasure(measure_category="management", description="动火审批")
    e1.measures.append(m1)
    e2.measures.append(m2)

    measures = collect_measures(merge_object_events(obj))
    assert measures == [m1, m2]
