"""四色分布图识别独立服务：无状态推理，X-API-Key 鉴权。"""
import base64
import os
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.services.four_color_recognizer import build_output_image, recognize_from_bytes

API_KEY_ENV = "FOUR_COLOR_API_KEY"

app = FastAPI(title="four-color-ai", version="1.0.0")


def require_api_key(x_api_key: str = Header(default="", alias="X-API-Key")) -> None:
    expected = os.environ.get(API_KEY_ENV, "")
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid api key")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


class Options(BaseModel):
    max_zones: int = 200
    canvas_width: int = 1600
    canvas_height: int = 1000
    enable_ocr: bool = True
    enable_clip: bool = True


class AnalyzeRequest(BaseModel):
    image_base64: str
    options: Options = Field(default_factory=Options)


@app.post("/api/v1/four-color/analyze")
def analyze(body: AnalyzeRequest, _: None = Depends(require_api_key)) -> dict:
    try:
        raw = base64.b64decode(body.image_base64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail={"code": "INVALID_IMAGE", "message": "图片 base64 解码失败"})
    try:
        result = recognize_from_bytes(raw)
    except RuntimeError:
        raise HTTPException(status_code=503, detail={"code": "MODEL_UNAVAILABLE", "message": "识别模型未加载"})
    except Exception:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL", "message": "识别管线异常"})
    if not result.zones:
        raise HTTPException(status_code=422, detail={"code": "NO_ZONE_DETECTED", "message": "未识别到红/橙/黄/蓝色块"})
    if result.processed_image is None:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL", "message": "识别管线未产出预览图"})
    png_bytes, cw, ch = build_output_image(
        result.processed_image,
        result.width,
        result.height,
        max_size=(body.options.canvas_width, body.options.canvas_height),
    )
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "request_id": uuid4().hex,
            "width": result.width,
            "height": result.height,
            "canvas_width": cw,
            "canvas_height": ch,
            "preview_png_base64": base64.b64encode(png_bytes).decode("ascii"),
            "zones": result.zones,
            "texts": result.texts,
            "excluded": result.excluded,
            "warnings": result.warnings,
        },
    }
