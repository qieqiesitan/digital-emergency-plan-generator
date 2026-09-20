"""8 类作业票种子完整性。"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "wt_seed", ROOT / "backend" / "app" / "services" / "work_ticket_seed_data.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_all_eight_types_present():
    mod = _load()
    codes = {t["code"] for t in mod.TEMPLATES}
    assert codes == {"DHZY", "YXKJ", "MBCD", "GCZY", "QZDZ", "LSYD", "PTZY", "DLZY"}


def test_graded_types_have_expected_levels():
    mod = _load()
    by_code: dict[str, set] = {}
    for t in mod.TEMPLATES:
        by_code.setdefault(t["code"], set()).add(t["level"])
    assert by_code["DHZY"] == {"特级", "一级", "二级"}
    assert by_code["GCZY"] == {"Ⅰ级", "Ⅱ级", "Ⅲ级", "Ⅳ级"}
    assert by_code["QZDZ"] == {"一级", "二级", "三级"}
    for code in ("YXKJ", "MBCD", "LSYD", "PTZY", "DLZY"):
        assert by_code[code] == {None}, f"{code} 不应分级"


def test_every_template_has_fields_and_chapter():
    mod = _load()
    for t in mod.TEMPLATES:
        assert t["fields"], f"{t['name']} 缺票面字段"
        assert isinstance(t["chapter"], int) and 5 <= t["chapter"] <= 12, t["name"]
        keys = [f["field_key"] for f in t["fields"]]
        assert len(keys) == len(set(keys)), f"{t['name']} 字段 key 重复"


def test_approval_matrix_covers_all_standard_rows():
    """表B.1 的每一行都要有对应配置。"""
    mod = _load()
    m = {(r["code"], r["level"]) for r in mod.APPROVAL_MATRIX}
    expected = {
        ("DHZY", "特级"), ("DHZY", "一级"), ("DHZY", "二级"),
        ("YXKJ", None), ("MBCD", None),
        ("GCZY", "Ⅰ级"), ("GCZY", "Ⅱ级"), ("GCZY", "Ⅲ级"), ("GCZY", "Ⅳ级"),
        ("QZDZ", "一级"), ("QZDZ", "二级"), ("QZDZ", "三级"),
        ("LSYD", None), ("PTZY", None), ("DLZY", None),
    }
    assert expected <= m, f"缺少审批行：{expected - m}"


def test_countersign_rows_present():
    """临时用电与动土/断路的会签单位不能漏。"""
    mod = _load()
    countersign = {r["code"]: r for r in mod.APPROVAL_MATRIX if r.get("countersign")}
    assert "配送电单位" in countersign["LSYD"]["countersign"]
    assert len(countersign["PTZY"]["countersign"]) >= 5, "动土应涉及多单位会签"
    assert countersign["DLZY"]["countersign"], "断路应有涉及单位会签"


def test_gas_test_required_only_for_two_types():
    """只有动火与受限空间强制气体检测。"""
    mod = _load()
    required = {t["code"] for t in mod.TEMPLATES if t.get("requires_gas_test")}
    assert required == {"DHZY", "YXKJ"}


def test_measure_parsing_is_scoped_to_appendix_tables():
    """每类措施应来自各自的附录A 表，不能所有类型共用同一批措施。"""
    mod = _load()
    text = (
        ROOT / "backend/app/regulations/data/texts/reg_gb_30871_2022.md"
    ).read_text(encoding="utf-8")
    counts = {
        chapter: len(mod.parse_measures(text, chapter=chapter))
        for chapter in range(5, 13)
    }
    assert all(count > 0 for count in counts.values()), counts
    assert len(set(counts.values())) >= 3, counts
    assert counts[5] != counts[12], counts


def _build_sql() -> str:
    """调用生成器的纯函数入口，拿 SQL 文本而不写文件。"""
    spec = importlib.util.spec_from_file_location(
        "wt_seed_gen", ROOT / "backend" / "seed_work_ticket_templates.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build_sql()


def test_measure_cleanup_statement_emitted_per_template():
    """每个模板的措施 INSERT 之前必须有清理语句。

    背景（2026-09-20 真库发现）：v1 种子把附录A 全部 106 条措施写给了动火与
    受限空间的 4 个模板；v2 用确定性 UUID5 + ON CONFLICT DO NOTHING 修正了
    同 ID 行的文本，但多出的行无人删除。若生成器只 INSERT 不清理，
    任何一次「修复后重放」都无法自愈，故把清理语句锁进测试。
    """
    lines = _build_sql().splitlines()
    insert_templates = {
        ln.split("'")[3]
        for ln in lines
        if ln.startswith("INSERT INTO work_ticket_template_measures ")
    }
    delete_templates = {
        ln.split("'")[1]
        for ln in lines
        if ln.startswith("DELETE FROM work_ticket_template_measures ")
    }
    assert insert_templates, "未生成任何措施 INSERT"
    assert insert_templates == delete_templates, (
        f"清理语句与模板集合不一致：缺 {insert_templates - delete_templates}"
    )


def test_measure_counts_per_template_match_appendix_tables():
    """生成产物的措施总数必须等于各章节附录表条数之和（回归锁）。"""
    mod = _load()
    expected_by_chapter = {5: 16, 6: 15, 7: 11, 8: 15, 9: 20, 10: 14, 11: 11, 12: 4}
    actual = sum(
        1
        for ln in _build_sql().splitlines()
        if ln.startswith("INSERT INTO work_ticket_template_measures ")
    )
    expected = sum(expected_by_chapter[t["chapter"]] for t in mod.TEMPLATES)
    assert actual == expected == 223, f"措施总数不符：actual={actual} expected={expected}"
