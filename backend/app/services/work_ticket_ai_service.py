"""作业票 AI 预填：风险辨识结果 / JSA 草稿。

与 hazard_ai_service 同惯例：未配置、能力停用、超时、返回非 JSON 一律降级为
{"available": False, ...}，不抛异常、不阻塞开票流程。

额外安全防线（本模块专有）：AI 输出中出现「可以作业」「符合作业条件」等批准性
表述时，整份结果作废 —— AI 不承担批准职责，票面上的结论只能由人给出。
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from app.services.ai_json import parse_ai_json
from app.services.llm_client import CapabilityDisabledError, llm_text_completion

# 复用能力注册表里既有的 work_ticket_jsa：风险辨识结果与 JSA 同属"作业危害分析"，
# 共用同一个管理员开关（真库 ai_capabilities 已注册该 code，无需新增种子）。
CAPABILITY = "work_ticket_jsa"
MODULE = "work_ticket"
AI_TIMEOUT_SECONDS = 60

_FORBIDDEN_APPROVAL_PHRASES = (
    "可以作业",
    "符合作业条件",
    "允许作业",
    "同意作业",
    "可以动火",
    "批准作业",
)

SYSTEM_PROMPT = (
    "你是危险化学品企业的特殊作业安全专家，熟悉 GB 30871-2022。"
    "只输出 JSON，不输出解释性前后缀。\n"
    "硬约束：\n"
    "1. 不得编造企业不存在的设备、介质、管线；不确定的事实写「待现场核实」\n"
    "2. 风险辨识结果 3~6 条，每条为一个具体危害及其控制措施\n"
    "3. 禁止输出「符合作业条件」「可以作业」之类批准性结论\n"
    "4. 输入中没有的信息不得推断（例如未给作业高度就不要提坠落风险）\n"
)

_OUTPUT_SCHEMA = (
    '{"risk_identification": {"text": "...", "basis": ["..."]},'
    ' "jsa": {"text": "...", "hazards": [{"hazard": "...", "control": "..."}]}}'
)


def _fallback(note: str) -> dict[str, Any]:
    return {
        "available": False,
        "risk_identification": None,
        "jsa": None,
        "measures_suggestions": [],
        "note": note,
    }


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_ai_result(raw: str) -> dict[str, Any]:
    """把模型输出归一化成前端契约；任何异常都降级为 available=False。"""
    try:
        data = parse_ai_json(raw)
    except Exception:  # parse_ai_json 抛 HTTPException，这里统一降级
        return _fallback("AI 返回格式异常，已跳过预填")
    if not isinstance(data, dict):
        return _fallback("AI 返回结构异常，已跳过预填")

    risk_raw = data.get("risk_identification") or {}
    risk_text = _clean_text(
        risk_raw.get("text") if isinstance(risk_raw, dict) else risk_raw
    )
    if not risk_text:
        return _fallback("AI 未返回有效的风险辨识内容")
    if any(phrase in risk_text for phrase in _FORBIDDEN_APPROVAL_PHRASES):
        return _fallback("AI 返回了批准性表述，已拒绝采用（批准只能由人给出）")

    basis_raw = risk_raw.get("basis") if isinstance(risk_raw, dict) else None
    basis = [str(item).strip() for item in (basis_raw or []) if str(item).strip()]

    jsa_raw = data.get("jsa") or {}
    jsa_text = _clean_text(jsa_raw.get("text") if isinstance(jsa_raw, dict) else jsa_raw)
    hazards: list[dict[str, str]] = []
    if isinstance(jsa_raw, dict):
        for item in jsa_raw.get("hazards") or []:
            if not isinstance(item, dict):
                continue
            hazard = _clean_text(item.get("hazard"))
            if hazard:
                hazards.append({"hazard": hazard, "control": _clean_text(item.get("control"))})

    return {
        "available": True,
        "risk_identification": {"text": risk_text, "basis": basis},
        "jsa": {"text": jsa_text, "hazards": hazards} if jsa_text else None,
        "measures_suggestions": [],
        "note": "AI 生成内容仅供参考，须由作业负责人确认",
    }


def build_messages(
    *,
    ticket_type: str,
    level: Optional[str],
    location_text: Optional[str],
    work_content: Optional[str],
    chemicals: Sequence[str] = (),
    last_risk_text: Optional[str] = None,
) -> list[dict]:
    user_prompt = (
        f"作业类型：{ticket_type}（{level or '不分级'}）\n"
        f"作业地点：{location_text or '（未提供）'}\n"
        f"作业内容：{work_content or '（未提供）'}\n"
        f"涉及危化品：{'、'.join(chemicals) if chemicals else '（未提供）'}\n"
        f"上张同类票的风险辨识（仅作风格参照，不得照抄）：{last_risk_text or '（无）'}\n\n"
        f"请输出 JSON，结构为：{_OUTPUT_SCHEMA}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


async def prefill(
    *,
    ticket_type: str,
    level: Optional[str],
    location_text: Optional[str],
    work_content: Optional[str],
    chemicals: Sequence[str] = (),
    last_risk_text: Optional[str] = None,
    ai_config: Optional[object],
) -> dict[str, Any]:
    """调用 AI 生成预填内容；任何失败都降级，不抛异常。"""
    if ai_config is None:
        return _fallback("企业未配置 AI，已跳过 AI 预填")
    messages = build_messages(
        ticket_type=ticket_type,
        level=level,
        location_text=location_text,
        work_content=work_content,
        chemicals=chemicals,
        last_risk_text=last_risk_text,
    )
    try:
        raw = await llm_text_completion(
            messages,
            ai_config,
            timeout=AI_TIMEOUT_SECONDS,
            module=MODULE,
            capability=CAPABILITY,
        )
    except CapabilityDisabledError:
        return _fallback("AI 能力「作业票智能预填」已被管理员停用")
    except Exception as exc:  # 超时/网络/5xx 一律降级
        return _fallback(f"AI 预填失败，已跳过（{type(exc).__name__}）")
    return normalize_ai_result(raw)
