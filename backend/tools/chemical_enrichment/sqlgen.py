"""生成幂等填充 SQL 与 JSON 快照：逐字段 COALESCE(NULLIF(...))，只填空、不覆盖。"""
import json
from pathlib import Path

HEADER = """-- 2026-09-10 化学品库字段富集（ChemBlink + PubChem，只填空不覆盖）
-- 生成脚本：backend/tools/enrich_chemical_library.py
-- 口径：只采实验值/无标注实测值；纯计算值留空；双源冲突留空并记录在报告中。
-- 幂等：逐字段 COALESCE(NULLIF(字段,''), 新值)，可重复执行。
"""


def _escape(value: str) -> str:
    return value.replace("'", "''")


def render_update_sql(rows: list) -> str:
    lines: list = []
    for row in rows:
        values = {k: v.strip() for k, v in row["values"].items() if (v or "").strip()}
        if not values:
            continue
        assignments = ", ".join(
            f"{field} = COALESCE(NULLIF({field},''), '{_escape(value)}')"
            for field, value in values.items()
        )
        lines.append(f"UPDATE chemical_library SET {assignments} WHERE id = '{row['id']}';")
    if not lines:
        return ""
    return HEADER + "\n" + "\n".join(lines) + "\n"


def write_outputs(rows: list, sql_path: Path, json_path: Path) -> None:
    sql_path = Path(sql_path)
    json_path = Path(json_path)
    sql_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    sql_path.write_text(render_update_sql(rows), encoding="utf-8", newline="\n")
    json_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
