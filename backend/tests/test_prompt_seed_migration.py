"""守护：提示词基线种子迁移必须与 seed_prompts_full.json 同步（防"改 JSON 忘重生成"）。"""

import json
from pathlib import Path

from scripts.generate_prompt_seed_migration import OUT_SQL, SEED_JSON, render_sql

BACKEND = Path(__file__).resolve().parents[1]


def test_prompt_seed_migration_matches_json():
    seeds = json.loads(SEED_JSON.read_text(encoding="utf-8"))
    expected = render_sql(seeds)
    actual = OUT_SQL.read_text(encoding="utf-8")
    assert actual == expected, (
        "提示词种子迁移与 seed_prompts_full.json 不一致："
        "请执行 cd backend && python scripts/generate_prompt_seed_migration.py"
    )


def test_prompt_seed_migration_is_insert_only_and_idempotent():
    sql = OUT_SQL.read_text(encoding="utf-8")
    assert "ON CONFLICT (template_code) DO NOTHING" in sql
    assert "UPDATE prompt_templates" not in sql  # 迁移绝不覆盖人工编辑
    assert "DELETE FROM prompt_templates" not in sql


def test_prompt_seed_covers_all_codes_once():
    seeds = json.loads(SEED_JSON.read_text(encoding="utf-8"))
    codes = [s["template_code"] for s in seeds]
    assert len(codes) == len(set(codes)), "seed JSON 存在重复 template_code"
    sql = OUT_SQL.read_text(encoding="utf-8")
    for code in codes:
        assert sql.count(f"$code${code}$code$") == 1, f"迁移中 {code} 应恰好出现一次"


def test_prompt_model_has_server_defaults_for_seed_columns():
    """temperature/max_tokens/status 必须有库级默认值，否则裸 SQL 插入会违反非空约束。"""
    from app.models.prompt import PromptTemplate

    table = PromptTemplate.__table__
    for name in ("temperature", "max_tokens", "status"):
        assert table.columns[name].server_default is not None, name
