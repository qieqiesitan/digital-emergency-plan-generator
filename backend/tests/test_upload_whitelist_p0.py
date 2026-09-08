"""P0-2 上传白名单与静态服务加固回归测试（2026-09-08 QA 报告 #2 / S2）。

- /api/v1/upload 仅允许白名单扩展名与 MIME，超限返回 4xx。
- /uploads 静态服务对危险类型强制 Content-Disposition: attachment，
  避免历史遗留文件以 text/html 内联执行（存储型 XSS 面关闭）。
"""

from app.main import (
    UPLOAD_ALLOWED_EXTENSIONS,
    UPLOAD_MAX_BYTES,
    _content_type_from_ext,
    _ext_from_filename,
    _is_allowed_upload,
    _is_risky_static_ext,
)


# ── 工具函数单元测试 ──

def test_allowed_extensions_cover_business_images():
    for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
        assert ext in UPLOAD_ALLOWED_EXTENSIONS


def test_allowed_extensions_cover_org_import_xlsx():
    assert ".xlsx" in UPLOAD_ALLOWED_EXTENSIONS


def test_risky_extensions_not_allowed():
    for ext in (".html", ".htm", ".svg", ".xml", ".exe", ".sh", ".bat", ".php", ".js", ".bin"):
        assert ext not in UPLOAD_ALLOWED_EXTENSIONS


def test_extension_parsing_case_insensitive():
    assert _ext_from_filename("LOGO.PNG") == ".png"
    assert _ext_from_filename("plan.JpEg") == ".jpeg"
    assert _ext_from_filename("noext") == ""
    assert _ext_from_filename("evil.html.exe") == ".exe"


def test_upload_guard_accepts_image_and_rejects_html():
    assert _is_allowed_upload("photo.png", "image/png") is True
    assert _is_allowed_upload("page.html", "text/html") is False
    assert _is_allowed_upload("img.svg", "image/svg+xml") is False
    # 扩展名伪装：后缀合法但 MIME 危险仍需拒绝
    assert _is_allowed_upload("trick.html", "image/png") is False
    # MIME 缺失时按扩展名判断
    assert _is_allowed_upload("photo.png", "") is True


def test_content_type_from_ext():
    assert _content_type_from_ext(".png") == "image/png"
    assert _content_type_from_ext(".xlsx") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert _content_type_from_ext(".unknown") == "application/octet-stream"


def test_max_size_is_20mb():
    assert UPLOAD_MAX_BYTES == 20 * 1024 * 1024


def test_risky_static_exts():
    assert _is_risky_static_ext(".html") is True
    assert _is_risky_static_ext(".svg") is True
    assert _is_risky_static_ext(".png") is False


# ── API 集成测试 ──

def _upload_through_api(filename: str, content_type: str, content: bytes = b"x"):
    """通过 ASGI 调用 /api/v1/upload（override 认证与 DB 依赖）。"""
    import asyncio

    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.dependencies import get_current_user
    from app.database import get_db
    from app.models.user import User

    user = User(id="u-up", email="up@test.com", role="user", password_hash="x")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: None

    async def run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            files = {"file": (filename, content, content_type)}
            resp = await client.post("/api/v1/upload", files=files)
        return resp.status_code, resp.text

    try:
        return asyncio.run(run())
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_upload_api_rejects_html():
    status, body = _upload_through_api("evil.html", "text/html")
    assert status == 400
    assert "不支持的文件类型" in body


def test_upload_api_rejects_svg_even_with_image_mime():
    status, _ = _upload_through_api("logo.svg", "image/svg+xml")
    assert status == 400


def test_upload_api_rejects_mime_disguise():
    # 扩展名伪装：名为 .png 但 content_type 为 text/html
    status, _ = _upload_through_api("photo.png", "text/html")
    assert status == 400


def test_upload_api_accepts_png_and_returns_uploads_url():
    """真实写入临时文件后删除：验证白名单通过且返回结构正确。"""
    import os
    import re

    from app.main import UPLOAD_DIR

    status, body = _upload_through_api("photo.png", "image/png", b"\x89PNG-fake")
    assert status == 200
    m = re.search(r'"/uploads/([0-9a-f]{32}\.png)"', body)
    assert m is not None
    created = os.path.join(UPLOAD_DIR, m.group(1))
    assert os.path.isfile(created)
    os.remove(created)


def test_static_html_served_as_attachment():
    """历史遗留 .html 文件静态访问必须强制附件下载而非 text/html 内联。"""
    import os
    import asyncio

    from httpx import ASGITransport, AsyncClient
    from app.main import app, UPLOAD_DIR

    marker = os.path.join(UPLOAD_DIR, "p0_whitelist_probe.html")
    with open(marker, "w", encoding="utf-8") as f:
        f.write("<html><script>alert(1)</script></html>")

    async def run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/uploads/p0_whitelist_probe.html")
        return resp

    try:
        resp = asyncio.run(run())
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("application/octet-stream")
        assert "attachment" in resp.headers.get("content-disposition", "")
        assert resp.headers.get("x-content-type-options") == "nosniff"
    finally:
        os.remove(marker)
