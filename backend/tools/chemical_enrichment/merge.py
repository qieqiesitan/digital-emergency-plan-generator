"""合并 ChemBlink / PubChem 取值：已有值不动、冲突留空、其余按 ChemBlink → PubChem 优先。"""
import re

FIELDS = [
    "un_no", "physical_state", "flash_point", "explosion_limit", "ignition_temp",
    "density", "boiling_point", "health_hazard", "fire_hazard",
]


def _number(value: str):
    match = re.search(r"-?\d+(?:\.\d+)?", value or "")
    return float(match.group(0)) if match else None


TEMPERATURE_FIELDS = ("flash_point", "boiling_point", "ignition_temp")


def _canonical(field: str, value: str):
    """把带单位的值归一到可比较的数值：温度 → ℃，密度 → g/mL；无法归一返回 None。"""
    number = _number(value)
    if number is None:
        return None
    if field in TEMPERATURE_FIELDS:
        if "°F" in value:
            return (number - 32) * 5 / 9
        if "℃" in value or "°C" in value:
            return number
        return None
    if field == "density":
        if "kg/m" in value:
            return number / 1000
        if "g/mL" in value or "g/cm" in value:
            return number
        return None
    return None


def _conflict(field: str, left: str, right: str) -> bool:
    if field == "un_no":
        return left != right
    if field in ("physical_state", "health_hazard", "fire_hazard", "explosion_limit"):
        return False  # 文本类字段不做数值冲突判定
    a, b = _canonical(field, left), _canonical(field, right)
    if a is None or b is None:
        return False
    base = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / base > 0.10


def merge_sources(chemblink: dict, pubchem: dict, existing: dict | None = None) -> dict:
    existing = existing or {}
    experimental = set(chemblink.get("experimental") or [])
    merged: dict = {}
    conflicts: list = []
    for field in FIELDS:
        current = (existing.get(field) or "").strip()
        if current:
            merged[field] = current
            continue
        left = (chemblink.get(field) or "").strip()
        right = (pubchem.get(field) or "").strip()
        if left and field in experimental:
            merged[field] = left  # ChemBlink 明确标注实验值 → 直接采信
            continue
        if left and right and _conflict(field, left, right):
            merged[field] = ""
            conflicts.append(field)
            continue
        merged[field] = left or right
    merged["conflicts"] = conflicts
    return merged
