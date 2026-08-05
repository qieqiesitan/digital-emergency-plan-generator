from io import BytesIO

import pytest
from fastapi import HTTPException
from PIL import Image

import app.services.floor_plan_storage_service as fps
from app.services.floor_plan_storage_service import MAX_BYTES, remove_floor_plan, remove_floor_plan_dir, save_floor_plan


def _png_buf(width: int = 120, height: int = 80) -> BytesIO:
    buf = BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, format="PNG")
    buf.seek(0)
    return buf


@pytest.mark.asyncio
async def test_reject_non_image():
    class FakeUpload:
        content_type = "text/plain"
        filename = "a.txt"
        async def read(self):
            return b"x"
    try:
        await save_floor_plan("e", "f", FakeUpload())
        assert False
    except HTTPException as exc:
        assert exc.status_code == 422


@pytest.mark.asyncio
async def test_save_valid_png_then_remove(tmp_path, monkeypatch):
    monkeypatch.setattr(fps, "UPLOAD_DIR", tmp_path)
    class FakeUpload:
        content_type = "image/png"
        filename = "plan.png"
        async def read(self):
            return _png_buf().read()

    url, width, height = await save_floor_plan("e-1", "f-1", FakeUpload())
    assert url.startswith("/uploads/enterprises/e-1/floors/f-1/")
    assert (width, height) == (120, 80)
    target = tmp_path / url.removeprefix("/uploads/")
    assert target.exists()
    remove_floor_plan(url)
    assert not target.exists()


@pytest.mark.asyncio
async def test_reject_oversized_by_content_length(tmp_path, monkeypatch):
    monkeypatch.setattr(fps, "UPLOAD_DIR", tmp_path)

    class FakeUpload:
        content_type = "image/png"
        filename = "big.png"
        size = MAX_BYTES + 1
        headers = {}
        async def read(self):
            return b""

    with pytest.raises(HTTPException) as exc_info:
        await save_floor_plan("e-1", "f-1", FakeUpload())
    assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_extension_derived_from_content_type(tmp_path, monkeypatch):
    monkeypatch.setattr(fps, "UPLOAD_DIR", tmp_path)
    buf = BytesIO()
    Image.new("RGB", (10, 10), "white").save(buf, format="JPEG")
    buf.seek(0)

    class FakeUpload:
        content_type = "image/jpeg"
        filename = "plan.html"
        async def read(self):
            return buf.read()

    url, width, height = await save_floor_plan("e-2", "f-2", FakeUpload())
    assert url.endswith(".jpg")
    assert ".html" not in url
    assert (width, height) == (10, 10)
    remove_floor_plan(url)
    remove_floor_plan_dir("e-2", "f-2")


def test_remove_floor_plan_blocks_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(fps, "UPLOAD_DIR", tmp_path)
    outside = tmp_path.parent / "traversal_target.txt"
    outside.write_text("keep")
    try:
        # /uploads/../xxx 解析后位于上传目录之外，必须拒绝删除
        remove_floor_plan(f"/uploads/../{outside.name}")
        assert outside.exists()
    finally:
        outside.unlink(missing_ok=True)


def test_normalize_floor_plan_url_rejects_non_uploads():
    assert fps.normalize_floor_plan_url(None) is None
    assert fps.normalize_floor_plan_url("") is None
    assert fps.normalize_floor_plan_url("/uploads/enterprises/e/f.png") == "/uploads/enterprises/e/f.png"
    for bad in ("https://evil.com/x.png", "uploads/x.png", "/uploads/../../app/main.py", "/uploads/a/../b.png"):
        with pytest.raises(HTTPException):
            fps.normalize_floor_plan_url(bad)


def test_remove_floor_plan_dir_removes_floor_files(tmp_path, monkeypatch):
    monkeypatch.setattr(fps, "UPLOAD_DIR", tmp_path)
    target = tmp_path / "enterprises" / "e-9" / "floors" / "f-9"
    target.mkdir(parents=True)
    (target / "a.png").write_bytes(b"x")
    fps.remove_floor_plan_dir("e-9", "f-9")
    assert not target.exists()


def test_remove_enterprise_uploads_removes_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(fps, "UPLOAD_DIR", tmp_path)
    target = tmp_path / "enterprises" / "e-9"
    (target / "floors" / "f-9").mkdir(parents=True)
    (target / "floors" / "f-9" / "a.png").write_bytes(b"x")
    fps.remove_enterprise_uploads("e-9")
    assert not target.exists()
