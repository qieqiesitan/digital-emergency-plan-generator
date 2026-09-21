"""只读扫描：找出"请求级 db 在作用域内、又 await 了 AI 调用"的代码位置。"""
import pathlib
import re

root = pathlib.Path("backend/app")
AI = (
    "llm_text_completion", "llm_collect_all", "llm_stream_all", "llm_chat_completion",
    "run_extraction", "parse_file", "onboarding", "hazard_ai_service", "risk_ai_service",
    "risk_dual_ai_service", "risk_notice_card_ai", "enterprise_org_service",
    "analyze_four_color", "extract_", "generate_",
)

rows = []
for path in sorted(root.rglob("*.py")):
    if "llm_client" in str(path):
        continue
    lines = path.read_text(encoding="utf-8").splitlines()
    fn, params, fn_line = None, "", 0
    for i, line in enumerate(lines, 1):
        m = re.match(r"\s*(?:async )?def (\w+)\((.*)", line)
        if m:
            fn, params, fn_line = m.group(1), m.group(2), i
            continue
        if fn and "await " in line and any(a in line for a in AI):
            rows.append((str(path).replace("\\", "/"), i, fn, "db" in params))

for r in rows:
    flag = "DB  " if r[3] else "    "
    print(f"{flag}{r[0]}:{r[1]}  in {r[2]}()")
print(f"总计 {len(rows)} 处；其中带请求级 db 的 {sum(1 for r in rows if r[3])} 处")
