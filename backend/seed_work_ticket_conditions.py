"""生成措施条件种子 SQL：YAML（事实源）+ 标准文本（措施正文）→ SQL + 覆盖报告。

两条硬规则（规格 §3）：
  1. 失配即报错中止：YAML 里的措施正文在标准文本里找不到 → RuntimeError（列出失配条目）
  2. 未映射即 unknown：标准文本里有、YAML 未映射 → 写入报告，运行时落 unknown（绝不猜）

用法（仓库根目录）：python backend/seed_work_ticket_conditions.py
"""

from __future__ import annotations

import importlib.util
import json
import random
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT_SQL = ROOT / "backend" / "db_migration_20260921_work_ticket_conditions.sql"
OUT_REPORT = ROOT / "backend" / "work_ticket_conditions_report.json"
YAML_PATH = ROOT / "backend" / "app" / "regulations" / "data" / "work_ticket_conditions.yaml"
STANDARD_TEXT = (
    ROOT / "backend" / "app" / "regulations" / "data" / "texts" / "reg_gb_30871_2022.md"
)
NS = uuid.NAMESPACE_URL
NS_PREFIX = "work-ticket/conditions/"
_CHAPTER_BY_CODE = {
    "DHZY": 5, "YXKJ": 6, "MBCD": 7, "GCZY": 8,
    "QZDZ": 9, "LSYD": 10, "PTZY": 11, "DLZY": 12,
}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _keys():
    return _load(
        "wt_cond_keys",
        ROOT / "backend" / "app" / "services" / "work_ticket_condition_loader.py",
    )


def _load_yaml() -> dict:
    return yaml.safe_load(YAML_PATH.read_text(encoding="utf-8")) or {}


def _parse_all_measures(shuffle_seed: int | None = None) -> dict[str, list[dict]]:
    """从标准文本解析每票种措施（复用既有解析器）；可打乱顺序用于锚定回归测试。"""
    seed = _load("wt_seed", ROOT / "backend" / "app" / "services" / "work_ticket_seed_data.py")
    text = STANDARD_TEXT.read_text(encoding="utf-8")
    out: dict[str, list[dict]] = {}
    for code, chapter in _CHAPTER_BY_CODE.items():
        items = list(seed.parse_measures(text, chapter=chapter))
        if shuffle_seed is not None:
            random.Random(shuffle_seed).shuffle(items)
        out[code] = items
    return out


def _q(value) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _uid(kind: str, key: str) -> str:
    return str(uuid.uuid5(NS, f"{NS_PREFIX}{kind}/{key}"))


def build_sql(measures_override: dict | None = None) -> tuple[str, dict]:
    """返回 (SQL 文本, 覆盖报告)。失配时抛 RuntimeError。"""
    config = _load_yaml()
    conditions: dict = config.get("conditions") or {}
    tickets: dict = config.get("tickets") or {}
    measures = measures_override or _parse_all_measures()
    keys = _keys()

    lines = [
        "-- 20260921 作业票措施条件映射（由 seed_work_ticket_conditions.py 生成，勿手改）",
        "-- 幂等：先按票种清理再插入。锚定键 measure_ref = 措施正文规范化后的 sha256 前 32 位。",
        "BEGIN;",
        "",
        "CREATE TABLE IF NOT EXISTS work_ticket_measure_conditions (",
        "    id            UUID PRIMARY KEY,",
        "    ticket_type   VARCHAR(20) NOT NULL,",
        "    measure_ref   VARCHAR(64) NOT NULL,",
        "    sort_order    INTEGER NOT NULL,",
        "    condition_key VARCHAR(60) NOT NULL,",
        "    UNIQUE (ticket_type, measure_ref, condition_key)",
        ");",
        "CREATE INDEX IF NOT EXISTS idx_wtmc_type ON work_ticket_measure_conditions(ticket_type);",
        "",
        "CREATE TABLE IF NOT EXISTS work_ticket_scenarios (",
        "    id            UUID PRIMARY KEY,",
        "    ticket_type   VARCHAR(20) NOT NULL,",
        "    condition_key VARCHAR(60) NOT NULL,",
        "    label         VARCHAR(200) NOT NULL,",
        "    auto_rule     VARCHAR(60) NULL,",
        "    sort_order    INTEGER NOT NULL,",
        "    UNIQUE (ticket_type, condition_key)",
        ");",
        "",
    ]

    by_ticket: dict[str, int] = {}
    measures_by_ticket: dict[str, int] = {}
    unmapped: list[dict] = []
    missing: list[dict] = []
    scenario_lines: list[str] = []

    for code, block in tickets.items():
        pool = measures.get(code, [])
        by_ref = {keys.measure_ref(m["measure_text"]): m for m in pool}
        mapped_refs: set[str] = set()
        by_ticket[code] = 0
        measures_by_ticket[code] = 0
        lines.append(
            f"DELETE FROM work_ticket_measure_conditions WHERE ticket_type = {_q(code)};"
        )
        for item in block.get("measures") or []:
            ref = keys.measure_ref(item["text"])
            hit = by_ref.get(ref)
            if hit is None:
                missing.append({"ticket_type": code, "text": item["text"][:60]})
                continue
            mapped_refs.add(ref)
            measures_by_ticket[code] += 1
            for cond in item["conditions"]:
                lines.append(
                    "INSERT INTO work_ticket_measure_conditions "
                    "(id, ticket_type, measure_ref, sort_order, condition_key) VALUES "
                    f"({_q(_uid('cond', f'{code}/{ref}/{cond}'))}, {_q(code)}, {_q(ref)}, "
                    f"{hit['sort_order']}, {_q(cond)}) ON CONFLICT (id) DO NOTHING;"
                )
                by_ticket[code] += 1
        for measure in pool:
            if keys.measure_ref(measure["measure_text"]) not in mapped_refs:
                unmapped.append(
                    {
                        "ticket_type": code,
                        "sort_order": measure["sort_order"],
                        "text": measure["measure_text"][:60],
                    }
                )

    if missing:
        raise RuntimeError(
            "条件映射与标准文本失配（YAML 里的下列措施正文在标准文本中找不到）："
            + json.dumps(missing, ensure_ascii=False)
        )

    # 情景项表同时承载"人工勾选项"与"该票种用到的自动项"：
    #   - auto_rule 为空 → 前端情景区展示为勾选框
    #   - auto_rule 非空 → 前端只读回显（"系统自动判定：…"），且提供判定原因用的中文名
    lines.append("")
    lines.append("-- 情景项：auto_rule 为空=人工勾选；非空=该票种用到的自动推断项（只读回显）")
    for code, block in tickets.items():
        scenario_lines.append(f"DELETE FROM work_ticket_scenarios WHERE ticket_type = {_q(code)};")
        manual_keys = [
            key
            for key in (block.get("scenario") or [])
            if not (conditions.get(key) or {}).get("auto")
        ]
        used_auto: set[str] = set()
        for item in block.get("measures") or []:
            for cond in item.get("conditions") or []:
                if (conditions.get(cond) or {}).get("auto"):
                    used_auto.add(cond)
        entries: list[tuple[str, str | None, int]] = [
            (key, None, order) for order, key in enumerate(manual_keys, start=1)
        ]
        entries += [
            (key, str((conditions.get(key) or {}).get("auto")), 100 + order)
            for order, key in enumerate(sorted(used_auto), start=1)
        ]
        for key, auto_rule, order in entries:
            meta = conditions.get(key) or {}
            scenario_lines.append(
                "INSERT INTO work_ticket_scenarios "
                "(id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES "
                f"({_q(_uid('scenario', f'{code}/{key}'))}, {_q(code)}, {_q(key)}, "
                f"{_q(str(meta.get('label') or key))}, "
                f"{_q(auto_rule) if auto_rule else 'NULL'}, {order}) "
                "ON CONFLICT (id) DO NOTHING;"
            )
    lines.extend(scenario_lines)
    lines.append("")
    lines.append("COMMIT;")

    report = {
        "by_ticket": by_ticket,
        # 66 = 建立了映射的**措施条数**；70 = 条件键总行数（4 条措施各自依赖两个条件）
        "mapped_measures": sum(measures_by_ticket.values()),
        "mapped_conditions": sum(by_ticket.values()),
        "measures_by_ticket": measures_by_ticket,
        "unmapped_total": len(unmapped),
        "unmapped": unmapped,
        "conditions": len(conditions),
        "manual_conditions": sum(
            1 for meta in conditions.values() if not (meta or {}).get("auto")
        ),
    }
    return "\n".join(lines) + "\n", report


def main() -> int:
    sql, report = build_sql()
    OUT_SQL.write_text(sql, encoding="utf-8", newline="\n")
    OUT_REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"已生成 {OUT_SQL.name}：{report['mapped_measures']} 条措施建立映射"
        f"（{report['mapped_conditions']} 个条件键），"
        f"未映射 {report['unmapped_total']} 条（见 {OUT_REPORT.name}）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
