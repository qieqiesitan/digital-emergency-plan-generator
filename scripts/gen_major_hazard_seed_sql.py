"""由 docs/标准数据-GB18218-2018/*.json 生成常量迁移 SQL。

输出 backend/db_migration_20260917_standard_constants.sql：
- DDL：4 张常量表
- 种子：表1 85 条 + 表2 24 条 + 表3 14 条 + 表4 24 条 + 表5 5 条 + 表6 4 条

id 一律用 uuid5(NAMESPACE_URL, "major-hazard/GB18218-2018/<表>/<自然键>")，
配 ON CONFLICT (id) DO NOTHING，保证脚本可重复执行、幂等可重放。

用法：python scripts/gen_major_hazard_seed_sql.py
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "标准数据-GB18218-2018"
OUT = ROOT / "backend" / "db_migration_20260917_standard_constants.sql"
NS = uuid.NAMESPACE_URL
STANDARD = "GB18218-2018"
NS_PREFIX = "major-hazard/GB18218-2018/"


def _uid(kind: str, key: str) -> str:
    return str(uuid.uuid5(NS, f"{NS_PREFIX}{kind}/{key}"))


def _q(value) -> str:
    """SQL 字符串字面量转义（单引号翻倍）。"""
    return "'" + str(value).replace("'", "''") + "'"


def _num(value) -> str:
    """把 '150(净重)' 这类带说明的临界量取出数值；纯数值原样返回；取不到返回 NULL。"""
    text = str(value).strip()
    if text in ("", "—", "-", "None"):
        return "NULL"
    buf, dot = "", False
    for ch in text:
        if ch.isdigit():
            buf += ch
        elif ch == "." and not dot:
            buf += ch
            dot = True
        else:
            break
    return buf or "NULL"


def _note(value) -> str | None:
    """数值以外还有说明文字时，把原文留进 critical_note。"""
    text = str(value).strip()
    if text in ("", "—", "-", "None"):
        return None
    if _num(text) == text:
        return None
    return text


def _load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def build_sql() -> str:
    t1 = _load("gb18218-2018-table1-critical-quantities.json")
    t2 = _load("gb18218-2018-table2-critical-quantities.json")
    t3 = _load("gb18218-2018-table3-beta-gas.json")
    t4 = _load("gb18218-2018-table4-beta-class.json")
    t5 = _load("gb18218-2018-table5-alpha.json")
    t6 = _load("gb18218-2018-table6-levels.json")

    lines: list[str] = [
        "-- 20260917 GB 18218-2018《危险化学品重大危险源辨识》常量表与种子数据",
        "-- 本文件由 scripts/gen_major_hazard_seed_sql.py 生成，请勿手工编辑。",
        "-- 数据来源：docs/标准数据-GB18218-2018/（标准正本 PDF 抽取，CAS 校验位已逐条验证）。",
        "-- id 使用 uuid5(NAMESPACE_URL, 'major-hazard/GB18218-2018/<表>/<自然键>')，",
        "-- 每条插入均按主键冲突跳过，保证幂等可重放。",
        "",
        "CREATE TABLE IF NOT EXISTS critical_quantities (",
        "    id UUID PRIMARY KEY,",
        "    standard VARCHAR(40) NOT NULL,",
        "    table_no VARCHAR(4) NOT NULL,",
        "    chemical_name VARCHAR(500) NOT NULL,",
        "    alias VARCHAR(500),",
        "    cas_no VARCHAR(120),",
        "    category VARCHAR(80),",
        "    symbol VARCHAR(20),",
        "    critical_t NUMERIC(18, 6),",
        "    critical_note VARCHAR(80),",
        "    source_page INTEGER,",
        "    created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        ");",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_cq_table1_name",
        "    ON critical_quantities (standard, chemical_name) WHERE table_no = '1';",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_cq_table2_symbol",
        "    ON critical_quantities (standard, symbol) WHERE table_no = '2';",
        "CREATE INDEX IF NOT EXISTS ix_cq_cas ON critical_quantities (cas_no);",
        "",
        "CREATE TABLE IF NOT EXISTS hazard_beta_factors (",
        "    id UUID PRIMARY KEY,",
        "    standard VARCHAR(40) NOT NULL,",
        "    source_table VARCHAR(4) NOT NULL,",
        "    chemical_name VARCHAR(200),",
        "    category VARCHAR(80),",
        "    symbol VARCHAR(20),",
        "    beta NUMERIC(6, 3) NOT NULL,",
        "    source_page INTEGER,",
        "    created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        ");",
        "CREATE INDEX IF NOT EXISTS ix_hbf_name ON hazard_beta_factors (standard, chemical_name);",
        "CREATE INDEX IF NOT EXISTS ix_hbf_symbol ON hazard_beta_factors (standard, symbol);",
        "",
        "CREATE TABLE IF NOT EXISTS exposure_alpha_factors (",
        "    id UUID PRIMARY KEY,",
        "    standard VARCHAR(40) NOT NULL,",
        "    label VARCHAR(40) NOT NULL,",
        "    population_min INTEGER NOT NULL,",
        "    population_max INTEGER,",
        "    alpha NUMERIC(4, 2) NOT NULL,",
        "    source_page INTEGER,",
        "    created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        ");",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_eaf_label",
        "    ON exposure_alpha_factors (standard, label);",
        "",
        "CREATE TABLE IF NOT EXISTS major_hazard_levels (",
        "    id UUID PRIMARY KEY,",
        "    standard VARCHAR(40) NOT NULL,",
        "    level_name VARCHAR(20) NOT NULL,",
        "    r_expression VARCHAR(60) NOT NULL,",
        "    r_min NUMERIC(12, 3),",
        "    r_max NUMERIC(12, 3),",
        "    source_page INTEGER,",
        "    created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        ");",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_mhl_level",
        "    ON major_hazard_levels (standard, level_name);",
        "",
    ]

    for r in t1:
        key = f"t1/{r['seq']}"
        cas = "；".join(r["cas"]) if r["cas"] else None
        note = _note(r["critical_t"])
        lines.append(
            "INSERT INTO critical_quantities "
            "(id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) "
            f"VALUES ({_q(_uid('critical', key))}, {_q(STANDARD)}, '1', {_q(r['name'])}, "
            f"{_q(r['alias']) if r['alias'] else 'NULL'}, {_q(cas) if cas else 'NULL'}, "
            f"{_num(r['critical_t'])}, {_q(note) if note else 'NULL'}, {r['source_page']}) "
            "ON CONFLICT (id) DO NOTHING;"
        )

    for r in t2:
        # 分组表头行的符号形如 "J(健康危害性符号)" / "W(物理危险性符号)"，带括号；
        # 真正的分级符号是 J1~J5、W1.1~W11，不含括号。
        if not r["symbol"] or "(" in r["symbol"]:
            continue  # 跳过「健康危害 J」「物理危险 W」两行分组表头
        key = f"t2/{r['symbol']}"
        note = _note(r["critical_t"])
        lines.append(
            "INSERT INTO critical_quantities "
            "(id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) "
            f"VALUES ({_q(_uid('critical', key))}, {_q(STANDARD)}, '2', {_q(r['description'])}, "
            f"{_q(r['category'])}, {_q(r['symbol'])}, {_num(r['critical_t'])}, "
            f"{_q(note) if note else 'NULL'}, {r['source_page']}) "
            "ON CONFLICT (id) DO NOTHING;"
        )

    for r in t3:
        key = f"t3/{r['name']}"
        lines.append(
            "INSERT INTO hazard_beta_factors "
            "(id, standard, source_table, chemical_name, beta, source_page) "
            f"VALUES ({_q(_uid('beta', key))}, {_q(STANDARD)}, '3', {_q(r['name'])}, "
            f"{_num(r['beta'])}, {r['source_page']}) ON CONFLICT (id) DO NOTHING;"
        )

    for r in t4:
        key = f"t4/{r['symbol']}"
        lines.append(
            "INSERT INTO hazard_beta_factors "
            "(id, standard, source_table, category, symbol, beta, source_page) "
            f"VALUES ({_q(_uid('beta', key))}, {_q(STANDARD)}, '4', {_q(r['category'])}, "
            f"{_q(r['symbol'])}, {_num(r['beta'])}, {r['source_page']}) "
            "ON CONFLICT (id) DO NOTHING;"
        )

    alpha_rows = [
        ("100人以上", 100, None, "2.0"),
        ("50~99人", 50, 99, "1.5"),
        ("30~49人", 30, 49, "1.2"),
        ("1~29人", 1, 29, "1.0"),
        ("0人", 0, 0, "0.5"),
    ]
    by_label = {r["exposed_population"]: r for r in t5}
    for label, lo, hi, alpha in alpha_rows:
        page = by_label.get(label, {}).get("source_page", 11)
        lines.append(
            "INSERT INTO exposure_alpha_factors "
            "(id, standard, label, population_min, population_max, alpha, source_page) "
            f"VALUES ({_q(_uid('alpha', label))}, {_q(STANDARD)}, {_q(label)}, {lo}, "
            f"{hi if hi is not None else 'NULL'}, {_num(alpha)}, {page}) "
            "ON CONFLICT (id) DO NOTHING;"
        )

    level_bounds = {
        "一级": ("100", "NULL"),
        "二级": ("50", "100"),
        "三级": ("10", "50"),
        "四级": ("NULL", "10"),
    }
    for r in t6:
        lo, hi = level_bounds[r["level"]]
        lines.append(
            "INSERT INTO major_hazard_levels "
            "(id, standard, level_name, r_expression, r_min, r_max, source_page) "
            f"VALUES ({_q(_uid('level', r['level']))}, {_q(STANDARD)}, {_q(r['level'])}, "
            f"{_q(r['r_expression'])}, {lo}, {hi}, {r['source_page']}) "
            "ON CONFLICT (id) DO NOTHING;"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    sql = build_sql()
    OUT.write_text(sql, encoding="utf-8", newline="\n")
    print(f"已生成 {OUT.relative_to(ROOT)}（{len(sql.splitlines())} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
