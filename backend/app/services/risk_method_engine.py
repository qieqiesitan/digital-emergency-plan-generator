"""风险评估多方法计算引擎。支持 LS 矩阵、LEC 评价法、煤矿 LS 矩阵、直接判定法。"""

from typing import Optional
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.risk_management import RiskAssessmentMethod


RISK_LEVEL_ORDER = ["低", "一般", "较大", "重大"]


def validate_dual_level(current_level: str | None, inherent_level: str | None) -> None:
    """现有风险等级不应高于固有风险等级，否则抛 ValueError。"""
    if (current_level and inherent_level
            and current_level in RISK_LEVEL_ORDER and inherent_level in RISK_LEVEL_ORDER
            and RISK_LEVEL_ORDER.index(current_level) > RISK_LEVEL_ORDER.index(inherent_level)):
        raise ValueError("现有风险等级不应高于固有风险等级")


def level_from_score(method_type: str, score: float, thresholds: list[dict]) -> str:
    """按阈值区间将分值映射为风险等级，未命中时兜底为“低”。"""
    for t in thresholds or []:
        if t["min"] <= score <= t["max"]:
            return t["level"]
    return "低"


@dataclass
class RiskResult:
    """风险评估计算结果。

    Attributes:
        risk_level: 风险等级标签，如"重大""较大""一般""低"。
        risk_score: 风险分值表达式，如 "R=12" 或 "D=240"。
        action:   建议处置措施文本。
        deadline: 整改期限描述。
    """
    risk_level: str
    risk_score: str
    action: str
    deadline: str


def compute_risk(
    method_type: str,
    params: dict,
    config: dict | None = None,
) -> RiskResult:
    """根据评估方法类型和参数计算风险等级。

    Args:
        method_type: 评估方法 — "LS" / "LEC" / "COAL_LS" / "DIRECT"。
        params: 方法所需参数，常见键有 l, s, e, c, risk_level。
        config: 方法配置字典，含 risk_thresholds 阈值列表。

    Returns:
        RiskResult，包含等级、分值、处置措施和整改期限。
    """
    # 直接判定法：直接返回 params 中的风险等级
    if method_type == "DIRECT":
        level = params.get("risk_level", "一般")
        return RiskResult(
            risk_level=level,
            risk_score="-",
            action=level,
            deadline="按需",
        )

    thresholds = (config or {}).get("risk_thresholds", [])

    # 计算风险分值 R 或 D，根据不同方法
    if method_type == "LS":
        l_val = float(params.get("l", 3))
        s_val = float(params.get("s", 3))
        r = int(l_val * s_val)
        score_str = f"R={r}"
    elif method_type == "LEC":
        l_val = float(params.get("l", 1))
        e_val = float(params.get("e", 1))
        c_val = float(params.get("c", 1))
        r = int(l_val * e_val * c_val)
        score_str = f"D={r}"
    elif method_type == "COAL_LS":
        l_val = float(params.get("l", 3))
        s_val = float(params.get("s", 3))
        r = int(l_val * s_val)
        score_str = f"R={r}"
        # 煤矿 LS 默认阈值（当配置未提供时使用）
        if not thresholds:
            thresholds = [
                {"min": 20, "max": 25, "level": "重大",
                 "action": "立即停产整改", "deadline": "立即"},
                {"min": 15, "max": 19, "level": "较大",
                 "action": "限期停产整改", "deadline": "1个月"},
                {"min": 10, "max": 14, "level": "一般",
                 "action": "限期整改", "deadline": "3个月"},
                {"min": 1,  "max": 9,  "level": "低",
                 "action": "加强日常管理", "deadline": "持续"},
            ]
    else:
        return RiskResult(
            risk_level="一般",
            risk_score="-",
            action="未知方法",
            deadline="N/A",
        )

    # 复用 level_from_score 得到风险等级，再按阈值项取 action/deadline
    level = level_from_score(method_type, r, thresholds)
    matched = next(
        (t for t in thresholds or [] if t["min"] <= r <= t["max"]), None
    )
    if matched:
        return RiskResult(
            risk_level=level,
            risk_score=score_str,
            action=matched.get("action", ""),
            deadline=matched.get("deadline", ""),
        )

    # 未命中任何阈值区间时的兜底：等级“低” + 日常管理
    return RiskResult(
        risk_level=level,
        risk_score=score_str,
        action="日常管理",
        deadline="持续",
    )


async def get_active_method_config(
    db: AsyncSession,
    enterprise_id: str,
    method_type: str = "LS",
) -> dict | None:
    """获取启用的评估方法配置。

    先查企业级配置，若无则回退到系统级（enterprise_id 为 NULL）配置。

    Args:
        db: 异步数据库会话。
        enterprise_id: 企业 ID。
        method_type: 评估方法类型，默认 "LS"。

    Returns:
        方法配置字典，未找到时返回 None。
    """
    # 先查企业级
    result = await db.execute(
        select(RiskAssessmentMethod).where(
            RiskAssessmentMethod.enterprise_id == enterprise_id,
            RiskAssessmentMethod.method_type == method_type,
            RiskAssessmentMethod.is_active == True,
        )
    )
    m = result.scalar_one_or_none()
    if m:
        return m.config

    # 回退到系统级配置
    result = await db.execute(
        select(RiskAssessmentMethod).where(
            RiskAssessmentMethod.enterprise_id.is_(None),
            RiskAssessmentMethod.method_type == method_type,
            RiskAssessmentMethod.is_active == True,
        )
    )
    m = result.scalar_one_or_none()
    return m.config if m else None
