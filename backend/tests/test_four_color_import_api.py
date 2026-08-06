"""四色图导入 API：存储辅助、schema、analyze/commit/cancel 端点（mock db，不依赖数据库）。"""
import io
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw
from pydantic import ValidationError

import app.services.floor_plan_storage_service as fss
from app.schemas.risk_management import (
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
