import re
from app.services.risk_method_engine import level_from_score


def parse_score(score_str: str) -> float | None:
    m = re.search(r"(-?\d+(?:\.\d+)?)", score_str or "")
    return float(m.group(1)) if m else None


def combine_factor(factors: dict[str, float], mode: str = "min") -> float:
    present = [v for k, v in factors.items() if k != "mode" and v > 0]
    if not present:
        return 1.0
    return min(present) if mode == "min" else _prod(present)


def _prod(values: list[float]) -> float:
    out = 1.0
    for v in values:
        out *= v
    return out


def conversion_reference(inherent_score: str, factors: dict[str, float], mode: str,
                         thresholds: list[dict], method_type: str = "LS") -> dict:
    """固有分值 × 综合系数 → 参考分值/等级。DIRECT 方法由调用方短路。"""
    score = parse_score(inherent_score)
    if score is None:
        return {"factor": 1.0, "reference_score": None, "reference_level": None, "note": "无法解析固有分值"}
    factor = combine_factor(factors, mode)
    ref_score = round(score * factor, 2)
    return {"factor": factor, "reference_score": ref_score,
            "reference_level": level_from_score(method_type, ref_score, thresholds)}
