"""抽取 API：列映射建议、触发抽取、上传解析。"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.dependencies import require_admin
from app.middleware.rate_limit import rate_limited
from app.schemas.extraction import RunExtractionIn, SuggestMappingIn
from app.services.ai_config_service import get_system_ai_config
from app.services.extraction_prompts import ENTITY_SCHEMAS, ExtractionSchemaError
from app.services.extraction_service import extract_candidates
from app.services.file_parser import parse_file_text
from app.services.schema_matching import suggest_mapping
from app.services.db_guard import release_request_connection

router = APIRouter(prefix="/extraction", tags=["Extraction"], dependencies=[Depends(require_admin)])


def _ok(data):
    return {"success": True, "code": 200, "message": "success", "data": data}


@router.post("/suggest-mapping")
async def api_suggest_mapping(payload: SuggestMappingIn, db: AsyncSession = Depends(get_db)):
    """给出「表格列 → 目标字段」的映射建议。AI 不可用时退回精确匹配。"""
    ai_config = await get_system_ai_config(db)
    await release_request_connection(db)  # 长耗时 AI 调用前把连接还池，避免 idle in transaction 占满池（压测 N-32）
    out = await suggest_mapping(
        headers=payload.headers, target_entity=payload.target_entity, ai_config=ai_config
    )
    return _ok(out)


@router.post("/run")
async def api_run_extraction(
    payload: RunExtractionIn,
    db: AsyncSession = Depends(get_db),
    _: None = rate_limited(limit=60, window_seconds=3600, scope="extraction_run"),
):
    """对已解析的文本执行抽取，结果落 DataHub 待确认队列。"""
    if payload.target_entity not in ENTITY_SCHEMAS:
        raise HTTPException(422, f"未知目标实体：{payload.target_entity}")
    ai_config = await get_system_ai_config(db)
    if ai_config is None:
        raise HTTPException(400, "尚未配置系统级 AI 模型，请先在系统设置中配置")
    try:
        out = await extract_candidates(
            db,
            job_id=payload.job_id,
            source_id=payload.source_id,
            target_entity=payload.target_entity,
            text=payload.text,
            filename=payload.filename,
            ai_config=ai_config,
        )
    except ExtractionSchemaError as exc:
        raise HTTPException(422, str(exc)) from exc
    # 抽取完成后回填任务计数：否则任务列表里新任务一直显示「进行中 / 0 条」。
    from app.models.ingest import IngestJob
    from app.services.ingest_service import update_job_counts

    job = (
        await db.execute(select(IngestJob).where(IngestJob.id == payload.job_id))
    ).scalar_one_or_none()
    if job is not None:
        await update_job_counts(db, job=job)
    return _ok(out)


@router.post("/parse-file")
async def api_parse_file(
    file: UploadFile = File(...),
    _: None = rate_limited(limit=30, window_seconds=3600, scope="extraction_parse"),
):
    """上传文件并转成文本，返回文本供前端预览后再触发抽取。"""
    # W0 安全修复：限制单文件大小，避免匿名/超限上传耗尽内存
    max_bytes = 20 * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, "文件超过 20MB 上限")
    if not data:
        raise HTTPException(422, "文件为空")
    try:
        text = parse_file_text(file.filename or "upload", data)
    except Exception as exc:
        raise HTTPException(422, f"文件解析失败：{exc}") from exc
    return _ok({"filename": file.filename, "chars": len(text), "text": text})
