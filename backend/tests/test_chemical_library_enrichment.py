"""化学品库字段富集：解析器 / 合并 / 幂等 SQL 单测（离线夹具，不联网）。"""
from pathlib import Path

import pytest

from backend.tools.chemical_enrichment.fetch import CachedFetcher
from backend.tools.chemical_enrichment.chemblink import parse_product_page

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


def test_chemblink_prefers_experimental_value():
    html = (FIXTURES / "chemblink_75-18-3.html").read_text(encoding="utf-8")
    data = parse_product_page(html)
    assert data["flash_point"] == "-36℃"
    assert data["boiling_point"] == "38℃"
    assert data["density"] == "0.846 g/mL"


def test_chemblink_plain_value_and_un():
    html = (FIXTURES / "chemblink_2050-92-2.html").read_text(encoding="utf-8")
    data = parse_product_page(html)
    assert data["flash_point"] == "52℃"
    assert data["boiling_point"] == "202-203℃"
    assert data["un_no"] == "2841"
    assert data["density"] == ""  # 裸数值无单位 → 按不可溯源留空


def test_chemblink_ghs_split_into_health_and_fire():
    html = (FIXTURES / "chemblink_75-18-3.html").read_text(encoding="utf-8")
    data = parse_product_page(html)
    assert "易燃液体 类别2" in data["fire_hazard"]
    assert "急性毒性 类别3" in data["health_hazard"]
    assert data["un_no"] == "1164"
