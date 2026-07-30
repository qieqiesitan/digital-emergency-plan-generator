import json, logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from app.models.enterprise import AIConfig
from app.config import settings
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import httpx
logger = logging.getLogger(__name__)

def _decrypt_api_key(hex_str: str) -> str:
    key = settings.ENCRYPTION_KEY.encode()[:32].ljust(32, b"\0")
    return unpad(AES.new(key, AES.MODE_ECB).decrypt(bytes.fromhex(hex_str)), 16).decode()

async def _call_llm(messages: list[dict], ai_config: AIConfig) -> str:
    api_key = _decrypt_api_key(ai_config.api_key_encrypted)
    base = ai_config.base_url or {"openai":"https://api.openai.com/v1","qwen":"https://dashscope.aliyuncs.com/compatible-mode/v1","deepseek":"https://api.deepseek.com/v1"}.get(ai_config.provider,"")
    payload = {"model":ai_config.model_name,"messages":messages,"temperature":ai_config.temperature,"max_tokens":ai_config.max_tokens,"top_p":ai_config.top_p,"stream":False}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{base}/chat/completions", json=payload, headers={"Authorization":f"Bearer {api_key}"})
            if resp.status_code != 200: raise HTTPException(500, f"AI 调用失败: HTTP {resp.status_code}")
            return resp.json()["choices"][0]["message"]["content"]
    except httpx.TimeoutException: raise HTTPException(504, "AI 响应超时（60s）")
    except HTTPException: raise
    except Exception as e: raise HTTPException(502, f"AI 服务连接失败: {str(e)}")

async def _get_ai_config(user_id: str, db: AsyncSession) -> AIConfig:
    result = await db.execute(select(AIConfig).where(AIConfig.user_id==user_id, AIConfig.is_active==True))
    config = result.scalar_one_or_none()
    if not config: raise HTTPException(400, "请先在系统设置中配置 AI 模型")
    return config

def _parse_ai_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"): raw = "\n".join(raw.split("\n")[1:] if raw.split("\n")[0].startswith("```") else raw.split("\n")); raw = raw[:-3].strip() if raw.endswith("```") else raw
    try: return json.loads(raw)
    except json.JSONDecodeError: raise HTTPException(500, f"AI 返回格式异常: {raw[:200]}")

async def suggest_objects(zone_name: str, zone_desc: str, enterprise_info: dict, ai_config: AIConfig, existing_names: list[str] = []) -> list[dict]:
    existing_str = "\n".join(f"- {n}" for n in existing_names) if existing_names else "无已有对象"
    prompt = f"""请根据以下信息列出该企业「{zone_name}」分区下的风险分析对象及单元。分区描述：{zone_desc}。企业信息：{json.dumps(enterprise_info, ensure_ascii=False, indent=2)}。已有对象（避免重复）：{existing_str}。输出 JSON：{{"objects":[{{"name":"...","category":"...","location":"...","description":"...","units":[{{"name":"...","unit_type":"设备|管道|阀门|仪表|电气|特种设备|其他"}}]}}]}}"""
    raw = await _call_llm([{"role":"system","content":"你是注册安全工程师，精通风险分级管控。"},{"role":"user","content":prompt}], ai_config)
    return _parse_ai_json(raw).get("objects",[])

async def suggest_events(unit_name: str, unit_type: str, object_name: str, zone_name: str, enterprise_info: dict, ai_config: AIConfig) -> list[dict]:
    prompt = f"""请分析单元「{unit_name}」(类型:{unit_type}，对象:{object_name}，分区:{zone_name})的风险事件。每事件含：accident_type/description/trigger_conditions/consequences/method_type(LEC/LS/DIRECT)/suggested_params/reasoning。企业信息：{json.dumps(enterprise_info, ensure_ascii=False, indent=2)}。输出 JSON：{{"events":[...]}}"""
    raw = await _call_llm([{"role":"system","content":"你是注册安全工程师，精通风险辨识和 GB 6441。"},{"role":"user","content":prompt}], ai_config)
    return _parse_ai_json(raw).get("events",[])

async def suggest_measures(accident_type: str, risk_level: str, unit_name: str, object_name: str, enterprise_info: dict, ai_config: AIConfig) -> list[dict]:
    prompt = f"""请为「{accident_type}」(等级:{risk_level}，单元:{unit_name}，对象:{object_name})建议管控措施。按 engineering/management/ppe/emergency 四类各 1-3 条，每条含 description 和 check_items(name+standard+frequency)。企业信息：{json.dumps(enterprise_info, ensure_ascii=False, indent=2)}。输出 JSON：{{"measures":[...]}}"""
    raw = await _call_llm([{"role":"system","content":"你是安全工程师。"},{"role":"user","content":prompt}], ai_config)
    return _parse_ai_json(raw).get("measures",[])

async def smart_guide(description: str, enterprise_info: dict, ai_config: AIConfig) -> dict:
    prompt = f"""用户描述：{description}\n企业信息：{json.dumps(enterprise_info, ensure_ascii=False, indent=2)}\n请生成完整风险分级管控层级(分区->对象->单元->事件->措施)，用 LS 矩阵评估(1-5)，每事件≥2 条措施，最多 5 分区 50 对象。输出 JSON：{{"zones":[...]}}"""
    raw = await _call_llm([{"role":"system","content":"你是注册安全工程师，输出严格 JSON。"},{"role":"user","content":prompt}], ai_config)
    return _parse_ai_json(raw)

async def analyze_floor_plan(enterprise_info: dict, ai_config: AIConfig) -> list[dict]:
    prompt = f"""根据企业信息分析功能区域，建议风险分区(name/description/location)。企业信息：{json.dumps(enterprise_info, ensure_ascii=False, indent=2)}。输出 JSON：{{"zones":[...]}}"""
    raw = await _call_llm([{"role":"system","content":"你是工厂布局分析专家。"},{"role":"user","content":prompt}], ai_config)
    return _parse_ai_json(raw).get("zones",[])

async def migrate_preview(risk_sources: list[dict], ai_config: AIConfig) -> list[dict]:
    prompt = f"""分析旧风险源数据，建议新体系映射(suggested_zone/suggested_object/suggested_accident_type/suggested_params)。旧数据：{json.dumps(risk_sources, ensure_ascii=False, indent=2)}。输出 JSON：{{"mappings":[...]}}"""
    raw = await _call_llm([{"role":"system","content":"你是数据迁移专家。"},{"role":"user","content":prompt}], ai_config)
    return _parse_ai_json(raw).get("mappings",[])
