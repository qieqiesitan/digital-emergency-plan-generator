"""化学品库字段富集：解析器 / 合并 / 幂等 SQL 单测（离线夹具，不联网）。"""
from pathlib import Path

import pytest

from backend.tools.chemical_enrichment.fetch import CachedFetcher

FIXTURES = Path(__file__).parent / "fixtures" / "chemical_enrichment"


class _FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


def test_fetcher_caches_response(tmp_path):
    calls = []

    def fake_get(url):
        calls.append(url)
        return _FakeResponse(200, "hello")

    fetcher = CachedFetcher(cache_dir=tmp_path, delay=0.0, get=fake_get)
    assert fetcher.text("https://example.com/a") == "hello"
    assert fetcher.text("https://example.com/a") == "hello"
    assert len(calls) == 1  # 第二次命中缓存
    assert fetcher.text("https://example.com/a", refresh=True) == "hello"
    assert len(calls) == 2


def test_fetcher_retries_then_raises(tmp_path):
    calls = []

    def fake_get(url):
        calls.append(url)
        return _FakeResponse(503, "")

    fetcher = CachedFetcher(cache_dir=tmp_path, delay=0.0, retries=3, get=fake_get)
    with pytest.raises(RuntimeError):
        fetcher.text("https://example.com/flaky")
    assert len(calls) == 3
