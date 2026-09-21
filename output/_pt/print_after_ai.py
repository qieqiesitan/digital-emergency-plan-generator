"""打印各 AI 调用点之后的代码（到函数结束或 30 行），用于判断"释放连接后是否还会写"。"""
import pathlib
import re

TARGETS = {
    "backend/app/routers/hazard_management.py": [1125],
    "backend/app/routers/hazardous_chemicals.py": [228, 328],
    "backend/app/routers/onboarding.py": [79, 102, 126],
    "backend/app/routers/regulations.py": [273],
    "backend/app/routers/resources_ext.py": [518, 730],
    "backend/app/routers/risk_notice_card.py": [374],
    "backend/app/routers/risk_sources_ext.py": [555, 729],
    "backend/app/routers/surrounding_ai.py": [232, 331],
    "backend/app/routers/extraction.py": [48],
}

for file, locs in TARGETS.items():
    lines = pathlib.Path(file).read_text(encoding="utf-8").splitlines()
    for loc in locs:
        # 找函数结束（下一个顶层 def/@router）
        end = len(lines)
        for j in range(loc, len(lines)):
            if re.match(r"^(async )?def |^@router", lines[j]):
                end = j
                break
        seg = lines[loc - 1:min(end, loc + 26)]
        print(f"--- {file}:{loc} （函数剩 {end - loc + 1} 行）")
        for k, text in enumerate(seg, start=loc):
            print(f"{k:5d}| {text}")
