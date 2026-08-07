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


def _analyze_payload(png: bytes, options: dict | None = None) -> dict:
    return {
        "image_base64": base64.b64encode(png).decode("ascii"),
        "options": options or {},
    }


def test_analyze_happy_path_with_canvas_options():
    png = _four_rect_png()
    resp = client.post(
        "/api/v1/four-color/analyze",
        headers={"X-API-Key": API_KEY},
        json=_analyze_payload(png, {"canvas_width": 800, "canvas_height": 600}),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["canvas_width"] == 800
    assert data["canvas_height"] == 600
    assert len(data["zones"]) == 4
    assert data["preview_png_base64"].startswith("iVBOR")
    for zone in data["zones"]:
        for poly in zone["polygons"]:
            for point in poly["points"]:
                assert 0 <= point["x"] <= 100
                assert 0 <= point["y"] <= 100


def test_analyze_invalid_base64_returns_400():
    resp = client.post(
        "/api/v1/four-color/analyze",
        headers={"X-API-Key": API_KEY},
        json={"image_base64": "!!!not-base64!!!", "options": {}},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_IMAGE"


def test_analyze_no_zone_returns_422():
    white = Image.new("RGB", (300, 200), "white")
    buf = io.BytesIO()
    white.save(buf, format="PNG")
    resp = client.post(
        "/api/v1/four-color/analyze",
        headers={"X-API-Key": API_KEY},
        json=_analyze_payload(buf.getvalue()),
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "NO_ZONE_DETECTED"


def test_analyze_pipeline_error_returns_500(monkeypatch):
    def boom(_data):
        raise ValueError("pipeline boom")

    monkeypatch.setattr("app.main.recognize_from_bytes", boom)
    resp = client.post(
        "/api/v1/four-color/analyze",
        headers={"X-API-Key": API_KEY},
        json=_analyze_payload(_four_rect_png()),
    )
    assert resp.status_code == 500
    assert resp.json()["detail"]["code"] == "INTERNAL"


def test_analyze_model_unavailable_returns_503(monkeypatch):
    def no_model(_data):
        raise RuntimeError("缺少 opencv-python-headless 依赖")

    monkeypatch.setattr("app.main.recognize_from_bytes", no_model)
    resp = client.post(
        "/api/v1/four-color/analyze",
        headers={"X-API-Key": API_KEY},
        json=_analyze_payload(_four_rect_png()),
    )
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "MODEL_UNAVAILABLE"
