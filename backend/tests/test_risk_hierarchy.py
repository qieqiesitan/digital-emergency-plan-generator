from types import SimpleNamespace

from app.routers.risk_management import sort_zones_by_floor


def _zone(floor_id, sort_order, name):
    return SimpleNamespace(id=name, floor_id=floor_id, sort_order=sort_order)


def test_sort_zones_by_floor_orders_by_floor_then_zone():
    zones = [
        _zone("f2", 1, "z2-1"),
        _zone("f1", 2, "z1-2"),
        _zone("f1", 0, "z1-0"),
        _zone("f2", 0, "z2-0"),
    ]
    order = {"f1": 0, "f2": 1}
    assert [z.id for z in sort_zones_by_floor(zones, order)] == ["z1-0", "z1-2", "z2-0", "z2-1"]


def test_sort_zones_by_floor_puts_unknown_floor_last():
    zones = [
        _zone(None, 0, "unassigned"),
        _zone("f1", 5, "z1"),
    ]
    order = {"f1": 0}
    assert [z.id for z in sort_zones_by_floor(zones, order)] == ["z1", "unassigned"]
