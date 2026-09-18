"""AI 调用统计：按能力/模块聚合、失败率、截断计数。"""

from unittest.mock import MagicMock

import pytest

from app.services.ai_usage_stats import (
    summarize_rows,
)


def _row(capability, success=True, tokens=100, truncated=False, duration=1000, retry=0, code=None):
    r = MagicMock()
    r.capability = capability
    r.success = success
    r.total_tokens = tokens
    r.truncated = truncated
    r.duration_ms = duration
    r.retry_count = retry
    r.error_code = code
    return r


def test_summarize_counts_and_tokens():
    rows = [
        _row("hazard_grade", tokens=100),
        _row("hazard_grade", tokens=200),
        _row("risk_suggest_measures", tokens=50),
    ]
    out = summarize_rows(rows)
    assert out["total_calls"] == 3
    assert out["total_tokens"] == 350
    by_cap = {c["capability"]: c for c in out["by_capability"]}
    assert by_cap["hazard_grade"]["calls"] == 2
    assert by_cap["hazard_grade"]["tokens"] == 300


def test_summarize_computes_failure_rate():
    rows = [
        _row("a", success=True),
        _row("a", success=False, code=429),
        _row("a", success=True),
        _row("a", success=True),
    ]
    out = summarize_rows(rows)
    by_cap = {c["capability"]: c for c in out["by_capability"]}
    assert by_cap["a"]["failures"] == 1
    assert by_cap["a"]["failure_rate"] == pytest.approx(0.25)


def test_summarize_flags_truncated_calls():
    """被截断的调用单独计数——它 success 可能是 True，但结果是半截的。"""
    rows = [_row("a", success=True, truncated=True), _row("a")]
    out = summarize_rows(rows)
    by_cap = {c["capability"]: c for c in out["by_capability"]}
    assert by_cap["a"]["truncated"] == 1
    assert out["total_truncated"] == 1


def test_summarize_averages_duration():
    rows = [_row("a", duration=1000), _row("a", duration=3000)]
    out = summarize_rows(rows)
    by_cap = {c["capability"]: c for c in out["by_capability"]}
    assert by_cap["a"]["avg_duration_ms"] == 2000


def test_summarize_handles_null_tokens():
    """有些供应商不回 token 数，不能因此报错或算成 0 而失真。"""
    rows = [_row("a", tokens=None), _row("a", tokens=100)]
    out = summarize_rows(rows)
    assert out["total_tokens"] == 100


def test_summarize_empty_rows():
    out = summarize_rows([])
    assert out["total_calls"] == 0
    assert out["by_capability"] == []


def test_summarize_ignores_rows_without_capability():
    """capability 为空的行归到 unknown，不丢弃——丢了会让总量对不上。"""
    rows = [_row(None), _row("a")]
    out = summarize_rows(rows)
    caps = {c["capability"] for c in out["by_capability"]}
    assert "unknown" in caps
    assert out["total_calls"] == 2
