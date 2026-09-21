"""列出 8 个 AI JSON 端点的重复样板（用于抽取共用入口）。"""
import pathlib
import re

FILES = [
    "backend/app/routers/hazardous_chemicals.py",
    "backend/app/routers/surrounding_ai.py",
    "backend/app/routers/resources_ext.py",
    "backend/app/routers/risk_sources_ext.py",
]

for f in FILES:
    lines = pathlib.Path(f).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if "await llm_text_completion(" in line:
            end = min(i + 26, len(lines))
            seg = [ln for ln in lines[i - 2:end]]
            fences = "lines[1:]" if any("lines[1:]" in x for x in seg) else (
                "raw[3:]" if any("raw[3:]" in x for x in seg) else "?")
            print(f"--- {f}:{i + 1}  fences={fences}")
            for j, text in enumerate(seg, start=i - 1):
                print(f"{j:5d}| {text}")
            print()
