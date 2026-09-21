"""条件键工具 + 条件生成器的锚定规则。"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _loader():
    from app.services.work_ticket_condition_loader import measure_ref, normalize_measure_text

    return normalize_measure_text, measure_ref


def _generator():
    spec = importlib.util.spec_from_file_location(
        "wt_cond_gen", ROOT / "backend" / "seed_work_ticket_conditions.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_normalize_strips_whitespace_and_converts_fullwidth():
    normalize, _ = _loader()
    assert normalize("动火点 30m 内　垂直空间") == normalize("动火点30m内垂直空间")
    assert normalize("（试行）") == normalize("(试行)")


def test_normalize_is_stable_for_trailing_punctuation():
    normalize, _ = _loader()
    assert normalize("措施一；") == normalize("措施一")


def test_measure_ref_is_deterministic_and_short():
    _, ref = _loader()
    a = ref("与动火设备相连接的所有管线已断开")
    assert a == ref(" 与动火设备相连接的所有管线已断开 ")
    assert len(a) == 32
    assert a != ref("与动火设备相连接的所有管线已断开，加盲板")


def test_generator_covers_eight_types_and_matches_spec_count():
    mod = _generator()
    sql, report = mod.build_sql()
    # 66 = 建立了映射的措施条数；70 = 条件键总行数（4 条措施各依赖两个条件）
    assert report["mapped_measures"] == 66, report["measures_by_ticket"]
    assert report["mapped_conditions"] == 70, report["by_ticket"]
    assert set(report["by_ticket"]) == {
        "DHZY", "YXKJ", "MBCD", "GCZY", "QZDZ", "LSYD", "PTZY", "DLZY",
    }
    assert report["unmapped_total"] == 40, report["unmapped_total"]
    assert "work_ticket_measure_conditions" in sql
    assert "work_ticket_scenarios" in sql


def test_generator_missing_yaml_text_raises(monkeypatch):
    """YAML 里的措施正文在标准文本中找不到 → 必须报错中止，不能静默丢弃。"""
    mod = _generator()
    monkeypatch.setattr(
        mod,
        "_load_yaml",
        lambda: {
            "conditions": {"dummy": {"label": "假条件", "auto": None}},
            "tickets": {
                "DHZY": {
                    "scenario": ["dummy"],
                    "measures": [
                        {"text": "这条措施在标准文本里根本不存在", "conditions": ["dummy"]}
                    ],
                }
            },
        },
    )
    with pytest.raises(RuntimeError, match="失配"):
        mod.build_sql()


def test_generator_reports_unmapped_measures():
    """标准文本里有、YAML 未映射的措施必须进入未映射清单。"""
    mod = _generator()
    _, report = mod.build_sql()
    assert len(report["unmapped"]) > 0
    assert all(
        {"ticket_type", "sort_order", "text"} <= set(item) for item in report["unmapped"]
    )


def test_generator_anchor_survives_reordering():
    """锚定稳定性：措施顺序打乱后，映射仍指向同一正文。"""
    mod = _generator()
    sql_a, _ = mod.build_sql()
    shuffled = mod._parse_all_measures(shuffle_seed=7)
    sql_b, _ = mod.build_sql(measures_override=shuffled)
    refs_a = sorted(
        line.split("'")[5]
        for line in sql_a.splitlines()
        if line.startswith("INSERT INTO work_ticket_measure_conditions ")
    )
    refs_b = sorted(
        line.split("'")[5]
        for line in sql_b.splitlines()
        if line.startswith("INSERT INTO work_ticket_measure_conditions ")
    )
    assert refs_a == refs_b
    assert len(refs_a) == 70
    assert all(len(ref) == 32 for ref in refs_a)


def test_generator_marks_manual_and_auto_scenario_rows():
    """情景表同时存人工项与自动项：人工项 auto_rule 为 NULL，自动项非空。"""
    mod = _generator()
    sql, _ = mod.build_sql()
    scenario_lines = [
        line for line in sql.splitlines() if "INTO work_ticket_scenarios " in line
    ]
    assert scenario_lines, "未生成情景项"
    # 动火票的自动项（气焊/电焊）必须写入且带 auto_rule，否则判定原因里只剩键名
    gas_line = next(line for line in scenario_lines if "'gas_welding'" in line)
    assert "'fire_method_gas'" in gas_line, gas_line
    # 人工项（如 in_tank_area）必须是 NULL
    manual_line = next(line for line in scenario_lines if "'in_tank_area'" in line)
    assert ", NULL," in manual_line, manual_line
