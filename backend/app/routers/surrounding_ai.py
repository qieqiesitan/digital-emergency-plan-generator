import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import httpx

from app.database import get_db
from app.models.enterprise import Enterprise, AIConfig
from app.schemas.enterprise import SurroundingInfo, NearbyUnit, SensitiveTarget
from app.schemas.common import ApiResponse
from app.dependencies import get_current_user
from app.config import settings
from app.services.prompt_cache import ensure_loaded, render_template

router = APIRouter(prefix="/enterprises", tags=["Surrounding AI"])

# TODO: 方向列表可从 sys_config 加载，当前保持硬编码作为 fallback
DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def _decrypt_api_key(hex_str: str) -> str:
    key = settings.ENCRYPTION_KEY.encode()[:32].ljust(32, b"\0")
    cipher = AES.new(key, AES.MODE_ECB)
    return unpad(cipher.decrypt(bytes.fromhex(hex_str)), 16).decode()


async def _call_llm_nonstream(messages: list[dict], ai_config: AIConfig) -> str:
    try:
        api_key = _decrypt_api_key(ai_config.api_key_encrypted)
    except Exception:
        raise HTTPException(500, "AI 配置密钥解密失败")
    base = ai_config.base_url or {
        "openai": "https://api.openai.com/v1",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "deepseek": "https://api.deepseek.com/v1",
    }.get(ai_config.provider, "")
    payload = {
        "model": ai_config.model_name,
        "messages": messages,
        "temperature": ai_config.temperature,
        "max_tokens": ai_config.max_tokens,
        "top_p": ai_config.top_p,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{base}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        if resp.status_code != 200:
            if resp.status_code == 401:
                raise HTTPException(500, "AI API Key 无效或已过期，请在系统设置中重新配置 AI 模型")
            raise HTTPException(500, f"AI 调用失败: HTTP {resp.status_code}")
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _get_enterprise_data(enterprise_id: str, user_id: str, db: AsyncSession) -> dict:
    result = await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == user_id)
    )
    ent = result.scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    return {
        "name": ent.name,
        "industry": ent.industry or "",
        "business_scope": ent.business_scope or "",
        "building_overview": ent.building_overview or "",
        "employee_count": ent.employee_count,
        "address": ent.address or "",
        "hazardous_chemicals": ent.hazardous_chemicals or "",
        "main_products": ent.main_products or "",
        "surrounding_info": ent.surrounding_info or {},
    }


def _build_existing_summary(surrounding: dict) -> str:
    parts = []

    nearby = surrounding.get("nearby_units", [])
    if nearby:
        parts.append("已录入的周边单位：")
        for u in nearby:
            parts.append(f"- {u.get('name','')}（方位：{u.get('direction','')}，距离：{u.get('distance_m','')}m，风险：{u.get('main_risk','')}）")

    targets = surrounding.get("sensitive_targets", [])
    if targets:
        parts.append("已录入的敏感目标：")
        for t in targets:
            parts.append(f"- {t.get('name','')}（方位：{t.get('direction','')}，距离：{t.get('distance_m','')}m，类型：{t.get('type','')}）")

    traffic = surrounding.get("traffic_info", "")
    if traffic:
        parts.append(f"已录入的交通状况：{traffic}")

    return "\n".join(parts) if parts else "当前无周边环境数据"


# ---------- AI question generation ----------

class AIQuestionItem(BaseModel):
    id: str
    question: str


class AIQuestionsResponse(BaseModel):
    questions: list[AIQuestionItem]


@router.post("/{enterprise_id}/surrounding/ai/questions", response_model=ApiResponse[AIQuestionsResponse])
async def get_surrounding_ai_questions(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    await ensure_loaded()
    await ensure_loaded()
    ent_data = await _get_enterprise_data(enterprise_id, current_user.id, db)
    ai_config = (await db.execute(
        select(AIConfig).where(AIConfig.user_id == current_user.id)
    )).scalar_one_or_none()
    if not ai_config:
        raise HTTPException(400, "请先在系统设置中配置 AI 模型")

    existing_summary = _build_existing_summary(ent_data["surrounding_info"])

    system_prompt = (
        "你是一位持有国家注册安全工程师资格的专业应急预案编制专家，熟悉 GB/T 29639-2020 标准。"
        "你的任务是一次性提出全面覆盖周边环境三大板块的调查问题，"
        "严格避免对已录入的周边单位和敏感目标重复提问。"
    )

    user_prompt = f"""请根据以下企业信息，一次性提出 6~10 个全面调查问题，覆盖该企业周边环境的三大板块：
1. 周边单位（相邻工厂、企业、设施的名称、方位、距离、主要风险）
2. 敏感目标（学校、医院、住宅区、水源地、文保单位等的名称、方位、距离、类型）
3. 交通状况（主要进出道路、消防车通行条件、最近高速/国道入口等）

企业信息：
- 名称：{ent_data["name"]}
- 行业：{ent_data["industry"]}
- 经营范围：{ent_data["business_scope"]}
- 地址：{ent_data["address"]}
- 建筑/厂区概况：{ent_data["building_overview"]}
- 员工人数：{ent_data["employee_count"] or "未知"}
- 危险化学品：{ent_data["hazardous_chemicals"]}
- 主要产品：{ent_data["main_products"]}

{existing_summary}

方位参考：{"、".join(DIRECTIONS)}

请以 JSON 格式输出，格式严格为：
{{"questions": [{{"id": "q1", "question": "问题文本"}}]}}
每个板块至少 2 个问题。只输出 JSON，不要任何解释。"""

    try:
        raw = await _call_llm_nonstream(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            ai_config,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:]) if lines[0].startswith("```") else raw
            if raw.endswith("```"):
                raw = raw[:-3].strip()
        data = json.loads(raw)
        questions = [AIQuestionItem(**q) for q in data.get("questions", [])]
        return ApiResponse(data=AIQuestionsResponse(questions=questions))
    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(500, f"AI 返回格式异常，无法解析 JSON: {raw[:200]}")
    except Exception as e:
        raise HTTPException(500, f"AI 调用失败: {str(e)}")


# ---------- AI generate surrounding info ----------

class AIAnswerInput(BaseModel):
    question_id: str
    question: str
    answer: str


class AIGenerateRequest(BaseModel):
    answers: list[AIAnswerInput]


class AIGenerateSurroundingResponse(BaseModel):
    surrounding: SurroundingInfo


@router.post("/{enterprise_id}/surrounding/ai/generate", response_model=ApiResponse[AIGenerateSurroundingResponse])
async def generate_surrounding_ai(
    enterprise_id: str,
    body: AIGenerateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    await ensure_loaded()
    ent_data = await _get_enterprise_data(enterprise_id, current_user.id, db)
    ai_config = (await db.execute(
        select(AIConfig).where(AIConfig.user_id == current_user.id)
    )).scalar_one_or_none()
    if not ai_config:
        raise HTTPException(400, "请先在系统设置中配置 AI 模型")

    existing_summary = _build_existing_summary(ent_data["surrounding_info"])

    qa_text = "\n".join(f"Q: {a.question}\nA: {a.answer}" for a in body.answers)

    system_prompt = (
        "你是一位持有国家注册安全工程师资格的专业应急预案编制专家，熟悉 GB/T 29639-2020 标准。"
        "严禁生成与已录入周边单位/敏感目标名称重复的数据。"
    )

    user_prompt = f"""请根据以下企业信息和用户回答，生成该企业周边环境信息。

企业信息：
- 名称：{ent_data["name"]}
- 行业：{ent_data["industry"]}
- 经营范围：{ent_data["business_scope"]}
- 地址：{ent_data["address"]}
- 建筑/厂区概况：{ent_data["building_overview"]}
- 员工人数：{ent_data["employee_count"] or "未知"}
- 危险化学品：{ent_data["hazardous_chemicals"]}
- 主要产品：{ent_data["main_products"]}

{existing_summary}

用户对周边环境调查的回答：
{qa_text}

请以 JSON 输出，格式严格为：
{{
  "nearby_units": [
    {{"name": "工厂名", "direction": "N", "distance_m": 500, "main_risk": "火灾爆炸"}}
  ],
  "sensitive_targets": [
    {{"name": "XX小学", "direction": "SE", "distance_m": 300, "type": "学校"}}
  ],
  "traffic_info": "主要进出道路为XX路，双向四车道，消防车可通行。距XX高速入口约3公里。"
}}

字段说明：
- direction: 必须从 {DIRECTIONS} 中选择
- distance_m: 整数，单位米
- main_risk: 该单位的主要危险性（火灾/爆炸/中毒/化学泄漏等）
- type: 敏感目标类型（学校/医院/住宅区/水源地/文保单位/商业区等）
- traffic_info: 交通状况的完整文字描述

只输出 JSON，不要任何解释。"""

    try:
        raw = await _call_llm_nonstream(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            ai_config,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:]) if lines[0].startswith("```") else raw
            if raw.endswith("```"):
                raw = raw[:-3].strip()
        data = json.loads(raw)

        nearby_units = [NearbyUnit(**u) for u in data.get("nearby_units", [])]
        sensitive_targets = [SensitiveTarget(**t) for t in data.get("sensitive_targets", [])]
        traffic_info = data.get("traffic_info", "")

        surrounding = SurroundingInfo(
            nearby_units=nearby_units,
            sensitive_targets=sensitive_targets,
            traffic_info=traffic_info,
        )
        return ApiResponse(data=AIGenerateSurroundingResponse(surrounding=surrounding))
    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(500, f"AI 返回格式异常，无法解析 JSON: {raw[:200]}")
    except Exception as e:
        raise HTTPException(500, f"AI 调用失败: {str(e)}")

