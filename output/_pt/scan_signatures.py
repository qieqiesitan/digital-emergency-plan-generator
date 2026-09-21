"""打印待改点位所在函数的签名，确认是否存在请求级 db。"""
import pathlib
import re

TARGETS = {
    "backend/app/routers/diagrams.py": [59],
    "backend/app/routers/extraction.py": [48],
    "backend/app/routers/hazard_management.py": [1125],
    "backend/app/routers/hazardous_chemicals.py": [228, 328],
    "backend/app/routers/onboarding.py": [79, 102, 126],
    "backend/app/routers/regulations.py": [273],
    "backend/app/routers/resources_ext.py": [518, 730],
    "backend/app/routers/risk_notice_card.py": [374],
    "backend/app/routers/risk_sources_ext.py": [555, 729],
    "backend/app/routers/surrounding_ai.py": [232, 331],
}

for f, locs in TARGETS.items():
    lines = pathlib.Path(f).read_text(encoding="utf-8").splitlines()
    for loc in locs:
        for i in range(loc - 1, 0, -1):
            if re.match(r"\s*(?:async )?def (\w+)\(", lines[i - 1]):
                chunk = " ".join(x.strip() for x in lines[i - 1:i + 5])
                end = chunk.find("):")
                sig = chunk[: end + 1] if end > 0 else chunk[:200]
                print(f"{f}:{loc}  ->  {sig[:190]}")
                break
