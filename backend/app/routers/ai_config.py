from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.models.enterprise import AIConfig
from app.schemas.ai_config import AIConfigCreate, AIConfigUpdate, AIConfigResponse, AITestRequest, AITestResult
from app.schemas.common import ApiResponse
from app.dependencies import get_current_user
from app.config import settings
import httpx

router = APIRouter(prefix="/settings", tags=["AI Config"])

def _encrypt(plain: str) -> str:
    key = settings.ENCRYPTION_KEY.encode()[:32].ljust(32, b"\0")
    cipher = AES.new(key, AES.MODE_ECB)
    return cipher.encrypt(pad(plain.encode(), 16)).hex()

def _decrypt(ciphertext_hex: str) -> str:
    key = settings.ENCRYPTION_KEY.encode()[:32].ljust(32, b"\0")
    cipher = AES.new(key, AES.MODE_ECB)
    return unpad(cipher.decrypt(bytes.fromhex(ciphertext_hex)), 16).decode()

@router.get("/ai-config", response_model=ApiResponse[AIConfigResponse])
async def get_ai_config(current_user=Depends(get_current_user), db=Depends(get_db)):
    r = (await db.execute(select(AIConfig).where(AIConfig.user_id == current_user.id))).scalar_one_or_none()
    if not r: raise HTTPException(404, "尚未配置 AI")
    return ApiResponse(data=AIConfigResponse.model_validate(r))

@router.put("/ai-config", response_model=ApiResponse[AIConfigResponse])
async def update_ai_config(data: AIConfigCreate, current_user=Depends(get_current_user), db=Depends(get_db)):
    r = (await db.execute(select(AIConfig).where(AIConfig.user_id == current_user.id))).scalar_one_or_none()
    encrypted = _encrypt(data.api_key)
    if r:
        r.provider = data.provider; r.api_key_encrypted = encrypted; r.model_name = data.model_name
        r.base_url = data.base_url; r.temperature = data.temperature; r.max_tokens = data.max_tokens; r.top_p = data.top_p
    else:
        r = AIConfig(user_id=current_user.id, provider=data.provider, api_key_encrypted=encrypted, model_name=data.model_name, base_url=data.base_url, temperature=data.temperature, max_tokens=data.max_tokens, top_p=data.top_p)
        db.add(r)
    await db.commit(); await db.refresh(r)
    return ApiResponse(data=AIConfigResponse.model_validate(r))

@router.delete("/ai-config")
async def delete_ai_config(current_user=Depends(get_current_user), db=Depends(get_db)):
    r = (await db.execute(select(AIConfig).where(AIConfig.user_id == current_user.id))).scalar_one_or_none()
    if r: await db.delete(r); await db.commit()
    return {"code": 0, "message": "已删除"}

@router.post("/ai-config/test", response_model=ApiResponse[AITestResult])
async def test_ai_connection(data: AITestRequest):
    try:
        base = data.base_url or {
            "openai": "https://api.openai.com/v1",
            "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "deepseek": "https://api.deepseek.com/v1",
        }.get(data.provider, data.base_url or "")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"{base}/chat/completions", json={"model": data.model_name, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5}, headers={"Authorization": f"Bearer {data.api_key}"})
            if resp.status_code == 200:
                return ApiResponse(data=AITestResult(ok=True, detail="连接成功"))
            return ApiResponse(data=AITestResult(ok=False, detail=f"HTTP {resp.status_code}: {resp.text[:200]}"))
    except Exception as e:
        return ApiResponse(data=AITestResult(ok=False, detail=str(e)))
