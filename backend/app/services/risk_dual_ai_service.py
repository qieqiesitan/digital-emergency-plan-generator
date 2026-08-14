"""AI 双等级参数建议服务（文本通道，不依赖图像识别）。

根据事件描述与既有管控措施文本，让 AI 分别给出固有风险
（不考虑管控措施）与现有风险（考虑管控措施）的参数与等级。
AI 失败/超时/未配置一律降级返回 available:false，不阻塞业务。
"""

from app.services.llm_client import llm_text_completion
from app.services.risk_ai_service import _parse_ai_json


async def suggest_dual_level(description: str, measures_text: str, ai_config) -> dict:
    """AI 建议事件的固有/现有双等级参数。

    Args:
        description: 事件描述（描述缺失时调用方回退事故类型）
        measures_text: 管控措施文本（measure_category:description 拼接）
        ai_config: AI 配置（未配置/异常时由调用方兜底降级）

    Returns:
        available=True 时含 inherent/current/note；否则
        {"available": False, "note": "AI 不可用，请手动评估或使用自动折算参考"}
    """
    prompt = (
        "你是安全风险评估专家。根据事故描述与管控措施，分别给出："
        "固有风险（不考虑管控措施）与现有风险（考虑管控措施）的参数与等级。\n\n"
        f"事故描述：{description}\n管控措施：{measures_text or '（无）'}\n\n"
        '输出 JSON：{"inherent": {"risk_level": "重大/较大/一般/低", "risk_score": "D=270"},'
        ' "current": {"risk_level": "...", "risk_score": "..."}, "note": "调参理由"}'
    )
    messages = [
        {"role": "system", "content": "你是安全风险评估专家，输出严格 JSON。"},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = await llm_text_completion(messages, ai_config, timeout=60)
        data = _parse_ai_json(raw)
        if "inherent" not in data or "current" not in data:
            raise ValueError("missing keys")
        return {"available": True, **data}
    except Exception:
        return {"available": False, "note": "AI 不可用，请手动评估或使用自动折算参考"}
