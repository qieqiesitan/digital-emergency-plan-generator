"""PubChem PUG-View 解析：UN 号 / 物理状态 / 爆炸极限 / 引燃温度 / 闪点 / 沸点 / 密度。"""
import re

GAS_WORDS = ("gas", "vapor")
SOLID_WORDS = ("solid", "crystal", "powder", "granul")


def map_physical_state(description: str) -> str:
    text = (description or "").lower()
    if not text:
        return ""
    if "liquid" in text:
        return "液态"
    if any(word in text for word in SOLID_WORDS):
        return "固态"
    if any(word in text for word in GAS_WORDS):
        return "气态"
    return ""


def _sections(node: dict) -> list:
    out = []
    for section in node.get("Section") or []:
        out.append(section)
        out.extend(_sections(section))
    return out


def _first_string(section: dict) -> str:
    for info in section.get("Information") or []:
        value = info.get("Value", {})
        if "StringWithMarkup" in value:
            return " ".join(x.get("String", "") for x in value["StringWithMarkup"]).strip()
        if "Number" in value:
            return str(value["Number"])
    return ""


def _pick(by_heading: dict, heading: str) -> str:
    return next((v for v in by_heading.get(heading, []) if v), "")


def _compact(value: str) -> str:
    """去掉数值与百分号之间的空格，并剥离文献引用后缀（如 `(NTP, 1992)`）。"""
    value = re.sub(r"\s*\([^)]*\)\s*$", "", value.strip())
    return re.sub(r"\s+%", "%", value.strip())


def parse_pug_view(record: dict) -> dict:
    by_heading: dict = {}
    for section in _sections(record.get("Record", {})):
        heading = section.get("TOCHeading")
        if heading:
            by_heading.setdefault(heading, []).append(_first_string(section))
    data = {
        "un_no": re.sub(r"\D", "", _pick(by_heading, "UN Number")),
        "physical_state": map_physical_state(_pick(by_heading, "Physical Description")),
        "flash_point": _compact(_pick(by_heading, "Flash Point")),
        "boiling_point": _compact(_pick(by_heading, "Boiling Point")),
        "density": _compact(_pick(by_heading, "Density")),
        "ignition_temp": _compact(_pick(by_heading, "Autoignition Temperature")),
        "explosion_limit": "",
    }
    lower = _compact(_pick(by_heading, "Lower Explosive Limit (LEL)"))
    upper = _compact(_pick(by_heading, "Upper Explosive Limit (UEL)"))
    if lower and upper:
        data["explosion_limit"] = f"{lower}~{upper}"
    return data
