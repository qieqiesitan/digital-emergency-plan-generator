from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.user import User
from app.routers.hazardous_chemicals import AIGenerateRequest, AIAnswerInput
from app.schemas.common import ApiResponse
from app.services.file_parser import parse_file_text
from app.services.onboarding_service import (
    classify_modules,
    compute_completion,
    extract_candidates,
    generate_org_candidates,
    get_enterprise_brief,
)

router = APIRouter(tags=["Onboarding"])


class CandidatesBody(BaseModel):
    enterprise_id: str
    module: str
    overview: str = ""
    existing_keys: list[str] = []


class ImportResult(BaseModel):
    module: str
    candidates: list[dict]
    source: str


def build_candidates_request(question: str, answer: str) -> AIGenerateRequest:
    """把一句概况包装成现有 AI 生成接口的 answers 结构。"""
    return AIGenerateRequest(
        answers=[AIAnswerInput(question_id="q0", question=question, answer=answer)]
    )


@router.get("/enterprises/{enterprise_id}/completion", response_model=ApiResponse[dict])
async def get_enterprise_completion(
    enterprise_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Enterprise).where(
        Enterprise.id == enterprise_id,
        Enterprise.user_id == current_user.id,
    ))
    ent = result.scalar_one_or_none()
    if not ent:
        raise HTTPException(status_code=404, detail="企业不存在")
    data = await compute_completion(enterprise_id, db, enterprise=ent)
    return ApiResponse(data=data)


@router.post("/onboarding/candidates", response_model=ApiResponse[dict])
async def onboarding_candidates(
    body: CandidatesBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """统一候选生成：org 走新增生成；其它模块由前端直接调用现有模块生成接口。"""
    if body.module == "org":
        result = await db.execute(select(Enterprise).where(
            Enterprise.id == body.enterprise_id,
            Enterprise.user_id == current_user.id,
        ))
        ent = result.scalar_one_or_none()
        if not ent:
            raise HTTPException(status_code=404, detail="企业不存在")
        brief = await get_enterprise_brief(body.enterprise_id, db, enterprise=ent)
        items = await generate_org_candidates(brief, db)
        return ApiResponse(data={"items": items})
    raise HTTPException(400, f"模块 {body.module} 请在前端接入现有生成接口")


@router.post("/onboarding/import", response_model=ApiResponse[ImportResult])
async def onboarding_import(
    module: str = "auto",
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await file.read()
    try:
        text = parse_file_text(file.filename or "", data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        target = module if module != "auto" else (await classify_modules(text, db))[0]
    except (ValueError, IndexError) as e:
        raise HTTPException(400, str(e) if isinstance(e, ValueError) else "未能识别资料所属模块")
    candidates = await extract_candidates(target, text, db)
    return ApiResponse(
        data=ImportResult(module=target, candidates=candidates, source=file.filename or "")
    )


@router.post("/onboarding/import/batch", response_model=ApiResponse[list[ImportResult]])
async def onboarding_import_batch(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results = []
    for file in files:
        data = await file.read()
        try:
            text = parse_file_text(file.filename or "", data)
        except ValueError as e:
            raise HTTPException(400, str(e))
        modules = await classify_modules(text, db)
        if not modules:
            continue
        for mod in modules:
            candidates = await extract_candidates(mod, text, db)
            results.append(
                ImportResult(module=mod, candidates=candidates, source=file.filename or "")
            )
    return ApiResponse(data=results)
