"""打印待插入释放点的上下文，便于人工复核。"""
import pathlib

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

for file, locs in TARGETS.items():
    lines = pathlib.Path(file).read_text(encoding="utf-8").splitlines()
    for loc in locs:
        print(f"--- {file}:{loc}")
        for j in range(max(0, loc - 4), min(len(lines), loc + 1)):
            print(f"{j + 1:5d}| {lines[j]}")
