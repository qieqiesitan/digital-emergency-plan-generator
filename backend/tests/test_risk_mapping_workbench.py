from datetime import datetime, timezone

from app.routers.risk_management import _same_ts
from app.schemas.risk_management import (
    BatchSaveRequest,
    BatchSaveZoneItem,
    HierarchyZoneResponse,
    RiskPolygon,
    RiskPolygonPoint,
    RiskZoneFloorPlanPolygon,
)


def _v2_polygon() -> RiskZoneFloorPlanPolygon:
    return RiskZoneFloorPlanPolygon(
        version=2,
        color_source="auto",
        color=None,
        polygons=[RiskPolygon(
            id="p1",
            label="原料库",
            points=[
                RiskPolygonPoint(x=10, y=10),
                RiskPolygonPoint(x=30, y=10),
                RiskPolygonPoint(x=30, y=40),
            ],
        )],
    )


def test_batch_save_schema_accepts_v2_polygon():
    polygon = _v2_polygon()
    payload = BatchSaveRequest(
        floor_id="floor-1",
        floor_updated_at="2026-08-04T10:00:00+08:00",
        zones=[BatchSaveZoneItem(zone_id="zone-1", updated_at="2026-08-04T10:00:00+08:00", floor_plan_polygon=polygon)],
    )
    assert payload.floor_id == "floor-1"
    assert payload.zones[0].floor_plan_polygon.polygons[0].points[0].x == 10


def test_batch_save_schema_accepts_new_zone_with_client_id():
    payload = BatchSaveRequest(
        floor_id="floor-1",
        floor_updated_at="2026-08-04T10:00:00+08:00",
        zones=[BatchSaveZoneItem(client_id="zone-client-1", floor_plan_polygon=_v2_polygon())],
        risk_points=[],
    )
    assert payload.zones[0].client_id == "zone-client-1"
    assert payload.zones[0].zone_id is None


def test_hierarchy_zone_response_extends_floor_fields():
    resp = HierarchyZoneResponse.model_validate({
        "id": "zone-1",
        "floor_id": "floor-1",
        "floor_name": "一层",
        "name": "原料库",
        "description": "原料储存区域",
        "floor_plan_polygon": {
            "version": 2,
            "color_source": "auto",
            "color": None,
            "polygons": [{"id": "p1", "points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}]}],
        },
        "max_risk_level": "较大",
        "effective_color": "#fa8c16",
        "objects": [{
            "id": "obj-1",
            "name": "储罐区风险点",
            "category": "危险化学品",
            "is_risk_point": True,
            "floor_id": "floor-1",
            "location_x": 32.5,
            "location_y": 45.2,
        }],
    })
    assert resp.floor_id == "floor-1"
    assert resp.floor_name == "一层"
    assert resp.max_risk_level == "较大"
    assert resp.effective_color == "#fa8c16"
    assert resp.floor_plan_polygon is not None
    assert resp.objects[0].floor_id == "floor-1"
    assert resp.objects[0].location_x == 32.5
    assert resp.objects[0].location_y == 45.2


def test_same_ts_compares_absolute_instant():
    a = datetime(2026, 8, 4, 2, 0, tzinfo=timezone.utc)
    assert _same_ts(a, "2026-08-04T10:00:00+08:00")
    assert _same_ts("2026-08-04T02:00:00Z", "2026-08-04T10:00:00+08:00")
    assert not _same_ts(a, "2026-08-04T10:00:01+08:00")


def test_same_ts_none_semantics():
    assert _same_ts(None, None)
    assert not _same_ts(None, "2026-08-04T10:00:00+08:00")
    assert not _same_ts("2026-08-04T10:00:00+08:00", None)
