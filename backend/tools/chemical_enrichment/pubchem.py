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


# 数值 + 单位（温度 / 密度 / 压力 / 百分比）
MEASURE_RE = re.compile(
    r"(-?\d+(?:\.\d+)?(?:\s*[-~]\s*-?\d+(?:\.\d+)?)?\s*"
    r"(?:°C|°F|℃|g/cm\s*3|g/cm³|g/mL|kg/m\s*3|mmHg|kPa|%))"
)
DENSITY_RE = re.compile(
    r"(\d+(?:\.\d+)?(?:\s*[-~]\s*\d+(?:\.\d+)?)?\s*(?:g/cm\s*3|g/cm³|g/mL|kg/m\s*3))"
)


def _pick_measure(value: str) -> str:
    """从 PubChem 长文本里取首个“数值+单位”；取不到则留空（不可溯源）。"""
    text = re.sub(r"\s*\([^)]*\)", "", value or "").strip()
    found = MEASURE_RE.search(text)
    if not found:
        return ""
    return re.sub(r"\s+%", "%", re.sub(r"\s+", " ", found.group(1))).strip()


def _pick_density(value: str) -> str:
    """密度只认密度单位，避免把文本里的温度（如 `at 68 °F`）误当密度。"""
    text = re.sub(r"\s*\([^)]*\)", "", value or "").strip()
    found = DENSITY_RE.search(text)
    return re.sub(r"\s+", " ", found.group(1)).strip() if found else ""


def parse_pug_view(record: dict) -> dict:
    by_heading: dict = {}
    for section in _sections(record.get("Record", {})):
        heading = section.get("TOCHeading")
        if heading:
            by_heading.setdefault(heading, []).append(_first_string(section))
    data = {
        "un_no": re.sub(r"\D", "", _pick(by_heading, "UN Number")),
        "physical_state": map_physical_state(_pick(by_heading, "Physical Description")),
        "flash_point": _pick_measure(_pick(by_heading, "Flash Point")),
        "boiling_point": _pick_measure(_pick(by_heading, "Boiling Point")),
        "density": _pick_density(_pick(by_heading, "Density")),
        "ignition_temp": _pick_measure(_pick(by_heading, "Autoignition Temperature")),
        "explosion_limit": "",
    }
    lower = _pick_measure(_pick(by_heading, "Lower Explosive Limit (LEL)"))
    upper = _pick_measure(_pick(by_heading, "Upper Explosive Limit (UEL)"))
    if lower and upper:
        data["explosion_limit"] = f"{lower}~{upper}"
    return data
