"""W3 前端债务棘轮：@ts-nocheck 与 eslint 基线"只减不增"。

26 个 @ts-nocheck 文件与 245 条 eslint error 是历史遗留（补类型需要大工程），
本测试保证它们不会被悄悄扩大：新代码若加债，CI（node scripts/eslint-ratchet.mjs）
与这里的上限都会失败。
"""

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "frontend"

TS_NOCHECK_LIMIT = 26
ESLINT_ERROR_LIMIT = 245


def test_eslint_baseline_is_recorded_and_capped():
    baseline = json.loads((FRONTEND / "eslint-baseline.json").read_text(encoding="utf-8"))
    assert baseline["byRule"], "基线必须按规则记录，便于定位新增债务"
    assert baseline["recordedAt"]
    assert baseline["errors"] <= ESLINT_ERROR_LIMIT, (
        f"eslint 错误数超过钉住的上限 {ESLINT_ERROR_LIMIT}，请先修掉新增债务"
    )
    assert (FRONTEND / "scripts" / "eslint-ratchet.mjs").exists(), "棘轮脚本缺失"
    pkg = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    assert "lint:ratchet" in pkg["scripts"], "package.json 未接棘轮命令"


def test_ts_nocheck_files_do_not_grow():
    files = sorted(
        p for p in (FRONTEND / "src").rglob("*.ts*")
        if p.suffix in (".ts", ".tsx") and "@ts-nocheck" in p.read_text(encoding="utf-8")
    )
    assert len(files) <= TS_NOCHECK_LIMIT, (
        "新增了 @ts-nocheck：" + ", ".join(str(p.relative_to(REPO)) for p in files)
    )
