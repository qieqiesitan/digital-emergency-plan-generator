"""提示词管理路由 — 本地DB CRUD + 可选YWT同步"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.prompt import PromptTemplate
from app.dependencies import get_current_user
from app.schemas.common import ApiResponse
from app.services.prompt_cache import invalidate_cache
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prompts", tags=["Prompt Templates"])


class PromptCreate(BaseModel):
    model_config = {"protected_namespaces": ()}
    template_code: str = Field(..., min_length=1, max_length=100)
    template_name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=64)
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    model_id: Optional[int] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 4096
    description: Optional[str] = None
    variables: Optional[dict] = None


class PromptUpdate(BaseModel):
    model_config = {"protected_namespaces": ()}
    template_name: Optional[str] = None
    category: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    model_id: Optional[int] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    description: Optional[str] = None
    variables: Optional[dict] = None
    status: Optional[str] = None


class PromptTestRequest(BaseModel):
    variables: dict = {}


def _to_response(p: PromptTemplate) -> dict:
    return {
        "id": p.id,
        "template_code": p.template_code,
        "template_name": p.template_name,
        "templateCode": p.template_code,
        "templateName": p.template_name,
        "category": p.category,
        "systemPrompt": p.system_prompt or "",
        "system_prompt": p.system_prompt or "",
        "userPromptTemplate": p.user_prompt_template or "",
        "user_prompt_template": p.user_prompt_template or "",
        "model_id": p.model_id,
        "temperature": p.temperature,
        "max_tokens": p.max_tokens,
        "description": p.description,
        "variables": p.variables,
        "status": p.status,
    }


@router.get("", response_model=ApiResponse[list])
async def list_prompts(
    category: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取提示词模板列表（本地DB）"""
    query = select(PromptTemplate)
    if category:
        query = query.where(PromptTemplate.category == category)
    rows = (await db.execute(query.order_by(PromptTemplate.category, PromptTemplate.template_code))).scalars().all()
    return ApiResponse(data=[_to_response(r) for r in rows])


@router.get("/{prompt_id}", response_model=ApiResponse[dict])
async def get_prompt(
    prompt_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单个提示词模板"""
    p = (await db.execute(select(PromptTemplate).where(PromptTemplate.id == prompt_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "提示词模板不存在")
    return ApiResponse(data=_to_response(p))


@router.post("", response_model=ApiResponse[dict])
async def create_prompt(
    data: PromptCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建提示词模板（本地DB）"""
    existing = (await db.execute(
        select(PromptTemplate).where(PromptTemplate.template_code == data.template_code)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(400, f"模板编码 {data.template_code} 已存在")

    p = PromptTemplate(**data.model_dump(exclude_none=True))
    db.add(p)
    await db.commit()
    await db.refresh(p)
    invalidate_cache()

    # 后台尝试同步到YWT
    _try_sync_to_ywt("create", _to_response(p))

    return ApiResponse(data=_to_response(p))


@router.put("/{prompt_id}", response_model=ApiResponse[dict])
async def update_prompt(
    prompt_id: int,
    data: PromptUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新提示词模板（本地DB）"""
    p = (await db.execute(select(PromptTemplate).where(PromptTemplate.id == prompt_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "提示词模板不存在")

    update_data = data.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(p, key, value)
    await db.commit()
    await db.refresh(p)
    invalidate_cache()

    _try_sync_to_ywt("update", _to_response(p))

    return ApiResponse(data=_to_response(p))


@router.post("/{prompt_id}/test", response_model=ApiResponse[dict])
async def test_prompt(
    prompt_id: int,
    data: PromptTestRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """测试提示词模板 — 尝试YWT，不可用时提示用户"""
    p = (await db.execute(select(PromptTemplate).where(PromptTemplate.id == prompt_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "提示词模板不存在")

    # 先尝试YWT
    try:
        from app import ywt_client
        result = await ywt_client.test_prompt(prompt_id, data.variables)
        if result.get("code") == 200:
            return ApiResponse(data=result.get("data"))
    except Exception as e:
        logger.warning(f"YWT测试不可用: {e}")

    # 本地渲染模板预览
    from app.services.prompt_cache import render_template
    rendered = render_template(p.user_prompt_template or "", data.variables)
    return ApiResponse(data={
        "result": f"【系统提示词】\n{p.system_prompt or '(无)'}\n\n【用户提示词(渲染后)】\n{rendered}\n\n---\n注：YWT中台不可用，以上为本地模板预览，非AI实际输出。",
        "tokens_used": None,
    })


def _try_sync_to_ywt(action: str, prompt_data: dict):
    """后台尝试同步到YWT，失败静默"""
    try:
        import asyncio
        async def _sync():
            try:
                from app import ywt_client
                body = {
                    "id": prompt_data.get("id"),
                    "templateCode": prompt_data.get("template_code"),
                    "templateName": prompt_data.get("template_name"),
                    "category": prompt_data.get("category"),
                    "systemPrompt": prompt_data.get("system_prompt"),
                    "userPromptTemplate": prompt_data.get("user_prompt_template"),
                }
                if action == "create":
                    await ywt_client.create_prompt(body)
                elif action == "update":
                    body["id"] = prompt_data["id"]
                    await ywt_client.update_prompt(body)
                logger.info(f"YWT同步成功: {action} {prompt_data.get('template_code')}")
            except Exception as e:
                logger.debug(f"YWT同步跳过（中台不可用）: {e}")
        asyncio.create_task(_sync())
    except Exception:
        pass
