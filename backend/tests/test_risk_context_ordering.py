"""test_risk_context_ordering.py"""
from types import SimpleNamespace

from app.services.risk_context_builder import build_risk_sources


def _obj(name, sort=0, created="2026-01-01", oid=None):
    return SimpleNamespace(
        id=oid or name, name=name, sort_order=sort, created_at=created,
        events=[], units=[], category="", location="", description="",
        is_risk_point=False, legacy_source_id=None, responsible_unit=None,
        responsible_person=None, contact_phone=None, floor_id=None,
    )


def _event(name, sort=0, created="2026-01-01"):
    return SimpleNamespace(
        id=name, sort_order=sort, created_at=created, accident_type=name,
        description="", trigger_conditions="", consequences="",
        risk_level="低", risk_score="R=4", method_type="", method_params={},
        chemical_id=None, measures=[], inherent_risk_level=None,
        inherent_risk_score=None, control_level=None,
    )


def test_build_risk_sources_is_deterministic_regardless_of_input_order():
    e1 = _event("火灾", created="2026-01-02")
    e2 = _event("触电", created="2026-01-01")
    unit = SimpleNamespace(id="u1", name="单元", sort_order=0, created_at="2026-01-01",
                           unit_type="", description="", location="", events=[e1, e2])
    obj = _obj("对象", created="2026-01-01")
    obj.units = [unit]
    obj2 = _obj("对象2", created="2026-01-01")
    obj2.events = [_event("火灾", created="2026-01-03")]
    zone_a = SimpleNamespace(id="z-b", name="乙区", sort_order=0, created_at="2026-01-02",
                             description="", floor=None, objects=[obj])
    zone_b = SimpleNamespace(id="z-a", name="甲区", sort_order=0, created_at="2026-01-01",
                             description="", floor=None, objects=[obj2])
    forward = build_risk_sources([zone_a, zone_b])
    backward = build_risk_sources([zone_b, zone_a])
    seq_forward = [(r["zone"], r["accident_type"]) for r in forward]
    seq_backward = [(r["zone"], r["accident_type"]) for r in backward]
    assert seq_forward == seq_backward
    assert seq_forward == [("甲区", "火灾"), ("乙区", "触电"), ("乙区", "火灾")]
