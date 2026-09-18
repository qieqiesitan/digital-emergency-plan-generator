"""上传体积守卫与分页夹紧（2026-09-18 审计新增防护）。"""

import io

import pytest
from fastapi import HTTPException, UploadFile

from app.services.pagination import clamp_page, clamp_page_size
from app.services.upload_guard import read_upload_capped


def _upload(payload: bytes, filename: str = "f.bin") -> UploadFile:
    return UploadFile(file=io.BytesIO(payload), filename=filename)


@pytest.mark.asyncio
async def test_read_upload_capped_allows_within_limit():
    data = await read_upload_capped(_upload(b"abcd"), 10, what="测试文件")
    assert data == b"abcd"


@pytest.mark.asyncio
async def test_read_upload_capped_rejects_oversize():
    with pytest.raises(HTTPException) as exc:
        await read_upload_capped(_upload(b"x" * 11), 10, what="测试文件")
    assert exc.value.status_code == 413
    assert "测试文件" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_read_upload_capped_accepts_exact_limit():
    data = await read_upload_capped(_upload(b"x" * 10), 10)
    assert len(data) == 10


def test_clamp_page_size_bounds():
    assert clamp_page_size(10_000_000) == 100
    assert clamp_page_size(0) == 1
    assert clamp_page_size("abc") == 20
    assert clamp_page_size(None) == 20
    assert clamp_page_size(50) == 50


def test_clamp_page_bounds():
    assert clamp_page(0) == 1
    assert clamp_page(-5) == 1
    assert clamp_page("x") == 1
    assert clamp_page(7) == 7
