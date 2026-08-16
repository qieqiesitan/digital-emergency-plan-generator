"""风险告知卡服务测试。"""
from datetime import datetime, timedelta, timezone
from app.models.risk_notice_card import RiskNoticeCard
from app.models.risk_management import RiskObject, RiskUnit, RiskEvent, RiskMeasure
from app.models.enterprise import Enterprise
from app.services.risk_notice_card_service import (
    compute_level, resolve_responsible, build_right_column, match_signs, compute_code,
    is_stale, merge_object_events, collect_measures, save_snapshot,
)


def test_risk_object_has_notice_card_fields():
    cols = {c.name for c in RiskObject.__table__.columns}
    assert {"responsible_unit", "responsible_person", "contact_phone", "public_token"} <= cols


def test_risk_object_schemas_include_responsibility_fields():
    from app.schemas.risk_management import (
        RiskObjectCreate, RiskObjectUpdate, RiskObjectResponse,
    )
    for model in (RiskObjectCreate, RiskObjectUpdate):
        for field in ("responsible_unit", "responsible_person", "contact_phone"):
            assert field in model.model_fields
            assert model.model_fields[field].default is None
    # 响应模型字段与 description/image_url 风格一致：DB 列恒存在，无默认值（必填）
    for field in ("responsible_unit", "responsible_person", "contact_phone"):
        assert field in RiskObjectResponse.model_fields
        assert RiskObjectResponse.model_fields[field].default is RiskObjectResponse.model_fields["description"].default
        assert RiskObjectResponse.model_fields[field].is_required()


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


def test_match_signs_excludes_eyewash_for_burn_and_poisoning():
    """热烫伤/吸入中毒场景不应自动匹配洗眼台（化学灼伤专用设施）。"""
    for accident_types in (["灼烫"], ["其他伤害", "灼烫"], ["中毒和窒息"]):
        signs = match_signs(accident_types)
        assert all(s["name"] != "洗眼台" for s in signs), accident_types


def test_match_signs_vehicle_and_boiler():
    """车辆伤害不出现紧急出口；锅炉爆炸不出现必须消除静电。"""
    vehicle = match_signs(["车辆伤害"])
    assert all(s["name"] != "紧急出口" for s in vehicle)
    boiler = match_signs(["锅炉爆炸"])
    assert all(s["name"] != "必须消除静电" for s in boiler)
    assert any(s["name"] == "紧急出口" for s in boiler)


def test_match_signs_fallback_is_generic_only():
    """未匹配事故类型（自定义）只用通用疏散提示，不配生产性防护标志。"""
    for accident_type in ("踩踏/人员伤害", "人员滑倒/摔伤", "设备损坏/数据丢失", "食物中毒"):
        signs = match_signs([accident_type])
        names = [s["name"] for s in signs]
        assert names, accident_type  # 非空（通用疏散提示）
        for bad in ("必须戴安全帽", "当心机械伤人", "禁止烟火"):
            assert bad not in names, f"{accident_type} 不应包含 {bad}"


def test_match_signs_custom_fire_explosion_maps_to_fire():
    """自定义「火灾爆炸」应映射到火灾组，而非兜底组。"""
    signs = match_signs(["火灾爆炸"])
    names = [s["name"] for s in signs]
    assert "当心火灾" in names
    assert "禁止烟火" in names


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


def test_save_snapshot_increments_version():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    async def run():
        existing = RiskNoticeCard(
            enterprise_id="e1",
            object_id="o1",
            version=1,
            content={
                "hazard_description": "旧文案",
                "accident_types": ["火灾"],
                "control_measures": [],
                "emergency_measures": [],
            },
            source="ai",
            created_by="u1",
        )
        db = AsyncMock()
        res = MagicMock()
        res.scalars.return_value.first.return_value = existing
        db.execute.return_value = res

        saved = await save_snapshot(
            db, "e1", "o1", "u1",
            {
                "hazard_description": "新文案",
                "accident_types": ["火灾"],
                "control_measures": [],
                "emergency_measures": [],
            },
        )
        assert saved is existing
        assert saved.version == 2
        assert saved.content["hazard_description"] == "新文案"
        assert saved.source == "ai"
        assert saved.created_by == "u1"
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(existing)

    asyncio.run(run())


def test_build_card_data_prefers_snapshot_signs():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from app.services.risk_notice_card_service import build_card_data

    async def run():
        snap = MagicMock()
        snap.content = {
            "hazard_description": "x", "accident_types": ["火灾"],
            "control_measures": [], "emergency_measures": [],
            "signs": [{"category": "notice", "name": "注意通风", "svg_name": "notice-ventilation"}],
            "signs_source": "ai",
        }
        snap.version = 1
        snap.source = "ai"
        snap.updated_at = None
        db = AsyncMock()
        db.execute.return_value = MagicMock()
        db.execute.return_value.scalars.return_value.first.return_value = snap
        ent = Enterprise(name="测试公司", safety_officer="李四", safety_officer_phone="13900000000")
        obj = RiskObject(id="o1", name="会议室", category="工作场所")
        events = [RiskEvent(id="e1", accident_type="火灾", risk_level="较大",
                            trigger_conditions="线路老化", consequences="火灾",
                            method_type="LS", method_params={"l": 3, "s": 3})]
        card = await build_card_data(db, ent, obj, [obj], events, [])
        # 快照标志优先：即使事故类型为火灾，也应使用快照中的人工/AI 标志，
        # 而不是规则 match_signs(["火灾"]) 产出的 当心火灾/禁止烟火。
        assert len(card.signs) == 1
        assert card.signs[0].svg_name == "notice-ventilation"
        assert card.signs[0].name == "注意通风"

    asyncio.run(run())


def test_normalize_signs_filters_and_limits():
    from app.services.risk_notice_card_service import normalize_signs

    signs = [
        {"category": "notice", "name": "紧急出口", "svg_name": "notice-exit"},
        {"category": "warning", "name": "当心火灾", "svg_name": "warning-fire"},
        {"category": "warning", "name": "当心爆炸", "svg_name": "warning-explosion"},
        {"category": "warning", "name": "当心触电", "svg_name": "warning-electric"},
        {"category": "prohibition", "name": "禁止烟火", "svg_name": "prohibition-smoking"},
        {"category": "instruction", "name": "必须戴安全帽", "svg_name": "instruction-helmet"},
        {"category": "instruction", "name": "必须戴防护手套", "svg_name": "instruction-gloves"},
        {"category": "instruction", "name": "必须穿绝缘鞋", "svg_name": "instruction-insulating-shoes"},
        {"category": "bogus", "name": "自造标志", "svg_name": "not-in-library"},
    ]
    out = normalize_signs(signs)
    names = [s["name"] for s in out]
    assert "自造标志" not in names
    cats = [s["category"] for s in out]
    order = ["warning", "prohibition", "instruction", "notice"]
    assert cats == sorted(cats, key=order.index)
    assert cats.count("instruction") <= 2
    assert len(out) <= 8
    assert len(out) == len({s["svg_name"] for s in out})  # 去重
