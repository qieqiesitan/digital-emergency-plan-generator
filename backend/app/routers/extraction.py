"""抽取 API：列映射建议、触发抽取、上传解析。"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.extraction import RunExtractionIn, SuggestMappingIn
from app.services.ai_config_service import get_system_ai_config
from app.services.extraction_prompts import ENTITY_SCHEMAS, ExtractionSchemaError
from app.services.extraction_service import extract_candidates
from app.services.file_parser import parse_file_text
from app.services.schema_matching import suggest_mapping

router = APIRouter(prefix="/extraction", tags=["Extraction"])


def _ok(data):
    return {"success": True, "code": 200, "message": "success", "data": data}


@router.post("/suggest-mapping")
async def api_suggest_mapping(payload: SuggestMappingIn, db: AsyncSession = Depends(get_db)):
    """给出「表格列 → 目标字段」的映射建议。AI 不可用时退回精确匹配。"""
    ai_config = await get_system_ai_config(db)
    out = await suggest_mapping(
        headers=payload.headers, target_entity=payload.target_entity, ai_config=ai_config
    )
    return _ok(out)


@router.post("/run")
async def api_run_extraction(payload: RunExtractionIn, db: AsyncSession = Depends(get_db)):
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
    return _ok(out)


@router.post("/parse-file")
async def api_parse_file(file: UploadFile = File(...)):
    """上传文件并转成文本，返回文本供前端预览后再触发抽取。"""
    data = await file.read()
    if not data:
        raise HTTPException(422, "文件为空")
    try:
        text = parse_file_text(file.filename or "upload", data)
    except Exception as exc:
        raise HTTPException(422, f"文件解析失败：{exc}") from exc
    return _ok({"filename": file.filename, "chars": len(text), "text": text})
