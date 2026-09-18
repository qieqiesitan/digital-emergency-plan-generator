"""由 seed_prompts_full.json 生成基线提示词种子迁移（幂等、仅新增）。

背景（2026-09-19 空库演练）：提示词模板只靠人工脚本 `backend/seed_prompts_full.py` 灌数据，
**全新安装的库 prompt_templates 为空** —— 生成链路拿到空系统提示词、提示词管理页空白。

约定：
- 迁移只做"**缺失即插入**"（`ON CONFLICT (template_code) DO NOTHING`），绝不覆盖人工编辑；
- 需要"用 JSON 覆盖线上模板"时仍用 `python seed_prompts_full.py`（它是 upsert 语义）；
- 本脚本与 `backend/tests/test_prompt_seed_migration.py` 一起防止"JSON 改了、迁移没重生成"。

用法：
    cd backend && python scripts/generate_prompt_seed_migration.py
输出：
    backend/db_migration_20260919_prompt_templates_seed.sql
"""

import json
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SEED_JSON = BACKEND / "seed_prompts_full.json"
OUT_SQL = BACKEND / "db_migration_20260919_prompt_templates_seed.sql"

HEADER = """-- 20260919 提示词模板基线种子（**由 scripts/generate_prompt_seed_migration.py 生成，勿手改**）
--
-- 目的：全新安装（空库）也能拿到完整提示词模板；只做"缺失即插入"，
--       已存在的 template_code 一律跳过，不会覆盖页面上的人工编辑。
-- 刷新线上模板（覆盖语义）仍用：python seed_prompts_full.py
-- 改完种子 JSON 后重新生成：python scripts/generate_prompt_seed_migration.py
\n"""


def _q(value: str, tag: str) -> str:
    """美元引用字符串：提示词里含单引号、反斜杠、换行都不会破坏 SQL。"""
    if value is None:
        return "NULL"
    if value == "":
        return "''"
    return f"${tag}${value}${tag}$"


def render_sql(seeds: list[dict]) -> str:
    lines = [HEADER]
    for item in sorted(seeds, key=lambda s: s["template_code"]):
        code = item["template_code"]
        lines.append(
            "INSERT INTO prompt_templates "
            "(template_code, template_name, category, system_prompt, user_prompt_template, "
            "description, temperature, max_tokens, status) VALUES ("
            f"{_q(code, 'code')}, {_q(item['template_name'], 'name')}, {_q(item['category'], 'cat')}, "
            f"{_q(item.get('system_prompt') or '', 'sys')}, {_q(item.get('user_prompt_template') or '', 'usr')}, "
            f"{_q(item.get('description') or '', 'desc')}, 0.7, 4096, 'active') "
            "ON CONFLICT (template_code) DO NOTHING;"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    seeds = json.loads(SEED_JSON.read_text(encoding="utf-8"))
    OUT_SQL.write_text(render_sql(seeds), encoding="utf-8")
    print(f"已生成 {OUT_SQL.name}：{len(seeds)} 条模板，{OUT_SQL.stat().st_size} 字节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
