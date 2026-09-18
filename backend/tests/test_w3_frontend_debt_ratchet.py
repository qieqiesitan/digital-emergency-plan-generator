"""W3 前端债务棘轮（2026-09-18 B1 批次后升级为"零容忍"）。

背景：26 个 @ts-nocheck 与 245 条 eslint error 曾是历史遗留，W3 先以"只减不增"兜底；
B1 批次（7 个 commit）把债务全部清零——eslint 0 error / 0 warning、@ts-nocheck 0 个、
explicit any 0 处。因此上限一并收紧到 0：任何新增债务都会让 CI
（backend 本测试 + frontend node scripts/eslint-ratchet.mjs）失败。
"""

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "frontend"

TS_NOCHECK_LIMIT = 0
ESLINT_ERROR_LIMIT = 0
ESLINT_WARNING_LIMIT = 0


def test_eslint_baseline_is_recorded_and_capped():
    baseline = json.loads((FRONTEND / "eslint-baseline.json").read_text(encoding="utf-8"))
    assert baseline["recordedAt"]
    assert baseline["errors"] <= ESLINT_ERROR_LIMIT, (
        f"eslint 错误数超过钉住的上限 {ESLINT_ERROR_LIMIT}，请先修掉新增债务"
    )
    assert baseline["warnings"] <= ESLINT_WARNING_LIMIT, (
        f"eslint 警告数超过钉住的上限 {ESLINT_WARNING_LIMIT}，请先修掉新增债务"
    )
    # 零债务时 byRule 允许为空；一旦有债务必须逐条登记，便于定位新增来源
    assert baseline["errors"] == 0 or baseline["byRule"], "有债务时必须按规则记录"
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


def test_frontend_sources_have_no_bom():
    """前后端源码都不得带 UTF-8 BOM（历史上 BOM 让补丁/脚本工具链异常过）。"""
    checker = FRONTEND / "scripts" / "check-source-hygiene.mjs"
    assert checker.exists(), "缺少源码卫生检查脚本"
    bases = (
        FRONTEND / "src",
        REPO / "backend" / "app",
        REPO / "backend" / "tests",
        REPO / "backend" / "scripts",
    )
    suffixes = {".ts", ".tsx", ".css", ".py"}
    offenders = [
        str(p.relative_to(REPO))
        for base in bases
        for p in base.rglob("*")
        if p.is_file() and p.suffix in suffixes and p.read_bytes()[:3] == b"\xef\xbb\xbf"
    ]
    assert not offenders, "以下文件带 UTF-8 BOM：" + ", ".join(offenders)
