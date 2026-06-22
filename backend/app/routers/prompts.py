from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from app.dependencies import get_current_user
from app.schemas.common import ApiResponse
from app import ywt_client
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prompts", tags=["Prompt Templates"])


class PromptCreate(BaseModel):
    model_config = {"protected_namespaces": ()}
    template_code: str = Field(..., min_length=1, max_length=64)
    template_name: str = Field(..., min_length=1, max_length=128)
    model_id: Optional[int] = None
    system_prompt: Optional[str] = None
    user_prompt_template: str
    variables: Optional[dict] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 4096
    category: Optional[str] = None
    description: Optional[str] = None


class PromptUpdate(BaseModel):
    model_config = {"protected_namespaces": ()}
    template_name: Optional[str] = None
    model_id: Optional[int] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    variables: Optional[dict] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    category: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class PromptTestRequest(BaseModel):
    variables: dict = {}


@router.get("", response_model=ApiResponse[list])
async def list_prompts(
    category: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
):
    """获取提示词模板列表"""
    items = await ywt_client.fetch_prompts(category=category)
    return ApiResponse(data=items)


@router.get("/{prompt_id}", response_model=ApiResponse[dict])
async def get_prompt(
    prompt_id: int,
    current_user=Depends(get_current_user),
):
    """获取单个提示词模板"""
    prompt = await ywt_client.fetch_prompt(prompt_id)
    if not prompt:
        raise HTTPException(404, "提示词模板不存在")
    return ApiResponse(data=prompt)


@router.post("", response_model=ApiResponse[dict])
async def create_prompt(
    data: PromptCreate,
    current_user=Depends(get_current_user),
):
    """创建提示词模板"""
    body = data.model_dump(exclude_none=True)
    # Map Python field names to Java field names
    body["templateCode"] = body.pop("template_code")
    body["templateName"] = body.pop("template_name")
    if "user_prompt_template" in body:
        body["userPromptTemplate"] = body.pop("user_prompt_template")
    if "system_prompt" in body:
        body["systemPrompt"] = body.pop("system_prompt")
    if "max_tokens" in body:
        body["maxTokens"] = body.pop("max_tokens")
    result = await ywt_client.create_prompt(body)
    if result.get("code") != 200:
        raise HTTPException(500, result.get("msg", "创建失败"))
    return ApiResponse(data=result.get("data"))


@router.put("/{prompt_id}", response_model=ApiResponse[dict])
async def update_prompt(
    prompt_id: int,
    data: PromptUpdate,
    current_user=Depends(get_current_user),
):
    """更新提示词模板"""
    body = data.model_dump(exclude_none=True)
    body["id"] = prompt_id
    if "template_name" in body:
        body["templateName"] = body.pop("template_name")
    if "user_prompt_template" in body:
        body["userPromptTemplate"] = body.pop("user_prompt_template")
    if "system_prompt" in body:
        body["systemPrompt"] = body.pop("system_prompt")
    if "max_tokens" in body:
        body["maxTokens"] = body.pop("max_tokens")
    result = await ywt_client.update_prompt(body)
    if result.get("code") != 200:
        raise HTTPException(500, result.get("msg", "更新失败"))
    return ApiResponse(data=result.get("data"))


@router.post("/{prompt_id}/test", response_model=ApiResponse[dict])
async def test_prompt(
    prompt_id: int,
    data: PromptTestRequest,
    current_user=Depends(get_current_user),
):
    """测试提示词模板（调用中台AI实际执行）"""
    result = await ywt_client.test_prompt(prompt_id, data.variables)
    if result.get("code") != 200:
        raise HTTPException(500, result.get("msg", "测试失败"))
    return ApiResponse(data=result.get("data"))
