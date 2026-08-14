import os
import uuid as uuid_lib
from contextlib import asynccontextmanager
from pathlib import Path as _Path
from fastapi import FastAPI, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from app.database import engine, Base
from app.routers import chat, auth, users, enterprises, enterprise_sub, enterprise_org, plans, sections, templates, versions, ai_config, dashboard, generation, export, export_tasks, risk_assessment, resource_investigation, risk_sources_ext, risk_management, resources_ext, surrounding_ai, hazardous_chemicals, prompts, config, roles, admin_users, external, regulations, diagrams, onboarding, risk_notice_card, public_risk_notice, public_risk, data_dicts
from app.dependencies import get_current_user
from app.services.mermaid_renderer import _close_browser
from app.middleware.hmac_auth import HmacAuthMiddleware

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
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

app.add_middleware(HmacAuthMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")
    if os.path.isdir(os.path.join(FRONTEND_DIST, "icons")):
        app.mount("/icons", StaticFiles(directory=os.path.join(FRONTEND_DIST, "icons")), name="icons")
SIGNS_DIR = _Path(__file__).resolve().parent / "static" / "signs"
SIGNS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/signs", StaticFiles(directory=str(SIGNS_DIR)), name="signs")

@app.post("/api/v1/upload")
async def upload_file(file: UploadFile = File(...), _=Depends(get_current_user)):
    ext = os.path.splitext(file.filename or "image.png")[1] or ".png"
    safe_name = f"{uuid_lib.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    return {"code": 0, "data": {"url": f"/uploads/{safe_name}"}}

app.include_router(chat.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(enterprises.router, prefix="/api/v1")
app.include_router(enterprise_sub.router, prefix="/api/v1")
app.include_router(enterprise_org.router, prefix="/api/v1")
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
app.include_router(risk_management.router, prefix="/api/v1")
app.include_router(resources_ext.router, prefix="/api/v1")
app.include_router(surrounding_ai.router, prefix="/api/v1")
app.include_router(hazardous_chemicals.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(prompts.router, prefix="/api/v1")
app.include_router(config.router, prefix="/api/v1")
app.include_router(roles.router, prefix="/api/v1")
app.include_router(admin_users.router, prefix="/api/v1")
app.include_router(external.router, prefix="/api")
app.include_router(regulations.router, prefix="/api/v1")
app.include_router(diagrams.router, prefix="/api/v1")
app.include_router(onboarding.router, prefix="/api/v1")
app.include_router(risk_notice_card.router, prefix="/api/v1")
app.include_router(public_risk_notice.router, prefix="/api/v1")
app.include_router(public_risk.router, prefix="/api/v1")
app.include_router(data_dicts.router, prefix="/api/v1")

@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if not os.path.isdir(FRONTEND_DIST):
        return {"detail": "Frontend not built"}, 404
    file_path = os.path.join(FRONTEND_DIST, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    if full_path.startswith("m") or full_path.startswith("m/"):
        mobile_html = os.path.join(FRONTEND_DIST, "m.html")
        if os.path.isfile(mobile_html):
            return FileResponse(mobile_html)
    index_html = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.isfile(index_html):
        return FileResponse(index_html)
    return {"detail": "Not found"}, 404
