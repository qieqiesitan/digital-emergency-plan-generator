from io import BytesIO

import pytest
from fastapi import HTTPException
from PIL import Image

from app.services.floor_plan_storage_service import UPLOAD_DIR, remove_floor_plan, save_floor_plan


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
async def test_save_valid_png_then_remove():
    buf = BytesIO()
    Image.new("RGB", (120, 80), "white").save(buf, format="PNG")
    buf.seek(0)

    class FakeUpload:
        content_type = "image/png"
        filename = "plan.png"
        async def read(self):
            return buf.read()

    url, width, height = await save_floor_plan("e-1", "f-1", FakeUpload())
    assert url.startswith("/uploads/enterprises/e-1/floors/f-1/")
    assert (width, height) == (120, 80)
    target = UPLOAD_DIR / url.removeprefix("/uploads/")
    assert target.exists()
    remove_floor_plan(url)
    assert not target.exists()
