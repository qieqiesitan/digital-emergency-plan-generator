"""诊断：打印含指定片段的所有 OpenAPI 路径与方法。"""
import json
import urllib.request

openapi = json.load(urllib.request.urlopen("http://127.0.0.1:8000/openapi.json"))
for needle in ("chemicals/ai/questions", "risk-management/ai/suggest-objects",
               "suggest-mapping", "checklist-template", "record-assist", "onboarding/candidates"):
    print(f"--- {needle}")
    for path, ops in openapi["paths"].items():
        if needle in path:
            print(f"    {sorted(ops.keys())} {path}")
