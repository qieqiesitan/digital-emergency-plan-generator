"""量一量 AI 端点样板（llm_text_completion + 围栏剥离 + JSON 解析 + 异常映射）重复了多少行。"""
import pathlib
import re

FILES = [
    "backend/app/routers/hazardous_chemicals.py",
    "backend/app/routers/surrounding_ai.py",
    "backend/app/routers/resources_ext.py",
    "backend/app/routers/risk_sources_ext.py",
]

PAT = re.compile(
    r"try:\s*\n\s*(?:await release_request_connection\(db\).*\n\s*)?raw = await llm_text_completion\("
    r"(?:[^\n]*\n)*?.*?raise HTTPException\(500, \"AI (?:调用失败|返回格式异常)",
    re.S,
)

total = 0
for f in FILES:
    src = pathlib.Path(f).read_text(encoding="utf-8")
    for m in PAT.finditer(src):
        n = m.group(0).count("\n") + 1
        total += n
        print(f"{f}: {n} 行")
print(f"合计重复样板 {total} 行（涉及 {len(FILES)} 个文件）")
