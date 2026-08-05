import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.risk_management import RiskZone
from app.routers.risk_management import create_zone, delete_floor, update_zone
from app.schemas.risk_management import RiskObjectUpdate, RiskZoneCreate, RiskZoneFloorPlanPolygon, RiskZoneUpdate
from app.services.risk_mapping_service import (
    effective_color,
    ensure_default_floor,
    normalize_polygon,
    validate_polygon_v2,
)


def _v2_polygon(polygons: list) -> dict:
    return {"version": 2, "color_source": "auto", "polygons": polygons}


def _points3() -> list[dict]:
    return [{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}]


def test_normalize_legacy_points():
    result = normalize_polygon({"points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}]}, "原料库")
    assert result["version"] == 2
    assert result["polygons"][0]["label"] == "原料库"
    assert result["polygons"][0]["points"][0]["x"] == 1


def test_validate_polygon_rejects_bad_coordinates():
    errors = validate_polygon_v2({
        "version": 2,
        "color_source": "manual",
        "color": "#ff4d4f",
        "polygons": [{"id": "p1", "points": [{"x": 10, "y": 10}, {"x": 20, "y": 20}, {"x": 30, "y": 101}]}],
    })
    assert any("0-100" in e for e in errors)


def test_validate_polygon_rejects_non_dict():
    errors = validate_polygon_v2("not-a-dict")
    assert any("必须为对象" in e for e in errors)


def test_validate_polygon_rejects_non_list_polygons():
    errors = validate_polygon_v2(_v2_polygon({"a": {"id": "p1", "points": _points3()}}))
    assert any("polygons" in e for e in errors)


def test_validate_polygon_rejects_non_list_polygon_item():
    errors = validate_polygon_v2(_v2_polygon(["not-a-dict"]))
    assert any("区域必须是对象" in e for e in errors)


def test_validate_polygon_rejects_non_list_points():
    errors = validate_polygon_v2(_v2_polygon([{"id": "p1", "points": "bad"}]))
    assert any("3 个顶点" in e for e in errors)


def test_validate_polygon_rejects_non_dict_point():
    errors = validate_polygon_v2(_v2_polygon([{"id": "p1", "points": ["bad"]}]))
    assert any("坐标必须是数值" in e for e in errors)


def test_risk_zone_polygon_normalizes_legacy_points():
    result = RiskZoneFloorPlanPolygon.model_validate({
        "id": "zone-1",
        "label": "原料库",
        "points": _points3(),
    })
    assert result.version == 2
    assert result.color_source == "auto"
    assert result.polygons[0].id == "zone-1"
    assert result.polygons[0].label == "原料库"
    assert result.polygons[0].points[0].x == 1


def test_risk_zone_create_accepts_legacy_polygon():
    zone = RiskZoneCreate(name="原料库", floor_plan_polygon={"points": _points3()})
    assert zone.floor_plan_polygon.version == 2
    assert zone.floor_plan_polygon.polygons[0].id == "legacy-polygon"


def test_risk_zone_polygon_rejects_invalid_version():
    with pytest.raises(ValidationError):
        RiskZoneFloorPlanPolygon.model_validate({"version": 1, "color_source": "auto", "polygons": [{"id": "p1", "points": _points3()}]})


def test_risk_zone_polygon_rejects_invalid_color_source():
    with pytest.raises(ValidationError):
        RiskZoneFloorPlanPolygon.model_validate({"version": 2, "color_source": "hack", "polygons": [{"id": "p1", "points": _points3()}]})


def test_risk_zone_polygon_requires_color_for_manual():
    with pytest.raises(ValidationError):
        RiskZoneFloorPlanPolygon.model_validate({"version": 2, "color_source": "manual", "polygons": [{"id": "p1", "points": _points3()}]})


def test_risk_zone_polygon_accepts_manual_with_color():
    result = RiskZoneFloorPlanPolygon.model_validate({
        "version": 2,
        "color_source": "manual",
        "color": "#ff4d4f",
        "polygons": [{"id": "p1", "points": _points3()}],
    })
    assert result.color == "#ff4d4f"


def test_risk_zone_polygon_rejects_empty_polygons():
    with pytest.raises(ValidationError):
        RiskZoneFloorPlanPolygon.model_validate({"version": 2, "color_source": "auto", "polygons": []})


def test_risk_zone_polygon_rejects_too_few_points():
    with pytest.raises(ValidationError):
        RiskZoneFloorPlanPolygon.model_validate({"version": 2, "color_source": "auto", "polygons": [{"id": "p1", "points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}]}]})


def test_risk_zone_polygon_rejects_duplicate_ids():
    with pytest.raises(ValidationError):
        RiskZoneFloorPlanPolygon.model_validate({
            "version": 2,
            "color_source": "auto",
            "polygons": [
                {"id": "p1", "points": _points3()},
                {"id": "p1", "points": _points3()},
            ],
        })


def test_risk_object_update_requires_risk_point_fields():
    with pytest.raises(ValidationError):
        RiskObjectUpdate(name="新增风险点", is_risk_point=True)


def test_risk_object_update_accepts_risk_point_with_fields():
    item = RiskObjectUpdate(name="新增风险点", is_risk_point=True, zone_id="z1", location_x=10, location_y=20)
    assert item.zone_id == "z1"
    assert item.location_x == 10


def test_risk_object_update_ignores_missing_fields_when_not_risk_point():
    item = RiskObjectUpdate(name="普通对象")
    assert item.is_risk_point is None


def test_ensure_default_floor_reuses_enterprise_floor_plan_url():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    db.add = MagicMock()
    enterprise = MagicMock()
    enterprise.floor_plan_url = "https://example.com/plan.png"
    db.get.return_value = enterprise

    floor = asyncio.run(ensure_default_floor(db, "enterprise-1"))

    assert floor.floor_plan_url == "https://example.com/plan.png"
    db.add.assert_called_once_with(floor)
    db.flush.assert_awaited_once()


def test_manual_color_wins():
    color = effective_color({"version": 2, "color_source": "manual", "color": "#123456", "polygons": []}, "重大")
    assert color == "#123456"


def _ent_result():
    return MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock()))


def _zone_result(z):
    return MagicMock(scalar_one_or_none=MagicMock(return_value=z))


def _scalar_count(n):
    m = MagicMock()
    m.scalar.return_value = n
    return m


def _make_zone(**overrides):
    values = dict(
        id="zone-1",
        enterprise_id="e-1",
        floor_id="f1",
        name="原料库",
        sort_order=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    values.update(overrides)
    return RiskZone(**values)


@pytest.mark.asyncio
async def test_create_zone_backfills_default_floor():
    db = AsyncMock()
    default_floor = MagicMock(id="default-floor")
    db.execute.side_effect = [
        _ent_result(),
        MagicMock(scalar_one_or_none=MagicMock(return_value=default_floor)),
    ]
    db.add = MagicMock()

    async def _fake_refresh(obj):
        obj.id = "zone-1"
        obj.sort_order = 0
        obj.created_at = datetime.now(timezone.utc)
        obj.updated_at = datetime.now(timezone.utc)
    db.refresh = _fake_refresh

    resp = await create_zone(RiskZoneCreate(name="原料库"), "e-1", MagicMock(id="u-1"), db)

    assert resp.data.floor_id == "default-floor"
    assert resp.data.name == "原料库"


@pytest.mark.asyncio
async def test_update_zone_floor_id_null_keeps_floor():
    db = AsyncMock()
    zone = _make_zone()
    db.execute.side_effect = [_ent_result(), _zone_result(zone)]

    resp = await update_zone("zone-1", RiskZoneUpdate(floor_id=None), "e-1", MagicMock(id="u-1"), db)

    assert resp.data.floor_id == "f1"
    # floor_id=null 表示不修改楼层，不应触发楼层解析/风险对象同步
    assert db.execute.call_count == 2


@pytest.mark.asyncio
async def test_update_zone_moving_floor_syncs_risk_objects():
    db = AsyncMock()
    zone = _make_zone()
    db.execute.side_effect = [
        _ent_result(),
        _zone_result(zone),
        MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock(id="f2"))),
        MagicMock(),  # UPDATE risk_objects 同步 floor_id
    ]

    resp = await update_zone("zone-1", RiskZoneUpdate(floor_id="f2"), "e-1", MagicMock(id="u-1"), db)

    assert resp.data.floor_id == "f2"
    assert db.execute.call_count == 4
    calls = [c.args[0] for c in db.execute.call_args_list]
    assert any("update risk_objects" in str(c).lower() for c in calls)


@pytest.mark.asyncio
async def test_delete_floor_returns_valid_api_response():
    db = AsyncMock()
    floor = MagicMock()
    floor.is_default = False
    floor.floor_plan_url = None
    db.execute.side_effect = [
        _ent_result(),
        _zone_result(floor),
        _scalar_count(0),  # zone_count
        _scalar_count(0),  # object_count
    ]

    resp = await delete_floor("floor-1", "e-1", MagicMock(id="u-1"), db)

    assert resp.data is None
    assert resp.message == "已删除"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_default_floor_blocked():
    db = AsyncMock()
    floor = MagicMock()
    floor.is_default = True
    db.execute.side_effect = [
        _ent_result(),
        _zone_result(floor),
        _scalar_count(0),
        _scalar_count(0),
    ]

    with pytest.raises(HTTPException) as exc_info:
        await delete_floor("floor-1", "e-1", MagicMock(id="u-1"), db)
    assert exc_info.value.status_code == 409
