"""列出本次改动涉及的 AI 端点：装饰器路径 + 函数名。"""
import pathlib
import re

FILES = [
    "backend/app/routers/hazardous_chemicals.py",
    "backend/app/routers/resources_ext.py",
    "backend/app/routers/risk_sources_ext.py",
    "backend/app/routers/surrounding_ai.py",
    "backend/app/routers/risk_management.py",
    "backend/app/routers/enterprise_org.py",
    "backend/app/routers/hazard_management.py",
    "backend/app/routers/extraction.py",
    "backend/app/routers/risk_notice_card.py",
    "backend/app/routers/onboarding.py",
]

WANT = (
    "questions", "generate", "suggest", "smart", "guide", "analyze", "migrate",
    "checklist", "assist", "grade", "governance", "inspection", "schedule",
    "wizard", "signs", "mapping", "candidates", "import",
)

for file in FILES:
    lines = pathlib.Path(file).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        m = re.match(r'@router\.(get|post|put|delete)\("([^"]*)"', line)
        if not m:
            continue
        for j in range(i + 1, min(i + 8, len(lines))):
            m2 = re.match(r"async def (\w+)", lines[j])
            if m2:
                name = m2.group(1)
                if any(w in name or w in m.group(2) for w in WANT):
                    print(f"{m.group(1).upper():5s} {m.group(2):55s} {file.split('/')[-1]}::{name}")
                break
