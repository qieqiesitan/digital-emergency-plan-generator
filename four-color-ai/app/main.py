"""四色分布图识别独立服务：无状态推理，X-API-Key 鉴权。"""
import os

from fastapi import Depends, FastAPI, Header, HTTPException

API_KEY_ENV = "FOUR_COLOR_API_KEY"

app = FastAPI(title="four-color-ai", version="1.0.0")


def require_api_key(x_api_key: str = Header(default="", alias="X-API-Key")) -> None:
    expected = os.environ.get(API_KEY_ENV, "")
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid api key")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/api/v1/four-color/analyze")
def analyze(_: None = Depends(require_api_key)) -> dict:
    raise HTTPException(status_code=501, detail="not implemented yet")
