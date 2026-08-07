"""四色识别服务服务级测试：healthz、鉴权、analyze 各分支。"""
import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import app

client = TestClient(app)

API_KEY = "test-key"


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    monkeypatch.setenv("FOUR_COLOR_API_KEY", API_KEY)


def _four_rect_png(width=600, height=450) -> bytes:
    img = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(img)
    for x0, y0, x1, y1, color in [
        (40, 40, 280, 180, (255, 0, 0)),
        (320, 40, 560, 180, (255, 127, 0)),
        (40, 230, 280, 410, (255, 255, 0)),
        (320, 230, 560, 410, (0, 0, 255)),
    ]:
        d.rectangle([x0, y0, x1, y1], fill=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_healthz_returns_200():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_analyze_requires_api_key():
    resp = client.post("/api/v1/four-color/analyze", json={})
    assert resp.status_code == 401


def test_analyze_rejects_wrong_api_key():
    resp = client.post(
        "/api/v1/four-color/analyze",
        headers={"X-API-Key": "wrong"},
        json={"image_base64": base64.b64encode(_four_rect_png()).decode("ascii")},
    )
    assert resp.status_code == 401
