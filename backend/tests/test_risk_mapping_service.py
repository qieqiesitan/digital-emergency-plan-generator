import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.enterprise import EnterpriseFloor
from app.models.risk_management import RiskZone
from app.routers.risk_management import batch_save_workbench, create_zone, delete_floor, update_zone
from app.schemas.risk_management import (
    BatchSaveRequest,
    BatchSaveRiskPointItem,
    BatchSaveZoneItem,
    RiskObjectUpdate,
    RiskZoneCreate,
    RiskZoneFloorPlanPolygon,
    RiskZoneUpdate,
)
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


def _floor_result(floor):
    return MagicMock(scalar_one_or_none=MagicMock(return_value=floor))


def _scalars_result(items):
    m = MagicMock()
    m.scalars.return_value = items
    return m


def _scalars_all_result(items):
    m = MagicMock()
    m.scalars.return_value.all.return_value = items
    return m


def _none_result():
    return MagicMock(scalar_one_or_none=MagicMock(return_value=None))


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


def _make_floor(**overrides):
    values = dict(
        id="floor-1",
        enterprise_id="e-1",
        name="一层",
        sort_order=0,
        is_default=False,
        canvas_texts=[],
        created_at=datetime(2026, 8, 4, 2, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 4, 2, 0, tzinfo=timezone.utc),
    )
    values.update(overrides)
    return EnterpriseFloor(**values)


def _batch_body(**overrides):
    values = dict(floor_id="floor-1", floor_updated_at="2026-08-04T10:00:00+08:00", zones=[])
    values.update(overrides)
    return BatchSaveRequest(**values)


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
        _scalar_count(2),  # zones
        _scalar_count(3),  # objects
        _scalar_count(4),  # units
        _scalar_count(5),  # events
        _scalar_count(6),  # measures
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),  # 级联 delete
    ]

    resp = await delete_floor("floor-1", "e-1", MagicMock(id="u-1"), db)

    assert resp.data == {"zones": 2, "objects": 3, "total": 20}
    assert resp.message == "已删除楼层及 20 条风险数据"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_default_floor_blocked():
    db = AsyncMock()
    floor = MagicMock()
    floor.is_default = True
    db.execute.side_effect = [
        _ent_result(),
        _zone_result(floor),
        _scalar_count(0),  # zones
        _scalar_count(0),  # objects
        _scalar_count(0),  # units
        _scalar_count(0),  # events
        _scalar_count(0),  # measures
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),  # 级联 delete
        _none_result(),
    ]

    with pytest.raises(HTTPException) as exc_info:
        await delete_floor("floor-1", "e-1", MagicMock(id="u-1"), db)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_delete_default_floor_promotes_alternative():
    db = AsyncMock()
    floor = MagicMock()
    floor.is_default = True
    floor.floor_plan_url = None
    alternative = MagicMock()
    alternative.is_default = False
    alternative.floor_plan_url = None
    enterprise = MagicMock()
    db.execute.side_effect = [
        _ent_result(),
        _zone_result(floor),
        _scalar_count(0),  # zones
        _scalar_count(0),  # objects
        _scalar_count(0),  # units
        _scalar_count(0),  # events
        _scalar_count(0),  # measures
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),  # 级联 delete
        _floor_result(alternative),
        MagicMock(scalar_one=MagicMock(return_value=enterprise)),
    ]

    resp = await delete_floor("floor-1", "e-1", MagicMock(id="u-1"), db)

    assert resp.data == {"zones": 0, "objects": 0, "total": 0}
    assert alternative.is_default is True
    assert enterprise.floor_plan_url is None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_batch_save_rejects_risk_point_bound_to_zone_of_other_floor():
    db = AsyncMock()
    floor = _make_floor()
    point = MagicMock(id="rp-1")
    db.execute.side_effect = [
        _ent_result(),
        _floor_result(floor),
        _scalars_result([]),      # existing_zones
        _scalars_result([point]), # existing_points
        _none_result(),           # 分区归属校验：目标分区不在当前楼层/企业
    ]
    body = _batch_body(risk_points=[BatchSaveRiskPointItem(
        id="rp-1",
        name="跨楼层风险点",
        zone_id="zone-other-floor",
        location_x=10,
        location_y=20,
    )])

    with pytest.raises(HTTPException) as exc_info:
        await batch_save_workbench(body, "e-1", MagicMock(id="u-1"), db)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "ZONE_FLOOR_MISMATCH"


@pytest.mark.asyncio
async def test_batch_save_accepts_risk_point_bound_to_current_floor_zone():
    db = AsyncMock()
    floor = _make_floor()
    point = MagicMock(id="rp-1", updated_at=datetime(2026, 8, 4, 2, 0, tzinfo=timezone.utc))
    db.execute.side_effect = [
        _ent_result(),
        _floor_result(floor),
        _scalars_result([]),                       # existing_zones
        _scalars_result([point]),                  # existing_points
        MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock(id="zone-1"))),  # 归属校验通过
        _scalars_all_result([]),                   # saved_zones
        _scalars_all_result([]),                   # saved_points
        _scalar_count(0),                          # zone_count
        _scalar_count(0),                          # risk_point_count
    ]
    body = _batch_body(risk_points=[BatchSaveRiskPointItem(
        id="rp-1",
        name="同楼层风险点",
        zone_id="zone-1",
        location_x=10,
        location_y=20,
        updated_at="2026-08-04T10:00:00+08:00",
    )])

    resp = await batch_save_workbench(body, "e-1", MagicMock(id="u-1"), db)

    assert resp.message == "保存成功"
    assert point.zone_id == "zone-1"
    assert point.floor_id == "floor-1"


@pytest.mark.parametrize("bad", [150.0, -1.0, float("nan"), float("inf")])
@pytest.mark.asyncio
async def test_batch_save_rejects_out_of_range_point_coordinates(bad):
    db = AsyncMock()
    floor = _make_floor()
    db.execute.side_effect = [
        _ent_result(),
        _floor_result(floor),
        _scalars_result([]),
        _scalars_result([]),
    ]
    item = BatchSaveRiskPointItem.model_construct(
        client_id="rp-new-1",
        id=None,
        name="越界风险点",
        category=None,
        description=None,
        zone_id="zone-1",
        zone_client_id=None,
        floor_id=None,
        location_x=bad,
        location_y=50.0,
        updated_at=None,
    )
    body = _batch_body(risk_points=[item])

    with pytest.raises(HTTPException) as exc_info:
        await batch_save_workbench(body, "e-1", MagicMock(id="u-1"), db)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "POINT_OUT_OF_RANGE"


@pytest.mark.asyncio
async def test_batch_save_rejects_duplicate_client_id():
    db = AsyncMock()
    floor = _make_floor()
    db.execute.side_effect = [
        _ent_result(),
        _floor_result(floor),
    ]
    polygon = RiskZoneFloorPlanPolygon.model_validate({
        "version": 2,
        "color_source": "auto",
        "polygons": [{"id": "p1", "points": _points3()}],
    })
    body = _batch_body(zones=[
        BatchSaveZoneItem(client_id="dup-1", floor_plan_polygon=polygon),
        BatchSaveZoneItem(client_id="dup-1", floor_plan_polygon=polygon),
    ])

    with pytest.raises(HTTPException) as exc_info:
        await batch_save_workbench(body, "e-1", MagicMock(id="u-1"), db)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "INVALID_PAYLOAD"


@pytest.mark.asyncio
async def test_batch_save_rejects_missing_zone():
    db = AsyncMock()
    floor = _make_floor()
    db.execute.side_effect = [
        _ent_result(),
        _floor_result(floor),
        _scalars_result([MagicMock(id="zone-1")]),  # existing_zones
        _scalars_result([]),                        # existing_points
    ]
    body = _batch_body()

    with pytest.raises(HTTPException) as exc_info:
        await batch_save_workbench(body, "e-1", MagicMock(id="u-1"), db)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "ZONE_NOT_BOUND"
    assert exc_info.value.detail["data"]["missing_zone_ids"] == ["zone-1"]


@pytest.mark.asyncio
async def test_batch_save_requires_cascade_confirmation_for_zone_with_objects():
    db = AsyncMock()
    floor = _make_floor()
    db.execute.side_effect = [
        _ent_result(),
        _floor_result(floor),
        _scalars_result([MagicMock(id="zone-1")]),  # existing_zones
        _scalars_result([]),                        # existing_points
    ]
    body = _batch_body(deleted_zone_ids=["zone-1"])
    counts = {"object_count": 2, "unit_count": 0, "event_count": 0, "measure_count": 0}

    with patch("app.routers.risk_management.cascade_counts", new=AsyncMock(return_value=counts)):
        with pytest.raises(HTTPException) as exc_info:
            await batch_save_workbench(body, "e-1", MagicMock(id="u-1"), db)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "CASCADE_CONFIRM_REQUIRED"
    assert exc_info.value.detail["data"]["object_count"] == 2


@pytest.mark.asyncio
async def test_batch_save_confirmed_cascade_deletes_zone():
    db = AsyncMock()
    floor = _make_floor()
    zone = MagicMock(id="zone-1")
    db.execute.side_effect = [
        _ent_result(),
        _floor_result(floor),
        _scalars_result([zone]),    # existing_zones
        _scalars_result([]),        # existing_points
        _scalars_all_result([]),    # saved_zones
        _scalars_all_result([]),    # saved_points
        _scalar_count(0),           # zone_count
        _scalar_count(0),           # risk_point_count
    ]
    body = _batch_body(deleted_zone_ids=["zone-1"], confirm_cascade_zone_ids=["zone-1"])
    counts = {"object_count": 2, "unit_count": 0, "event_count": 0, "measure_count": 0}

    with patch("app.routers.risk_management.cascade_counts", new=AsyncMock(return_value=counts)):
        resp = await batch_save_workbench(body, "e-1", MagicMock(id="u-1"), db)

    assert resp.message == "保存成功"
    db.delete.assert_awaited_once_with(zone)
    db.commit.assert_awaited_once()
