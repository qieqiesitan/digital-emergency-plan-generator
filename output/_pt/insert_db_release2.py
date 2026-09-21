"""在第二批（服务型 AI 调用）点位前插入释放语句；import 放到完整 import 块之后。"""
import pathlib
import re

IMPORT_LINE = "from app.services.db_guard import release_request_connection\n"
MARK = "await release_request_connection(db)"
COMMENT = "  # 长耗时 AI 调用前把连接还池，避免 idle in transaction 占满池（压测 N-32）"

TARGETS = {
    "backend/app/routers/extraction.py": [29],
    "backend/app/routers/enterprise_org.py": [174],
    "backend/app/routers/hazard_management.py": [1563, 1863, 1892, 1926, 1952, 1980, 2008],
    "backend/app/routers/risk_management.py": [1014, 1263, 1270, 1277, 1289, 1296, 1320],
}


def import_block_end(lines: list[str]) -> int:
    """返回 import 块的最后一个行号（0 基），遇到 .py 语义上的第一条语句即停。"""
    depth = 0
    last = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if depth == 0 and not (stripped.startswith(("import ", "from ")) or stripped == ""
                               or stripped.startswith("#")):
            break
        depth += line.count("(") - line.count(")")
        if depth <= 0:
            depth = 0
            last = i
    return last


for file, locs in TARGETS.items():
    path = pathlib.Path(file)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = False
    for loc in sorted(locs, reverse=True):
        target = lines[loc - 1]
        if MARK in target:
            print(f"跳过（已存在）: {file}:{loc}")
            continue
        indent = re.match(r"(\s*)", target).group(1)
        lines.insert(loc - 1, f"{indent}{MARK}{COMMENT}\n")
        changed = True
        print(f"插入: {file}:{loc} indent={len(indent)}")
    if changed and not any(IMPORT_LINE.strip() == l.strip() for l in lines):
        pos = import_block_end(lines) + 1
        lines.insert(pos, IMPORT_LINE)
        print(f"补 import: {file} @ line {pos + 1}")
    if changed:
        path.write_text("".join(lines), encoding="utf-8")
