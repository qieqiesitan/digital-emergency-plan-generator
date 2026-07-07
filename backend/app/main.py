import os
import uuid as uuid_lib
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from app.database import engine, Base
from app.routers import auth, users, enterprises, enterprise_sub, plans, sections, templates, versions, ai_config, dashboard, generation, export, export_tasks, risk_assessment, resource_investigation, risk_sources_ext, resources_ext, surrounding_ai, hazardous_chemicals, prompts, config, roles, admin_users, external
from app.dependencies import get_current_user
from app.services.mermaid_renderer import _close_browser
from app.middleware.hmac_auth import HmacAuthMiddleware

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Frontend dist directory (built SPA assets)
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
# Support DEPLOY_DIST env override for deployment on VM
DEPLOY_DIST = os.environ.get("DEPLOY_DIST", "")
if DEPLOY_DIST:
    FRONTEND_DIST = DEPLOY_DIST

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await _close_browser()

app = FastAPI(title="Digital Emergency Plan Generator", version="1.0.0", lifespan=lifespan)

# HMAC 签名验证（/api/external/* 端点）
app.add_middleware(HmacAuthMiddleware)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Static file mounts
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")
    app.mount("/icons", StaticFiles(directory=os.path.join(FRONTEND_DIST, "icons")), name="icons")

# File upload endpoint
@app.post("/api/v1/upload")
async def upload_file(file: UploadFile = File(...), _=Depends(get_current_user)):
    """Upload images such as floor plans"""
    ext = os.path.splitext(file.filename or "image.png")[1] or ".png"
    safe_name = f"{uuid_lib.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    return {"code": 0, "data": {"url": f"/uploads/{safe_name}"}}

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(enterprises.router, prefix="/api/v1")
app.include_router(enterprise_sub.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(sections.router, prefix="/api/v1")
app.include_router(generation.router, prefix="/api/v1")
app.include_router(templates.router, prefix="/api/v1")
app.include_router(versions.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")
app.include_router(export_tasks.router, prefix="/api/v1")
app.include_router(ai_config.router, prefix="/api/v1")
app.include_router(risk_assessment.router, prefix="/api/v1")
app.include_router(resource_investigation.router, prefix="/api/v1")
app.include_router(risk_sources_ext.router, prefix="/api/v1")
app.include_router(resources_ext.router, prefix="/api/v1")
app.include_router(surrounding_ai.router, prefix="/api/v1")
app.include_router(hazardous_chemicals.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(prompts.router, prefix="/api/v1")
app.include_router(config.router, prefix="/api/v1")
app.include_router(roles.router, prefix="/api/v1")
app.include_router(admin_users.router, prefix="/api/v1")
# 外部系统接入 API（PROTEGO 商城）
app.include_router(external.router, prefix="/api")

@app.get("/api/health")
async def health():
    return {"status": "ok"}

# SPA fallback: serves index.html (desktop) or m.html (mobile) for non-API routes
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if not os.path.isdir(FRONTEND_DIST):
        return {"detail": "Frontend not built"}, 404

    # API paths already handled by routers, this catches only static file requests
    # Serve specific static files first
    file_path = os.path.join(FRONTEND_DIST, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    # Mobile routes: fallback to m.html
    if full_path.startswith("m") or full_path.startswith("m/"):
        mobile_html = os.path.join(FRONTEND_DIST, "m.html")
        if os.path.isfile(mobile_html):
            return FileResponse(mobile_html)

    # Desktop SPA fallback
    index_html = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.isfile(index_html):
        return FileResponse(index_html)

    return {"detail": "Not found"}, 404
