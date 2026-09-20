"""作业票措施库修复核验探针（只读）。

用法（仓库根目录）：
    python output/playwright/e2e-20260920/scripts/_work_ticket_measure_probe.py

证据输出：同目录 work-ticket-measure-fix.json

核验四项：
  1. DHZY 三个级别 = 16 条、YXKJ = 15 条
  2. 措施总数 = 223
  3. 动火保留的 16 条与 GB 30871 附录A 表 A.1 逐条一致（独立抽取，交叉验证）
  4. 受限空间保留的 15 条与表 A.2 一致
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent / "work-ticket-measure-fix.json"
STANDARD_TEXT = (
    ROOT / "backend" / "app" / "regulations" / "data" / "texts" / "reg_gb_30871_2022.md"
)


def psql(sql: str) -> list[list[str]]:
    """执行只读 SQL，返回以 | 分隔的行（--tuples-only 去掉表头与统计行）。"""
    out = subprocess.run(
        [
            "docker", "exec", "emergency-plan-db", "psql", "-U", "postgres",
            "-d", "emergency_plan", "--no-align", "--tuples-only", "-c", sql,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    return [ln.split("|") for ln in out.strip().splitlines() if ln.strip()]


def appendix_measures(table_no: int) -> list[str]:
    """从标准文本抽取表 A.<table_no> 的措施文本（四列行的第 2 列）。

    这是独立于 work_ticket_seed_data.parse_measures 的第二套抽取实现，
    两条路径结果一致才算交叉验证成立。
    """
    text = STANDARD_TEXT.read_text(encoding="utf-8")
    row = re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]{4,}?)\s*\|")
    header = re.compile(rf"^表A[.．]{table_no}(?:\s|$)")
    table_title = re.compile(r"^表A[.．][1-8](?:\s|$)")
    in_table = False
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if table_title.match(stripped):
            in_table = bool(header.match(stripped))
            continue
        if not in_table:
            continue
        match = row.match(stripped)
        if match and int(match.group(1)) == len(out) + 1:
            out.append(match.group(2).strip())
    return out


def main() -> int:
    counts = {
        code: int(total)
        for code, total in psql(
            "SELECT t.code, count(m.id) FROM work_ticket_templates t "
            "LEFT JOIN work_ticket_template_measures m ON m.template_id=t.id "
            "GROUP BY t.code;"
        )
    }
    level_counts = {
        f"{code}/{level}": int(total)
        for code, level, total in psql(
            "SELECT t.code, coalesce(t.level,'-'), count(m.id) FROM work_ticket_templates t "
            "LEFT JOIN work_ticket_template_measures m ON m.template_id=t.id "
            "GROUP BY t.code, t.level ORDER BY t.code, t.level;"
        )
    }
    total = int(psql("SELECT count(*) FROM work_ticket_template_measures;")[0][0])
    db_fire = [row[1].strip() for row in psql(
        "SELECT m.sort_order, m.measure_text FROM work_ticket_template_measures m "
        "JOIN work_ticket_templates t ON t.id=m.template_id "
        "WHERE t.code='DHZY' AND t.level='二级' ORDER BY m.sort_order;"
    )]
    db_space = [row[1].strip() for row in psql(
        "SELECT m.sort_order, m.measure_text FROM work_ticket_template_measures m "
        "JOIN work_ticket_templates t ON t.id=m.template_id "
        "WHERE t.code='YXKJ' ORDER BY m.sort_order;"
    )]
    text_fire = appendix_measures(1)
    text_space = appendix_measures(2)

    checks = {
        "dhzy_levels_are_16": all(
            level_counts.get(f"DHZY/{level}") == 16 for level in ("特级", "一级", "二级")
        ),
        "yxkj_is_15": counts.get("YXKJ") == 15,
        # 注意按"级别"断言：GCZY 4 个级别 × 15、QZDZ 3 个级别 × 20，
        # 按 code 聚合会得到 60 / 60，那样比的是合计而不是每张票面的条数。
        "other_types_unchanged": (
            all(level_counts.get(f"GCZY/{lv}") == 15 for lv in ("Ⅰ级", "Ⅱ级", "Ⅲ级", "Ⅳ级"))
            and all(level_counts.get(f"QZDZ/{lv}") == 20 for lv in ("一级", "二级", "三级"))
            and level_counts.get("LSYD/-") == 14
            and level_counts.get("MBCD/-") == 11
            and level_counts.get("PTZY/-") == 11
            and level_counts.get("DLZY/-") == 4
        ),
        "total_is_223": total == 223,
        "appendix_extract_fire_16": len(text_fire) == 16,
        "appendix_extract_space_15": len(text_space) == 15,
        "fire_text_matches_appendix": db_fire == text_fire,
        "space_text_matches_appendix": db_space == text_space,
    }
    EVIDENCE.write_text(
        json.dumps(
            {
                "counts_by_code": counts,
                "counts_by_level": level_counts,
                "total": total,
                "fire_count": len(db_fire),
                "space_count": len(db_space),
                "fire_last": db_fire[-1:] if db_fire else [],
                "space_last": db_space[-1:] if db_space else [],
                "checks": checks,
                "all_passed": all(checks.values()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
