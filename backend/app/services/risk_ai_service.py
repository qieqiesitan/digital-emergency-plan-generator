"""AI 辅助风险辨识服务。

为 risk_management 路由的 6 个 AI 端点提供共用逻辑层，
封装 LLM 调用、提示词构建和响应解析。
"""
import json
import logging
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
    """AES-256 ECB 解密 API Key — 与 generation.py 保持一致。"""
    key = settings.ENCRYPTION_KEY.encode()[:32].ljust(32, b"\0")
    cipher = AES.new(key, AES.MODE_ECB)
    return unpad(cipher.decrypt(bytes.fromhex(hex_str)), 16).decode()


async def _call_llm(messages: list[dict], ai_config: AIConfig) -> str:
    """非流式 LLM 调用，60s 超时。

    Args:
        messages: OpenAI 格式的消息列表 [{"role":"system","content":"..."}, ...]
        ai_config: 用户的 AI 配置（含加密 API Key）

    Returns:
        AI 返回的文本内容

    Raises:
        HTTPException(500/502/504): 调用失败、连接失败或超时
    """
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

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{base}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code != 200:
                raise HTTPException(500, f"AI 调用失败: HTTP {resp.status_code}")
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except httpx.TimeoutException:
        raise HTTPException(504, "AI 响应超时（60s），请稍后重试")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"AI 服务连接失败: {str(e)}")


async def _get_ai_config(user_id: str, db: AsyncSession) -> AIConfig:
    """获取用户 AI 配置，未配置则抛出 400。

    Args:
        user_id: 用户 UUID
        db: 数据库会话

    Returns:
        AIConfig ORM 实例

    Raises:
        HTTPException(400): 用户未配置 AI 模型
    """
    result = await db.execute(
        select(AIConfig).where(
            AIConfig.user_id == user_id,
            AIConfig.is_active == True,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(400, "请先在系统设置中配置 AI 模型")
    return config


def _parse_ai_json(raw: str) -> dict:
    """解析 AI 返回的 JSON 字符串，处理 markdown 代码块包裹。

    Args:
        raw: AI 返回的原始文本

    Returns:
        解析后的 dict

    Raises:
        HTTPException(500): JSON 解析失败
    """
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:]) if lines[0].startswith("```") else raw
        if raw.endswith("```"):
            raw = raw[:-3].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"AI JSON parse failed: {raw[:200]}")
        raise HTTPException(500, f"AI 返回格式异常，无法解析 JSON: {raw[:200]}")


async def suggest_objects(
    zone_name: str,
    zone_desc: str,
    enterprise_info: dict,
    ai_config: AIConfig,
    existing_names: list[str] = [],
) -> list[dict]:
    """AI 建议分区下的风险分析对象及单元。

    Args:
        zone_name: 分区名称
        zone_desc: 分区描述
        enterprise_info: 企业基本信息（name/industry/hazardous_chemicals 等）
        ai_config: AI 配置
        existing_names: 已有对象名称列表（用于去重）

    Returns:
        objects 列表，每项含 name/category/location/description/units
    """
    existing_str = "\n".join(f"- {n}" for n in existing_names) if existing_names else "（无已有对象）"

    prompt = (
        f"请根据以下信息，列出该企业「{zone_name}」分区下可能存在的主要风险分析对象。\n\n"
        f"分区描述：{zone_desc}\n\n"
        f"企业信息：\n{json.dumps(enterprise_info, ensure_ascii=False, indent=2)}\n\n"
        f"已有对象（请避免重复）：\n{existing_str}\n\n"
        f"为每个对象列出建议的分析单元（设备、管道、阀门等部件），"
        f"并给出对象类别、位置和风险描述。\n\n"
        f"输出 JSON 格式：\n"
        f'{{"objects": [{{"name": "...", "category": "...", "location": "...", '
        f'"description": "...", "units": [{{"name": "...", '
        f'"unit_type": "设备|管道|阀门|仪表|电气|特种设备|其他"}}]}}]}}'
    )

    messages = [
        {
            "role": "system",
            "content": "你是持有国家注册安全工程师资格的应急预案专家，精通 GB/T 13861 和 GB 6441。",
        },
        {"role": "user", "content": prompt},
    ]

    raw = await _call_llm(messages, ai_config)
    data = _parse_ai_json(raw)
    return data.get("objects", [])


async def suggest_events(
    unit_name: str,
    unit_type: str,
    object_name: str,
    zone_name: str,
    enterprise_info: dict,
    ai_config: AIConfig,
) -> list[dict]:
    """AI 建议单元可能的风险事件及评估参数。

    Args:
        unit_name: 单元名称
        unit_type: 单元类型（设备/管道/阀门/...）
        object_name: 所属对象名称
        zone_name: 所属分区名称
        enterprise_info: 企业基本信息
        ai_config: AI 配置

    Returns:
        events 列表，每项含 accident_type/description/trigger_conditions/
        consequences/method_type/suggested_params/reasoning
    """
    prompt = (
        f"你是一位持有国家注册安全工程师资格的风险评估专家。\n\n"
        f"请分析以下风险分析单元可能发生的事故类型，给出 1-3 个最可能的风险事件。\n\n"
        f"每个事件包含：\n"
        f"- accident_type: 事故类型（按 GB 6441-1986）\n"
        f"- description: 事故描述\n"
        f"- trigger_conditions: 触发条件\n"
        f"- consequences: 可能后果\n"
        f"- method_type: 建议评估方法（LS/LEC/DIRECT）\n"
        f"- suggested_params: 建议评估参数（如 {{\"l\":2,\"s\":4}}），含 reasoning 说明理由\n"
        f"- reasoning: 参数选择理由\n\n"
        f"单元信息：\n"
        f"- 单元名称：{unit_name}\n"
        f"- 单元类型：{unit_type}\n"
        f"- 所属对象：{object_name}\n"
        f"- 所属分区：{zone_name}\n\n"
        f"企业信息：\n{json.dumps(enterprise_info, ensure_ascii=False, indent=2)}\n\n"
        f'输出 JSON：{{"events": [{{"accident_type": "...", ...}}]}}'
    )

    messages = [
        {
            "role": "system",
            "content": "你是持有国家注册安全工程师资格的风险评估专家，精通 GB/T 13861 和 GB 6441。",
        },
        {"role": "user", "content": prompt},
    ]

    raw = await _call_llm(messages, ai_config)
    data = _parse_ai_json(raw)
    return data.get("events", [])


async def suggest_measures(
    accident_type: str,
    risk_level: str,
    unit_name: str,
    object_name: str,
    enterprise_info: dict,
    ai_config: AIConfig,
) -> list[dict]:
    """AI 建议风险事件的管控措施及检查项目。

    Args:
        accident_type: 事故类型（如"储罐泄漏"）
        risk_level: 风险等级（重大/较大/一般/低）
        unit_name: 所属单元名称
        object_name: 所属对象名称
        enterprise_info: 企业基本信息
        ai_config: AI 配置

    Returns:
        measures 列表，每项含 measure_category/measure_type/description/check_items
    """
    prompt = (
        f"请为以下风险事件建议管控措施。\n"
        f"按四类措施（engineering 工程技术、management 管理措施、ppe 个体防护、"
        f"emergency 应急处置）各建议 1-3 条，每条含措施描述和 1-2 个检查项目"
        f"（name + standard + frequency）。\n\n"
        f"事件信息：\n"
        f"- 事故类型：{accident_type}\n"
        f"- 风险等级：{risk_level}\n"
        f"- 所属单元：{unit_name}\n"
        f"- 所属对象：{object_name}\n\n"
        f"企业信息：\n{json.dumps(enterprise_info, ensure_ascii=False, indent=2)}\n\n"
        f'输出 JSON：{{"measures": [{{"measure_category": "engineering|management|ppe|emergency", '
        f'"measure_type": "...", "description": "...", '
        f'"check_items": [{{"name": "...", "standard": "...", "frequency": "..."}}]}}]}}'
    )

    messages = [
        {
            "role": "system",
            "content": "你是持有国家注册安全工程师资格的应急预案专家。",
        },
        {"role": "user", "content": prompt},
    ]

    raw = await _call_llm(messages, ai_config)
    data = _parse_ai_json(raw)
    return data.get("measures", [])


async def smart_guide(
    description: str,
    enterprise_info: dict,
    ai_config: AIConfig,
) -> dict:
    """一键智能导引：自然语言描述 → 完整层级结构。

    Args:
        description: 用户自然语言描述（如"储罐区有3个5000m³原油储罐..."）
        enterprise_info: 企业基本信息
        ai_config: AI 配置

    Returns:
        dict 含 zones 和 summary 字段，zones 为完整层级结构
    """
    prompt = (
        f"用户描述了以下企业区域，请分析并生成完整的风险分级管控层级结构"
        f"（分区 → 对象 → 单元 → 事件 → 措施）。\n\n"
        f"用户描述：\n{description}\n\n"
        f"企业信息：\n{json.dumps(enterprise_info, ensure_ascii=False, indent=2)}\n\n"
        f"要求：\n"
        f"1. 解析描述中的实体关系，生成到措施层级\n"
        f"2. 每个事件使用 LS 矩阵法评估（L: 1-5, S: 1-5），含 risk_level 和 risk_score\n"
        f"3. 每事件至少 2 条管控措施\n"
        f"4. 最多生成 5 个分区、50 个对象\n\n"
        f'输出 JSON 格式（完整层级）：\n'
        f'{{"zones": [{{"name": "...", "description": "...", '
        f'"objects": [{{"name": "...", "category": "...", '
        f'"is_risk_point": false, "units": [{{"name": "...", '
        f'"unit_type": "...", "events": [{{"accident_type": "...", '
        f'"risk_level": "重大|较大|一般|低", "risk_score": "R=XX", '
        f'"method_type": "LS", "method_params": {{"l": X, "s": X}}, '
        f'"measures": [...]}}]}}]}}]}}]}}\n'
        f"只输出 JSON，不要任何解释。"
    )

    messages = [
        {
            "role": "system",
            "content": "你是注册安全工程师，精通风险分级管控和 GB/T 29639 标准。输出严格 JSON。",
        },
        {"role": "user", "content": prompt},
    ]

    raw = await _call_llm(messages, ai_config)
    data = _parse_ai_json(raw)
    return data


async def analyze_floor_plan(
    enterprise_info: dict,
    ai_config: AIConfig,
) -> list[dict]:
    """AI 分析平面图建议分区。

    Args:
        enterprise_info: 企业基本信息
        ai_config: AI 配置

    Returns:
        zones 列表，每项含 name/description/location
    """
    prompt = (
        f"请根据以下企业信息，分析该企业的功能区域分布，"
        f"建议风险分区（name / description / approximate_location）。\n\n"
        f"企业信息：\n{json.dumps(enterprise_info, ensure_ascii=False, indent=2)}\n\n"
        f'输出 JSON：{{"zones": [{{"name": "...", "description": "...", "location": "厂区西北角..."}}]}}'
    )

    messages = [
        {"role": "system", "content": "你是工厂布局分析专家。"},
        {"role": "user", "content": prompt},
    ]

    raw = await _call_llm(messages, ai_config)
    data = _parse_ai_json(raw)
    return data.get("zones", [])


async def migrate_preview(
    risk_sources: list[dict],
    ai_config: AIConfig,
) -> list[dict]:
    """AI 分析旧 risk_sources 数据，建议新五层体系映射。

    Args:
        risk_sources: 旧版风险源数据列表
        ai_config: AI 配置

    Returns:
        mappings 列表，每项含 source_id/suggested_zone/suggested_object/
        suggested_accident_type/suggested_params
    """
    prompt = (
        f"请分析以下旧版风险源数据，为每条建议在新五层体系中的映射位置。\n\n"
        f"旧数据：\n{json.dumps(risk_sources, ensure_ascii=False, indent=2)}\n\n"
        f'输出 JSON：{{"mappings": [{{"source_id": "...", "suggested_zone": "...", '
        f'"suggested_object": "...", "suggested_accident_type": "...", '
        f'"suggested_params": {{"l": X, "s": X}}}}]}}'
    )

    messages = [
        {"role": "system", "content": "你是安全数据迁移专家。"},
        {"role": "user", "content": prompt},
    ]

    raw = await _call_llm(messages, ai_config)
    data = _parse_ai_json(raw)
    return data.get("mappings", [])
