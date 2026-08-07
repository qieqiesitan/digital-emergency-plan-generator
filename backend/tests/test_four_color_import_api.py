"""四色图导入 API：存储辅助、schema、analyze/commit/cancel 端点（mock db，不依赖数据库）。"""
import io
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw
from pydantic import ValidationError

import app.services.floor_plan_storage_service as fss
from app.schemas.risk_management import (
    FourColorAnalyzeResponse,
    FourColorDraftZone,
    FourColorExcludedItem,
    FourColorTextItem,
    FloorResponse,
    FourColorCommitRequest,
    FourColorCommitZone,
    RiskPolygonPoint,
)
from app.services.floor_plan_storage_service import (
    MAX_BYTES,
    promote_four_color_file,
    remove_four_color_temp_dir,
    save_four_color_temp,
)


def _png_bytes(img: Image.Image | None = None, width=120, height=80, color=(255, 0, 0)) -> bytes:
    if img is None:
        img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _four_color_png() -> bytes:
    img = Image.new("RGB", (600, 450), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, 280, 180], fill=(255, 0, 0))
    d.rectangle([320, 40, 560, 180], fill=(255, 127, 0))
    d.rectangle([40, 230, 280, 410], fill=(255, 255, 0))
    d.rectangle([320, 230, 560, 410], fill=(0, 0, 255))
    return _png_bytes(img)


# ── 存储辅助 ──


def test_save_four_color_temp_writes_and_returns_url(tmp_path, monkeypatch):
    monkeypatch.setattr(fss, "UPLOAD_DIR", tmp_path)
    url, token = save_four_color_temp("e-1", "f-1", _png_bytes(), "image/png")
    assert url.startswith("/uploads/enterprises/e-1/floors/f-1/four_color_tmp/")
    assert (tmp_path / url.removeprefix("/uploads/")).exists()
    assert token


def test_save_four_color_temp_cleans_old_session(tmp_path, monkeypatch):
    monkeypatch.setattr(fss, "UPLOAD_DIR", tmp_path)
    url1, _ = save_four_color_temp("e-1", "f-1", _png_bytes(), "image/png")
    url2, _ = save_four_color_temp("e-1", "f-1", _png_bytes(), "image/png")
    assert not (tmp_path / url1.removeprefix("/uploads/")).exists()
    assert (tmp_path / url2.removeprefix("/uploads/")).exists()


def test_save_four_color_temp_rejects_bad_type(tmp_path, monkeypatch):
    monkeypatch.setattr(fss, "UPLOAD_DIR", tmp_path)
    with pytest.raises(HTTPException) as exc:
        save_four_color_temp("e-1", "f-1", b"x", "image/gif")
    assert exc.value.status_code == 422


def test_save_four_color_temp_rejects_oversized(tmp_path, monkeypatch):
    monkeypatch.setattr(fss, "UPLOAD_DIR", tmp_path)
    with pytest.raises(HTTPException) as exc:
        save_four_color_temp("e-1", "f-1", b"x" * (MAX_BYTES + 1), "image/png")
    assert exc.value.status_code == 413


def test_promote_four_color_file_renames_to_final(tmp_path, monkeypatch):
    monkeypatch.setattr(fss, "UPLOAD_DIR", tmp_path)
    url, token = save_four_color_temp("e-1", "f-1", _png_bytes(width=120, height=80), "image/png")
    final_url, width, height = promote_four_color_file("e-1", "f-1", token)
    assert "four_color_tmp" not in final_url
    assert (width, height) == (120, 80)
    assert (tmp_path / final_url.removeprefix("/uploads/")).exists()
    assert not (tmp_path / url.removeprefix("/uploads/")).exists()


def test_promote_four_color_file_rejects_bad_token(tmp_path, monkeypatch):
    monkeypatch.setattr(fss, "UPLOAD_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        promote_four_color_file("e-1", "f-1", "../evil")


def test_remove_four_color_temp_dir_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(fss, "UPLOAD_DIR", tmp_path)
    _, token = save_four_color_temp("e-1", "f-1", _png_bytes(), "image/png")
    remove_four_color_temp_dir("e-1", "f-1", token)
    remove_four_color_temp_dir("e-1", "f-1", token)


# ── Schema ──


def _commit_zone(name="分区1", level="重大", points=None):
    pts = points or [{"x": 10, "y": 10}, {"x": 30, "y": 10}, {"x": 30, "y": 40}]
    return FourColorCommitZone(name=name, risk_level=level, polygons=[{"points": pts}])


def test_commit_request_accepts_valid_payload():
    req = FourColorCommitRequest(file_token="a" * 32, zones=[_commit_zone()], replace_existing=True)
    assert req.zones[0].risk_level == "重大"
    assert req.file_token == "a" * 32


def test_commit_request_rejects_unknown_level():
    with pytest.raises(ValidationError):
        _commit_zone(level="绿色")


def test_commit_request_rejects_too_few_points():
    with pytest.raises(ValidationError):
        _commit_zone(points=[{"x": 1, "y": 2}])


def test_commit_request_rejects_out_of_range_point():
    with pytest.raises(ValidationError):
        RiskPolygonPoint(x=150, y=50)


def test_commit_request_rejects_empty_zones():
    with pytest.raises(ValidationError):
        FourColorCommitRequest(file_token="a" * 32, zones=[], replace_existing=True)


# ── 端点：analyze ──


def _ent_exec_result(ent):
    m = MagicMock()
    m.scalar_one_or_none.return_value = ent
    return m


def _floor_exec_result(floor):
    m = MagicMock()
    m.scalar_one_or_none.return_value = floor
    return m


class FakeUpload:
    def __init__(self, data: bytes, content_type="image/png"):
        self.data = data
        self.content_type = content_type
        self.filename = "sample.png"
        self.size = len(data)
        self.headers = {}

    async def read(self):
        return self.data


@pytest.mark.asyncio
async def test_analyze_returns_zones_and_does_not_touch_db(monkeypatch):
    from app.routers import risk_management as rm

    db = AsyncMock()
    db.execute.side_effect = [_ent_exec_result(MagicMock()), _floor_exec_result(MagicMock())]
    monkeypatch.setattr(rm, "save_four_color_temp", MagicMock(return_value=("/uploads/tmp/x.png", "a" * 32)))
    resp = await rm.analyze_four_color("f-1", "e-1", FakeUpload(_four_color_png()), current_user=MagicMock(), db=db)
    data = resp.data
    assert data.canvas_width == 600 and data.canvas_height == 450
    assert len(data.zones) == 4
    assert {z.risk_level for z in data.zones} == {"重大", "较大", "一般", "低"}
    assert db.add.call_count == 0
    assert db.commit.call_count == 0


@pytest.mark.asyncio
async def test_analyze_no_zones_returns_422(monkeypatch):
    from app.routers import risk_management as rm

    db = AsyncMock()
    db.execute.side_effect = [_ent_exec_result(MagicMock()), _floor_exec_result(MagicMock())]
    monkeypatch.setattr(rm, "save_four_color_temp", MagicMock(return_value=("/uploads/tmp/x.png", "a" * 32)))
    remove_mock = MagicMock()
    monkeypatch.setattr(rm, "remove_four_color_temp_dir", remove_mock)
    upload = FakeUpload(_png_bytes(color=(255, 255, 255)))  # 纯白
    with pytest.raises(HTTPException) as exc:
        await rm.analyze_four_color("f-1", "e-1", upload, current_user=MagicMock(), db=db)
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "NO_ZONE_DETECTED"
    remove_mock.assert_called_once_with("e-1", "f-1", "a" * 32)


@pytest.mark.asyncio
async def test_analyze_invalid_image_returns_422(monkeypatch):
    from app.routers import risk_management as rm

    db = AsyncMock()
    db.execute.side_effect = [_ent_exec_result(MagicMock()), _floor_exec_result(MagicMock())]
    monkeypatch.setattr(rm, "save_four_color_temp", MagicMock(return_value=("/uploads/tmp/x.png", "a" * 32)))
    remove_mock = MagicMock()
    monkeypatch.setattr(rm, "remove_four_color_temp_dir", remove_mock)
    with pytest.raises(HTTPException) as exc:
        await rm.analyze_four_color("f-1", "e-1", FakeUpload(b"not-an-image"), current_user=MagicMock(), db=db)
    assert exc.value.status_code == 422
    remove_mock.assert_called_once_with("e-1", "f-1", "a" * 32)


@pytest.mark.asyncio
async def test_analyze_floor_not_found_404():
    from app.routers import risk_management as rm

    db = AsyncMock()
    db.execute.side_effect = [_ent_exec_result(MagicMock()), _floor_exec_result(None)]
    with pytest.raises(HTTPException) as exc:
        await rm.analyze_four_color("f-x", "e-1", FakeUpload(b"x"), current_user=MagicMock(), db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_analyze_propagates_excluded_and_texts(monkeypatch):
    """识别器算出的 excluded/texts/suspected 必须原样透传到 analyze 响应。"""
    from app.routers import risk_management as rm
    from app.services.four_color_recognizer import RecognizeResult

    db = AsyncMock()
    db.execute.side_effect = [_ent_exec_result(MagicMock()), _floor_exec_result(MagicMock())]
    monkeypatch.setattr(rm, "save_four_color_temp", MagicMock(return_value=("/uploads/tmp/x.png", "a" * 32)))
    fake = RecognizeResult(
        zones=[{
            "client_id": "d1",
            "name": "分区1",
            "risk_level": "重大",
            "color": "#ff4d4f",
            "suspected": True,
            "polygons": [{"id": "p1", "points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}]}],
        }],
        warnings=[],
        width=600,
        height=450,
        excluded=[{
            "color": "红",
            "reason": "legend",
            "polygons": [{"id": "p2", "points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}]}],
        }],
        texts=[{
            "points": [{"x": 1, "y": 2}, {"x": 3, "y": 2}, {"x": 3, "y": 4}, {"x": 1, "y": 4}],
            "text": "原料库",
            "confidence": 0.9,
        }],
    )
    monkeypatch.setattr(rm, "recognize_from_bytes", MagicMock(return_value=fake))
    resp = await rm.analyze_four_color("f-1", "e-1", FakeUpload(_four_color_png()), current_user=MagicMock(), db=db)
    assert resp.data.excluded[0].reason == "legend"
    assert resp.data.texts[0].text == "原料库"
    assert resp.data.zones[0].suspected is True


# ── 端点：commit ──


def _count_exec_result(n):
    m = MagicMock()
    m.scalar.return_value = n
    return m


def _zones_exec_result(zones):
    m = MagicMock()
    m.scalars.return_value.all.return_value = zones
    return m


def _commit_body(replace=True, level="重大"):
    return FourColorCommitRequest(
        file_token="a" * 32,
        zones=[_commit_zone(level=level)],
        replace_existing=replace,
    )


def _fake_floor_response():
    return FloorResponse(
        id="f-1",
        enterprise_id="e-1",
        name="一层",
        sort_order=0,
        floor_plan_url=None,
        description=None,
        canvas_width=600,
        canvas_height=450,
        canvas_texts=[],
        is_default=False,
        zone_count=0,
        risk_point_count=0,
        created_at="2026-08-06T00:00:00+08:00",
        updated_at="2026-08-06T00:00:00+08:00",
    )


def _saved_zones_result(*names_levels):
    zones = []
    for i, (name, level) in enumerate(names_levels):
        zones.append({
            "id": f"z-{i + 1}",
            "enterprise_id": "e-1",
            "floor_id": "f-1",
            "floor_name": "一层",
            "name": name,
            "description": None,
            "sort_order": i,
            "floor_plan_polygon": None,
            "max_risk_level": level,
            "effective_color": None,
            "object_count": 0,
            "created_at": "2026-08-06T00:00:00+08:00",
            "updated_at": "2026-08-06T00:00:00+08:00",
        })
    return _zones_exec_result(zones)


@pytest.mark.asyncio
async def test_commit_rejects_invalid_session(monkeypatch):
    from app.routers import risk_management as rm

    db = AsyncMock()
    db.execute.side_effect = [_ent_exec_result(MagicMock()), _floor_exec_result(MagicMock())]
    monkeypatch.setattr(rm, "four_color_temp_dir", MagicMock(return_value=None))
    with pytest.raises(HTTPException) as exc:
        await rm.commit_four_color_import(_commit_body(), "f-1", "e-1", current_user=MagicMock(), db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_commit_rejects_not_empty_without_replace(monkeypatch):
    from app.routers import risk_management as rm

    floor = MagicMock()
    floor.is_default = False
    floor.canvas_texts = []
    db = AsyncMock()
    db.execute.side_effect = [
        _ent_exec_result(MagicMock()),
        _floor_exec_result(floor),
        _count_exec_result(2),  # 已有分区
        _count_exec_result(0),  # 未绑定风险点
    ]
    monkeypatch.setattr(rm, "four_color_temp_dir", MagicMock(return_value=MagicMock()))
    with pytest.raises(HTTPException) as exc:
        await rm.commit_four_color_import(_commit_body(replace=False), "f-1", "e-1", current_user=MagicMock(), db=db)
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "FLOOR_NOT_EMPTY"


@pytest.mark.asyncio
async def test_commit_rejects_polygon_validation_failure(monkeypatch):
    from app.routers import risk_management as rm

    floor = MagicMock()
    floor.is_default = False
    db = AsyncMock()
    db.execute.side_effect = [_ent_exec_result(MagicMock()), _floor_exec_result(floor)]
    monkeypatch.setattr(rm, "four_color_temp_dir", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(rm, "validate_polygon_v2", MagicMock(return_value=["坐标越界"]))
    with pytest.raises(HTTPException) as exc:
        await rm.commit_four_color_import(_commit_body(), "f-1", "e-1", current_user=MagicMock(), db=db)
    assert exc.value.status_code == 422
    assert "坐标越界" in exc.value.detail


@pytest.mark.asyncio
async def test_commit_replace_deletes_old_zones_and_creates_new(monkeypatch):
    from app.routers import risk_management as rm

    floor = MagicMock()
    floor.is_default = False
    floor.canvas_texts = ["旧文字"]
    old_zone = MagicMock()
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.side_effect = [
        _ent_exec_result(MagicMock()),
        _floor_exec_result(floor),
        _zones_exec_result([old_zone]),
        MagicMock(),            # delete 未绑定风险对象
        _saved_zones_result(("重大区", "重大"), ("低风险区", "低")),
    ]
    monkeypatch.setattr(rm, "four_color_temp_dir", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(rm, "promote_four_color_file", MagicMock(return_value=("/uploads/enterprises/e-1/floors/f-1/20260806_x.png", 600, 450)))
    monkeypatch.setattr(rm, "_floor_response", AsyncMock(return_value=_fake_floor_response()))
    remove_tmp = MagicMock()
    remove_old = MagicMock()
    monkeypatch.setattr(rm, "remove_four_color_temp_dir", remove_tmp)
    monkeypatch.setattr(rm, "remove_floor_plan", remove_old)
    body = FourColorCommitRequest(
        file_token="a" * 32,
        zones=[
            _commit_zone(name="重大区", level="重大"),
            _commit_zone(name="低风险区", level="低"),
        ],
        replace_existing=True,
    )
    resp = await rm.commit_four_color_import(body, "f-1", "e-1", current_user=MagicMock(), db=db)
    db.delete.assert_called_once_with(old_zone)
    assert floor.floor_plan_url == "/uploads/enterprises/e-1/floors/f-1/20260806_x.png"
    assert floor.canvas_width == 600 and floor.canvas_height == 450
    assert floor.canvas_texts == []
    assert db.add.call_count == 2
    assert db.commit.call_count == 1
    remove_tmp.assert_called_once_with("e-1", "f-1", "a" * 32)
    remove_old.assert_called_once()
    assert len(resp.data.zones) == 2
    created_polys = [call.args[0].floor_plan_polygon for call in db.add.call_args_list]
    assert created_polys[0]["color"] == "#ff4d4f"
    assert created_polys[1]["color"] == "#52c41a"


@pytest.mark.asyncio
async def test_commit_without_replace_on_empty_floor_creates_zones(monkeypatch):
    from app.routers import risk_management as rm

    floor = MagicMock()
    floor.is_default = False
    floor.canvas_texts = []
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.side_effect = [
        _ent_exec_result(MagicMock()),
        _floor_exec_result(floor),
        _count_exec_result(0),  # 分区数
        _count_exec_result(0),  # 未绑定风险点数
        _saved_zones_result(("分区1", "重大")),
    ]
    monkeypatch.setattr(rm, "four_color_temp_dir", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(rm, "promote_four_color_file", MagicMock(return_value=("/uploads/enterprises/e-1/floors/f-1/20260806_x.png", 600, 450)))
    monkeypatch.setattr(rm, "_floor_response", AsyncMock(return_value=_fake_floor_response()))
    monkeypatch.setattr(rm, "remove_four_color_temp_dir", MagicMock())
    monkeypatch.setattr(rm, "remove_floor_plan", MagicMock())
    resp = await rm.commit_four_color_import(_commit_body(replace=False), "f-1", "e-1", current_user=MagicMock(), db=db)
    assert resp.data.zones[0].name == "分区1"
    assert db.delete.call_count == 0


# ── 端点：cancel ──


@pytest.mark.asyncio
async def test_cancel_removes_temp_dir(monkeypatch):
    from app.routers import risk_management as rm

    db = AsyncMock()
    db.execute.side_effect = [_ent_exec_result(MagicMock()), _floor_exec_result(MagicMock())]
    monkeypatch.setattr(rm, "four_color_temp_dir", MagicMock(return_value=MagicMock()))
    remove_mock = MagicMock()
    monkeypatch.setattr(rm, "remove_four_color_temp_dir", remove_mock)
    resp = await rm.cancel_four_color_import("a" * 32, "f-1", "e-1", current_user=MagicMock(), db=db)
    assert resp.message == "已清理临时文件"
    remove_mock.assert_called_once_with("e-1", "f-1", "a" * 32)


@pytest.mark.asyncio
async def test_cancel_invalid_session_404(monkeypatch):
    from app.routers import risk_management as rm

    db = AsyncMock()
    db.execute.side_effect = [_ent_exec_result(MagicMock()), _floor_exec_result(MagicMock())]
    monkeypatch.setattr(rm, "four_color_temp_dir", MagicMock(return_value=None))
    with pytest.raises(HTTPException) as exc:
        await rm.cancel_four_color_import("bad-token", "f-1", "e-1", current_user=MagicMock(), db=db)
    assert exc.value.status_code == 404


# ── Schema：干扰过滤扩展 ──


def test_analyze_response_accepts_excluded_and_texts():
    resp = FourColorAnalyzeResponse(
        preview_url="/uploads/x.png",
        canvas_width=1200,
        canvas_height=900,
        zones=[FourColorDraftZone(
            client_id="d1",
            name="分区1",
            risk_level="重大",
            color="#ff4d4f",
            suspected=True,
            suggested_name="原料库",
            ai_hint="疑似Logo",
            polygons=[{"id": "p1", "points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}]}],
        )],
        excluded=[FourColorExcludedItem(
            color="红",
            reason="legend",
            polygons=[{"id": "p2", "points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}]}],
        )],
        texts=[FourColorTextItem(
            points=[{"x": 1, "y": 2}, {"x": 3, "y": 2}, {"x": 3, "y": 4}, {"x": 1, "y": 4}],
            text="原料库",
            confidence=0.9,
        )],
    )
    assert resp.zones[0].suspected is True
    assert resp.zones[0].suggested_name == "原料库"
    assert resp.zones[0].ai_hint == "疑似Logo"
    assert resp.excluded[0].reason == "legend"
    assert resp.texts[0].text == "原料库"


def test_excluded_item_rejects_unknown_reason():
    with pytest.raises(ValidationError):
        FourColorExcludedItem(color="红", reason="mystery", polygons=[{"id": "p", "points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}]}])
