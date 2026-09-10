"""合并 ChemBlink / PubChem 取值：已有值不动、冲突留空、其余按 ChemBlink → PubChem 优先。"""
import re

FIELDS = [
    "un_no", "physical_state", "flash_point", "explosion_limit", "ignition_temp",
    "density", "boiling_point", "health_hazard", "fire_hazard",
]


def _number(value: str):
    match = re.search(r"-?\d+(?:\.\d+)?", value or "")
    return float(match.group(0)) if match else None


def _conflict(field: str, left: str, right: str) -> bool:
    if field == "un_no":
        return left != right
    a, b = _number(left), _number(right)
    if a is None or b is None:
        return False
    base = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / base > 0.10


def merge_sources(chemblink: dict, pubchem: dict, existing: dict | None = None) -> dict:
    existing = existing or {}
    merged: dict = {}
    conflicts: list = []
    for field in FIELDS:
        current = (existing.get(field) or "").strip()
        if current:
            merged[field] = current
            continue
        left = (chemblink.get(field) or "").strip()
        right = (pubchem.get(field) or "").strip()
        if left and right and _conflict(field, left, right):
            merged[field] = ""
            conflicts.append(field)
            continue
        merged[field] = left or right
    merged["conflicts"] = conflicts
    return merged
