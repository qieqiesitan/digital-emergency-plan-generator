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
