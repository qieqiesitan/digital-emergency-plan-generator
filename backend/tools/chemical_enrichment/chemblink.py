"""ChemBlink 中文产品页解析：理化性质（实验值优先）、GHS 危害分类、UN 号。

口径：只采「实验值」或无标注的实测值；只有「计算值」时返回空串；
无单位的裸数值（如部分页面的「密度 0.777」）视为不可溯源，同样留空。
"""
import re

from bs4 import BeautifulSoup

FIELD_LABELS = [
    "密度", "熔点", "沸点", "折射率", "闪点", "蒸汽压", "溶解性", "外观", "性状",
    "安全数据", "危险品标志", "危害分类", "分子量", "CAS",
]
FIRE_KEYWORDS = ("易燃", "爆炸", "氧化", "自燃", "自热", "遇水放出", "有机过氧化物", "加压气体")
HEALTH_KEYWORDS = (
    "急性毒性", "皮肤腐蚀", "皮肤刺激", "严重眼损伤", "眼刺激", "呼吸道致敏", "皮肤致敏",
    "生殖细胞致突变", "致癌", "生殖毒性", "特定目标器官毒性", "吸入危害",
)
VALUE_RE = re.compile(
    r"(-?\d+(?:\.\d+)?(?:\s*[-~]\s*-?\d+(?:\.\d+)?)?\s*(?:℃|°C|g/cm\s*3|g/cm³|g/mL))"
)


def _lines(html: str) -> list:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", html)
    text = BeautifulSoup(text, "lxml").get_text("\n")
    return [x.strip() for x in text.split("\n") if x.strip()]


def _block(lines: list, label: str) -> str:
    if label not in lines:
        return ""
    out = []
    for line in lines[lines.index(label) + 1:]:
        if line in FIELD_LABELS:
            break
        out.append(line)
    return " ".join(out)


def _normalize(value: str) -> str:
    value = value.replace("−", "-").replace("°C", "℃").strip(" ,;|*")
    value = re.sub(r"\s+", " ", value)
    # 源页面把密度单位拆成 `g/cm` + `3` 两行 → 收敛为 g/cm³
    value = re.sub(r"g/cm\s*3", "g/cm³", value)
    value = re.sub(r"g/cm3", "g/cm³", value)
    # 去掉数值与单位之间的空格：`52 ℃` → `52℃`、`0.846 g/mL` 保持
    return re.sub(r"\s+(℃|g/cm\s*3|g/cm³)", r"\1", value)


def _pick_value(block: str) -> tuple:
    """返回 (值, 是否带「实验值」标注)。"""
    if not block:
        return "", False
    experimental = re.search(r"([^,;|]*\(实验值\))", block)
    if experimental:
        found = VALUE_RE.search(experimental.group(1))
        if found:
            return _normalize(found.group(1)), True
    if "计算值" in block and "实验值" not in block:
        return "", False
    found = VALUE_RE.search(block)
    return (_normalize(found.group(1)), False) if found else ("", False)


def _parse_ghs(lines: list) -> tuple:
    """GHS 表按「中文类别名 / 英文码 / 类别号 / H 码」分行，逐行归入健康或火灾类。"""
    if "危害分类" not in lines:
        return "", ""
    start = lines.index("危害分类") + 1
    window = lines[start:start + 400]
    health: list = []
    fire: list = []
    for index, line in enumerate(window):
        if line.startswith(FIRE_KEYWORDS):
            target = fire
        elif line.startswith(HEALTH_KEYWORDS):
            target = health
        else:
            continue
        number = ""
        if index + 2 < len(window) and re.fullmatch(r"\d+[A-Z]?", window[index + 2]):
            number = window[index + 2]
        target.append(f"{line} 类别{number}" if number else line)
    return "；".join(dict.fromkeys(health)), "；".join(dict.fromkeys(fire))


def parse_product_page(html: str) -> dict:
    lines = _lines(html)
    health, fire = _parse_ghs(lines)
    match = re.search(r"\bUN\s*(\d{4})\b", " ".join(lines))
    experimental: list = []
    values = {}
    for field, label in (("flash_point", "闪点"), ("boiling_point", "沸点"), ("density", "密度")):
        value, is_experimental = _pick_value(_block(lines, label))
        values[field] = value
        if is_experimental:
            experimental.append(field)
    return {
        **values,
        "un_no": match.group(1) if match else "",
        "health_hazard": health,
        "fire_hazard": fire,
        "experimental": experimental,
    }
