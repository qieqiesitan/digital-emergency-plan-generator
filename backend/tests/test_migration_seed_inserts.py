"""守护：迁移脚本里的种子 INSERT 必须覆盖模型的"非空且无库级默认值"列。

2026-09-19 空库演练发现的两起启动失败都属这一类：
  - `db_migration_20260917_ai_capability.sql`：INSERT 缺 `is_enabled`（模型只有 ORM default）
  - `db_migration_20260917_work_ticket_seed.sql`：INSERT 缺 `validation`

原因：`create_all` 按模型建表，**模型的 ORM default 不会生成库级默认值**；
于是迁移里的 INSERT 少列一列就在空库上触发 not-null 约束 → 全新安装/灾难重建直接启动失败。

本测试静态比对"迁移 INSERT 的列清单"与"模型非空无默认列"，对不上即失败。
"""

import re
from pathlib import Path

import pytest
from sqlalchemy import Integer

import app.main  # noqa: F401  确保所有模型已导入，Base.metadata 完整
from app.database import Base

MIGRATION_DIR = Path(__file__).resolve().parents[1]
INSERT_RE = re.compile(
    r"INSERT\s+INTO\s+(?P<table>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<cols>[^)]*)\)\s*VALUES",
    re.IGNORECASE | re.DOTALL,
)


def _required_columns(table_name: str) -> set[str] | None:
    table = Base.metadata.tables.get(table_name)
    if table is None:
        return None
    return {
        col.name
        for col in table.columns
        # 主键也纳入：种子 INSERT 若不写主键，就必须有库级默认值（gen_random_uuid() 等）
        # 例外：单列整数主键由 SQLAlchemy 建成 SERIAL/IDENTITY，库级默认自动存在
        # （如 prompt_templates.id → nextval('prompt_templates_id_seq')）
        if not col.nullable and col.server_default is None
        and not (col.primary_key and isinstance(col.type, Integer))
    }


def test_seed_inserts_cover_required_columns():
    offenders: list[str] = []
    checked = 0
    for path in sorted(MIGRATION_DIR.glob("db_migration_*.sql")):
        text = path.read_text(encoding="utf-8")
        for match in INSERT_RE.finditer(text):
            table = match.group("table")
            required = _required_columns(table)
            if required is None:
                continue  # 表不在模型里（纯 SQL 表）：交给演练验证
            inserted = {
                col.strip().strip('"').lower()
                for col in match.group("cols").split(",")
                if col.strip()
            }
            checked += 1
            missing = sorted(required - inserted)
            if missing:
                line = text[: match.start()].count("\n") + 1
                offenders.append(f"{path.name}:{line} INSERT INTO {table} 缺列 {missing}")
    assert checked > 0, "未扫描到任何种子 INSERT（守护测试失效）"
    assert not offenders, (
        "以下种子 INSERT 在空库上会违反非空约束（模型无库级默认值）：\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("table", ["ai_capabilities", "work_ticket_template_fields"])
def test_known_fresh_install_tables_are_guarded(table):
    """两起已修复案例保持可回归（表存在且被扫描）。"""
    assert table in Base.metadata.tables
