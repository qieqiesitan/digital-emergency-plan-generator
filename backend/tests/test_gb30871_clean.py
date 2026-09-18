"""GB 30871 文本清洗：讹字修复与判据。"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "backend" / "app" / "regulations" / "data" / "texts" / "reg_gb_30871_2022.md"


def _load():
    """按路径加载脚本，避免把 scripts/ 变成包引入导入副作用。"""
    spec = importlib.util.spec_from_file_location(
        "clean_gb30871_text", ROOT / "scripts" / "clean_gb30871_text.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_source_text_is_cleaned():
    """判据：就地文本里"式"存在、"怯"与"聂"清零。

    计划原文此处断言"源文件仍含讹字"（用于确认清洗不是无的放矢），
    与步骤 5 的就地清洗互相矛盾——清洗完成后该断言必然失败。
    故改为断言清洗结果；「清洗确有作用」由
    test_clean_replaces_e_and_roman_numeral 覆盖。
    """
    t = SRC.read_text(encoding="utf-8")
    assert t.count("式") > 0, "清洗后应存在正确的「式」"
    assert t.count("怯") == 0, "清洗后不应残留 式→怯 讹字"
    assert t.count("聂") == 0, "清洗后不应残留 Ⅱ→聂 讹字"


def test_clean_replaces_e_and_roman_numeral():
    mod = _load()
    out = mod.clean_text("动火方怯；聂级高处作业；便携怯检测仪")
    assert "方式" in out
    assert "Ⅱ级" in out
    assert "便携式" in out
    assert "怯" not in out
    assert "聂" not in out


def test_clean_is_idempotent():
    mod = _load()
    once = mod.clean_text("样怯与方怯")
    assert mod.clean_text(once) == once


def test_clean_writes_backup_and_verifies_criteria(tmp_path):
    mod = _load()
    target = tmp_path / "std.md"
    target.write_text("动火方怯与聂级", encoding="utf-8")
    report = mod.clean_file(target, backup_dir=tmp_path / "bak")

    assert (tmp_path / "bak" / "std.md").exists(), "必须先备份原文件"
    fixed = target.read_text(encoding="utf-8")
    assert "怯" not in fixed and "聂" not in fixed
    assert report["replacements"]["怯->式"] == 1
    assert report["replacements"]["聂->Ⅱ"] == 1
