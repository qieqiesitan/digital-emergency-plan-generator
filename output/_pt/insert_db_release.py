"""在指定的 AI 调用点之前插入 `await release_request_connection(db)`。

行号来自 output/_pt/scan_ai_callsites.py 的扫描结果；按文件倒序插入以免行号漂移。
"""
import pathlib
import re

IMPORT_LINE = "from app.services.db_guard import release_request_connection\n"
MARK = "await release_request_connection(db)"

TARGETS = {
    "backend/app/routers/hazardous_chemicals.py": [228, 328],
    "backend/app/routers/resources_ext.py": [518, 730],
    "backend/app/routers/risk_sources_ext.py": [555, 729],
    "backend/app/routers/surrounding_ai.py": [232, 331],
    "backend/app/routers/hazard_management.py": [1125],
    "backend/app/routers/regulations.py": [273],
    "backend/app/services/extraction_service.py": [119],
    "backend/app/services/onboarding_service.py": [151, 170, 201],
    "backend/app/services/risk_notice_card_ai.py": [44, 103],
}

COMMENT = "  # 长耗时 AI 调用前把连接还池，避免 idle in transaction 占满池（压测 N-32）"

for file, locs in TARGETS.items():
    path = pathlib.Path(file)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    # 自下而上插入
    for loc in sorted(locs, reverse=True):
        target = lines[loc - 1]
        if MARK in target:
            print(f"跳过（已存在）: {file}:{loc}")
            continue
        indent = re.match(r"(\s*)", target).group(1)
        lines.insert(loc - 1, f"{indent}{MARK}{COMMENT}\n")
        print(f"插入: {file}:{loc}  indent={len(indent)}")
    # 补 import（放在最后一条 from app. 之后）
    if not any(IMPORT_LINE.strip() == l.strip() for l in lines):
        last = max(i for i, l in enumerate(lines) if l.startswith("from app.") or l.startswith("import "))
        lines.insert(last + 1, IMPORT_LINE)
        print(f"补 import: {file}")
    path.write_text("".join(lines), encoding="utf-8")
