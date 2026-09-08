import os
import sys
import uuid as uuid_lib
from contextlib import asynccontextmanager
import logging
from pathlib import Path as _Path
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from app.config import settings
from app.database import async_session
from app.routers import chat, auth, users, enterprises, enterprise_sub, enterprise_org, hazard_management, plans, sections, templates, versions, review, ai_config, dashboard, generation, export, export_tasks, risk_assessment, resource_investigation, risk_sources_ext, risk_management, resources_ext, surrounding_ai, hazardous_chemicals, prompts, config, roles, admin_users, external, regulations, diagrams, onboarding, risk_notice_card, public_risk_notice, public_risk, public_hazard, chemical_library, data_dicts, third_party_config
from app.models.report_version import ResourceInvestigationVersion, RiskAssessmentVersion
from app.models.risk_assessment import RiskAssessmentReport
from app.models.resource_investigation import ResourceInvestigationReport
from app.routers.report_versions import build_report_versions_router
from app.dependencies import get_current_user
from app.services.mermaid_renderer import _close_browser
from app.services.migration_runner import run_migrations
from app.middleware.hmac_auth import HmacAuthMiddleware

logger = logging.getLogger(__name__)


def _is_asyncpg_data_error(exc: BaseException) -> bool:
    """沿异常链查找 asyncpg 数据层错误（非法 UUID / 超长字段等）。"""
    import asyncpg

    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, asyncpg.exceptions.DataError):
            return True
        # SQLAlchemy 包装层链：StatementError.orig / DBAPIError.original_exception /
        # Python 隐式 __cause__ / __context__
        nxt = (
            getattr(exc, "orig", None)
            or getattr(exc, "original_exception", None)
            or exc.__cause__
            or exc.__context__
        )
        if not isinstance(nxt, BaseException):
            break
        exc = nxt
    return False

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# P0-2 安全加固：上传类型白名单与大小上限。
# 覆盖业务场景：企业 logo/检查照片（image/*）、组织架构导入（.xlsx）等。
UPLOAD_ALLOWED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".txt", ".csv", ".json",
}
UPLOAD_MAX_BYTES = 20 * 1024 * 1024

# 静态访问时强制下载的危险类型（历史遗留 .html/.svg/.xml/.php/.sh/.bat/.exe 等）
_RISKY_STATIC_EXTS = {
    ".html", ".htm", ".svg", ".xml", ".xhtml", ".php", ".phtml",
    ".sh", ".bat", ".cmd", ".exe", ".msi", ".js", ".mjs", ".vbs",
    ".jsp", ".asp", ".aspx", ".cgi", ".pl",
}


def _ext_from_filename(filename: str) -> str:
    """取小写扩展名；多段后缀取最后一段。"""
    return os.path.splitext(filename or "")[1].lower()


def _content_type_from_ext(ext: str) -> str:
    """上传落库统一以白名单扩展名推导 Content-Type，避免客户端伪造。"""
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".json": "application/json",
    }.get(ext, "application/octet-stream")


def _is_risky_static_ext(ext: str) -> bool:
    """扩展名是否属于可执行/内联渲染风险类型。"""
    return ext in _RISKY_STATIC_EXTS


def _is_allowed_upload(filename: str, content_type: str) -> bool:
    """上传校验：扩展名必须在白名单，且 Content-Type 与扩展名推导一致
    （为空时按扩展名放行；不一致视为伪装攻击拒绝）。"""
    ext = _ext_from_filename(filename)
    if ext not in UPLOAD_ALLOWED_EXTENSIONS:
        return False
    normalized = _content_type_from_ext(ext)
    if not content_type:
        return True
    client_mime = (content_type or "").split(";")[0].strip().lower()
    return client_mime == normalized


class UploadsStaticFiles(StaticFiles):
    """uploads 静态服务：危险类型强制附件下载 + nosniff，阻断内联执行。"""

    def file_response(self, full_path, stat_result, scope, status_code=200):
        response = super().file_response(full_path, stat_result, scope, status_code)
        basename = os.path.basename(full_path)
        ext = _ext_from_filename(basename)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if _is_risky_static_ext(ext):
            response.headers["Content-Disposition"] = f'attachment; filename="{basename}"'
            response.headers["Content-Type"] = "application/octet-stream"
        return response


FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
DEPLOY_DIST = os.environ.get("DEPLOY_DIST", "")
if DEPLOY_DIST:
    FRONTEND_DIST = DEPLOY_DIST

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动接线：迁移运行器在 advisory lock 内执行 create_all（幂等补建缺失表）
    # 并应用未记录迁移（失败 fail-fast 中止启动），随后导入第三方配置 seed。
    try:
        await run_migrations()
    except Exception:
        logger.critical("数据库迁移失败，服务中止启动", exc_info=True)
        sys.exit(1)
    from app.services.third_party_config import import_seed_configs
    await import_seed_configs()
    # 任务 8：APScheduler 隐患定时扫描（每 5 分钟）。依赖缺失/启动异常仅告警降级，
    # 不阻塞服务启动（规格 §16）；外部 cron 可退化为调用 run_hazard_scans 的内部端点。
    scheduler = None
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from app.services.hazard_scheduler import run_hazard_scans

        async def _run_hazard_scans_job() -> None:
            async with async_session() as session:
                await run_hazard_scans(session)

        scheduler = AsyncIOScheduler()
        scheduler.add_job(_run_hazard_scans_job, "interval", minutes=5,
                          id="hazard_scans", replace_existing=True)
        scheduler.start()
    except Exception:
        logger.warning("APScheduler 启动失败，隐患定时扫描已降级跳过（不影响服务启动）", exc_info=True)
        scheduler = None
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    await _close_browser()

app = FastAPI(title="Digital Emergency Plan Generator", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def _security_headers(request, call_next):
    """QA #7：补齐安全响应头（API 响应）。"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    return response


@app.middleware("http")
async def _db_data_error_to_422(request, call_next):
    """非法 UUID / 超长字段等 asyncpg 数据错误：500 → 422，防内部细节泄露。

    放在最外层（后注册先执行），捕获经由 Starlette 异常中间件重抛的
    StatementError/asyncpg 数据错误；其余异常继续走框架默认 500 路径。
    """
    try:
        return await call_next(request)
    except Exception as exc:  # noqa: BLE001 - 需检查后决定是否重抛
        if _is_asyncpg_data_error(exc):
            logger.warning("数据库参数校验失败（已转 422）: %s", type(exc).__name__)
            return JSONResponse(
                status_code=422,
                content={
                    "detail": "请求参数无效（如 ID 格式错误或字段超长），请检查后重试"
                },
            )
        raise

app.add_middleware(HmacAuthMiddleware)


def _resolve_cors_origins(raw: str | None = None) -> list[str]:
    """从 CORS_ORIGINS（逗号分隔）解析 CORS 白名单；未配置时回退本地开发源。"""
    if raw is None:
        raw = settings.CORS_ORIGINS or ""
    raw = raw.strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return ["http://localhost:5173", "http://localhost:8082"]


# 安全加固（S5）：allow_credentials=True 与 allow_origins=["*"] 组合非法且危险，
# 故显式配置通配符时强制关闭 credentials。
CORS_ORIGINS = _resolve_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials="*" not in CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", UploadsStaticFiles(directory=UPLOAD_DIR), name="uploads")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")
    if os.path.isdir(os.path.join(FRONTEND_DIST, "icons")):
        app.mount("/icons", StaticFiles(directory=os.path.join(FRONTEND_DIST, "icons")), name="icons")
SIGNS_DIR = _Path(__file__).resolve().parent / "static" / "signs"
SIGNS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/signs", StaticFiles(directory=str(SIGNS_DIR)), name="signs")

@app.post("/api/v1/upload")
async def upload_file(file: UploadFile = File(...), _=Depends(get_current_user)):
    filename = file.filename or ""
    ext = _ext_from_filename(filename)
    if not _is_allowed_upload(filename, file.content_type or ""):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型（{ext or '无扩展名'}）。"
            "仅允许图片（png/jpg/jpeg/gif/webp/bmp）及 pdf/doc/docx/xls/xlsx/txt/csv/json。",
        )
    data = await file.read(UPLOAD_MAX_BYTES + 1)
    if len(data) > UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=413, detail="文件超过 20MB 上限")
    safe_name = f"{uuid_lib.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        f.write(data)
    return {"code": 0, "data": {"url": f"/uploads/{safe_name}"}}

app.include_router(chat.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(enterprises.router, prefix="/api/v1")
app.include_router(enterprise_sub.router, prefix="/api/v1")
app.include_router(enterprise_org.router, prefix="/api/v1")
app.include_router(hazard_management.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(sections.router, prefix="/api/v1")
app.include_router(generation.router, prefix="/api/v1")
app.include_router(templates.router, prefix="/api/v1")
app.include_router(versions.router, prefix="/api/v1")
app.include_router(review.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")
app.include_router(export_tasks.router, prefix="/api/v1")
app.include_router(ai_config.router, prefix="/api/v1")
app.include_router(risk_assessment.router, prefix="/api/v1")
app.include_router(resource_investigation.router, prefix="/api/v1")
app.include_router(build_report_versions_router("risk-assessment", RiskAssessmentReport, RiskAssessmentVersion), prefix="/api/v1")
app.include_router(build_report_versions_router("resource-investigation", ResourceInvestigationReport, ResourceInvestigationVersion), prefix="/api/v1")
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
app.include_router(public_hazard.router, prefix="/api/v1")
app.include_router(chemical_library.router, prefix="/api/v1")
app.include_router(data_dicts.router, prefix="/api/v1")
app.include_router(third_party_config.router, prefix="/api/v1")

@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    # API 未知路径返回 JSON 404，避免 catch-all 把 /api/* 兜成 SPA HTML
    if full_path.startswith("api/"):
        return JSONResponse(status_code=404, content={"detail": "接口不存在"})
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
