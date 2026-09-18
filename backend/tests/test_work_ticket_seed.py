"""作业票种子：常量表结构与措施解析。"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_seed_data_covers_two_types_with_levels():
    mod = _load("wt_seed", "backend/app/services/work_ticket_seed_data.py")
    codes = {t["code"] for t in mod.TEMPLATES}
    assert codes == {"DHZY", "YXKJ"}, "计划 8 只做动火与受限空间"
    dhzy_levels = {t["level"] for t in mod.TEMPLATES if t["code"] == "DHZY"}
    assert dhzy_levels == {"特级", "一级", "二级"}, "动火票按等级分三种模板"


def test_every_field_has_group_and_key():
    mod = _load("wt_seed", "backend/app/services/work_ticket_seed_data.py")
    for tpl in mod.TEMPLATES:
        assert tpl["fields"], f"{tpl['name']} 没有票面字段"
        for f in tpl["fields"]:
            assert f["field_key"] and f["label"] and f["group_name"]


def test_approval_matrix_matches_standard_table_b1():
    """审批矩阵必须与 GB 30871 附录B 表B.1 一致。"""
    mod = _load("wt_seed", "backend/app/services/work_ticket_seed_data.py")
    m = {(r["code"], r["level"]): r["approver"] for r in mod.APPROVAL_MATRIX}
    assert m[("DHZY", "特级")] == "主管领导"
    assert m[("DHZY", "一级")] == "安全管理部门"
    assert m[("DHZY", "二级")] == "所在基层单位"
    assert m[("YXKJ", None)] == "所在基层单位"


def test_parse_measures_from_appendix_a():
    mod = _load("wt_seed", "backend/app/services/work_ticket_seed_data.py")
    text = (ROOT / "backend/app/regulations/data/texts/reg_gb_30871_2022.md").read_text(
        encoding="utf-8"
    )
    measures = mod.parse_measures(text, chapter=5)
    assert len(measures) >= 10, f"动火作业措施应不少于 10 条，实际 {len(measures)}"
    for m in measures:
        assert m["measure_text"] and m["article_anchor"].startswith("GB 30871-2022")


def test_parse_measures_rejects_empty_text():
    mod = _load("wt_seed", "backend/app/services/work_ticket_seed_data.py")
    assert mod.parse_measures("", chapter=5) == []


def test_build_sql_is_deterministic():
    mod = _load("wt_seed_gen", "backend/seed_work_ticket_templates.py")
    a = mod.build_sql()
    b = mod.build_sql()
    assert a == b, "两次生成必须逐字节一致"
    assert "ON CONFLICT (id) DO NOTHING" in a
