"""四色图导入 API：存储辅助、schema、analyze/commit/cancel 端点（mock db，不依赖数据库）。"""
import io
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw

import app.services.floor_plan_storage_service as fss
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
