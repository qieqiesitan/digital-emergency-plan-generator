"""删除前复核：这 4 个文件是否真的没有任何引用（含动态 import / lazy / 测试）。"""
import pathlib
import re

TARGETS = [
    "components/enterprise/RiskSourceForm",
    "mobile/screens/RiskSourceListScreen",
    "mobile/components/plan/PlanCard",
    "mobile/hooks/useStreamGeneration",
]

root = pathlib.Path("frontend/src")
files = [p for p in root.rglob("*") if p.suffix in (".ts", ".tsx")]

for target in TARGETS:
    hits = []
    stem = target.split("/")[-1]
    for p in files:
        if str(p).replace("\\", "/").endswith(target + ".tsx") or str(p).replace("\\", "/").endswith(target + ".ts"):
            continue
        text = p.read_text(encoding="utf-8")
        # 精确匹配 import 该模块，或按名字引用（PlanCard/useStreamGeneration 等）
        if target in text.replace("\\", "/") or re.search(rf'\b{re.escape(stem)}\b', text):
            hits.append(str(p).replace("\\", "/"))
    print(f"{'[X] 仍被引用' if hits else '[OK] 无引用'}  {target}")
    for h in hits[:6]:
        print(f"      - {h}")
