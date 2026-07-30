"""风险评估多方法计算引擎。支持 LS 矩阵、LEC 评价法、煤矿 LS 矩阵、直接判定法。"""
from typing import Optional
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.risk_management import RiskAssessmentMethod

@dataclass
class RiskResult:
    risk_level: str; risk_score: str; action: str; deadline: str

def compute_risk(method_type: str, params: dict, config: dict | None = None) -> RiskResult:
    if method_type == "DIRECT":
        level = params.get("risk_level", "一般")
        return RiskResult(risk_level=level, risk_score="-", action=level, deadline="按需")
    thresholds = (config or {}).get("risk_thresholds", [])
    if method_type == "LS":
        l_val = float(params.get("l", 3)); s_val = float(params.get("s", 3)); r = int(l_val * s_val); score_str = f"R={r}"
    elif method_type == "LEC":
        l_val = float(params.get("l", 1)); e_val = float(params.get("e", 1)); c_val = float(params.get("c", 1)); r = int(l_val * e_val * c_val); score_str = f"D={r}"
    elif method_type == "COAL_LS":
        l_val = float(params.get("l", 3)); s_val = float(params.get("s", 3)); r = int(l_val * s_val); score_str = f"R={r}"
        if not thresholds:
            thresholds = [
                {"min":20,"max":25,"level":"重大","action":"立即停产整改","deadline":"立即"},
                {"min":15,"max":19,"level":"较大","action":"限期停产整改","deadline":"1个月"},
                {"min":10,"max":14,"level":"一般","action":"限期整改","deadline":"3个月"},
                {"min":1,"max":9,"level":"低","action":"加强日常管理","deadline":"持续"},
            ]
    else:
        return RiskResult(risk_level="一般", risk_score="-", action="未知方法", deadline="N/A")
    for t in thresholds:
        if t["min"] <= r <= t["max"]:
            return RiskResult(risk_level=t["level"], risk_score=score_str, action=t.get("action",""), deadline=t.get("deadline",""))
    return RiskResult(risk_level="低", risk_score=score_str, action="日常管理", deadline="持续")

async def get_active_method_config(db: AsyncSession, enterprise_id: str, method_type: str = "LS") -> dict | None:
    result = await db.execute(select(RiskAssessmentMethod).where(RiskAssessmentMethod.enterprise_id==enterprise_id, RiskAssessmentMethod.method_type==method_type, RiskAssessmentMethod.is_active==True))
    m = result.scalar_one_or_none()
    if m: return m.config
    result = await db.execute(select(RiskAssessmentMethod).where(RiskAssessmentMethod.enterprise_id.is_(None), RiskAssessmentMethod.method_type==method_type, RiskAssessmentMethod.is_active==True))
    m = result.scalar_one_or_none()
    return m.config if m else None
