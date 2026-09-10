"""化学品库字段富集：解析器 / 合并 / 幂等 SQL 单测（离线夹具，不联网）。"""
from pathlib import Path

import pytest

from backend.tools.chemical_enrichment.pubchem import map_physical_state, parse_pug_view
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


def test_fetcher_decodes_utf8_bytes(tmp_path):
    """requests 可能猜错编码（resp.text 乱码），缓存必须按 UTF-8 解码字节。"""

    class _FakeResponse:
        status_code = 200
        content = "危害分类".encode("utf-8")
        text = "å±å®³åç±»"  # 模拟 requests 猜成 latin-1

    fetcher = CachedFetcher(cache_dir=tmp_path, delay=0.0, get=lambda url: _FakeResponse())
    assert fetcher.text("https://example.com/zh") == "危害分类"


def test_pubchem_density_requires_unit():
    def record(value):
        return {"Record": {"Section": [{"TOCHeading": "Density", "Information": [
            {"Value": {"StringWithMarkup": [{"String": value}]}}]}]}}

    assert parse_pug_view(record("0.7914 g/cm3 (NTP, 1992)"))["density"] == "0.7914 g/cm3"
    assert parse_pug_view(
        record("0.557 at 68 °F (USCG, 1999) - Less dense than water; will float"))["density"] == ""


def test_pubchem_flash_point_strips_citation_and_prose():
    def record(value):
        return {"Record": {"Section": [{"TOCHeading": "Flash Point", "Information": [
            {"Value": {"StringWithMarkup": [{"String": value}]}}]}]}}

    assert parse_pug_view(record("-117 °F (USCG, 1999)"))["flash_point"] == "-117 °F"
    assert parse_pug_view(
        record("12 °C closed cup - highly flammable (NTP, 1992)"))["flash_point"] == "12 °C"


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


def test_pubchem_extracts_un_state_and_limits():
    import json

    record = json.loads((FIXTURES / "pubchem_887.json").read_text(encoding="utf-8"))
    data = parse_pug_view(record)
    assert data["un_no"] == "1230"
    assert data["physical_state"] == "液态"
    assert data["explosion_limit"] == "6%~36.5%"


def test_pubchem_state_mapping_rules():
    assert map_physical_state("A colorless gas with a pungent odor") == "气态"
    assert map_physical_state("White crystalline solid") == "固态"
    assert map_physical_state("Oily liquid") == "液态"
    assert map_physical_state("") == ""


def test_merge_conflicting_un_is_left_blank():
    from backend.tools.chemical_enrichment.merge import merge_sources

    chemblink = {"un_no": "1164", "flash_point": "-36℃"}
    pubchem = {"un_no": "2384", "flash_point": "-37.8 ℃", "physical_state": "液态",
               "explosion_limit": "6%~36.5%", "ignition_temp": "", "boiling_point": "37 ℃",
               "density": ""}
    merged = merge_sources(chemblink, pubchem)
    assert merged["un_no"] == ""
    assert merged["flash_point"] == "-36℃"
    assert merged["physical_state"] == "液态"
    assert merged["explosion_limit"] == "6%~36.5%"
    assert merged["boiling_point"] == "37 ℃"
    assert "un_no" in merged["conflicts"]


def test_merge_does_not_overwrite_existing_values():
    from backend.tools.chemical_enrichment.merge import FIELDS, merge_sources

    merged = merge_sources({"flash_point": "12℃"}, {"physical_state": "液态"},
                           existing={"flash_point": "管理员手改值"})
    assert merged["flash_point"] == "管理员手改值"
    assert merged["physical_state"] == "液态"
    assert set(merged) >= set(FIELDS) | {"conflicts"}


def test_merge_handles_unit_difference_instead_of_false_conflict():
    from backend.tools.chemical_enrichment.merge import merge_sources

    merged = merge_sources({"flash_point": "12℃"}, {"flash_point": "53.6 °F"})
    assert merged["flash_point"] == "12℃"
    assert merged["conflicts"] == []


def test_merge_real_numeric_conflict_is_left_blank():
    from backend.tools.chemical_enrichment.merge import merge_sources

    merged = merge_sources({"flash_point": "12℃"}, {"flash_point": "40 ℃"})
    assert merged["flash_point"] == ""
    assert merged["conflicts"] == ["flash_point"]


def test_merge_text_fields_never_conflict():
    from backend.tools.chemical_enrichment.merge import merge_sources

    merged = merge_sources({"health_hazard": "急性毒性 类别3"}, {"health_hazard": "类别4"})
    assert merged["health_hazard"] == "急性毒性 类别3"
    assert merged["conflicts"] == []


def test_collect_record_tolerates_single_source_failure(tmp_path):
    from backend.tools.chemical_enrichment.fetch import CachedFetcher
    from backend.tools.enrich_chemical_library import collect_record

    html = (FIXTURES / "chemblink_75-18-3.html").read_text(encoding="utf-8")

    class _Response:
        pass

    def fake_get(url):
        response = _Response()
        if "pubchem" in url:
            response.status_code = 404
            response.text = ""
            response.content = b""
        else:
            response.status_code = 200
            response.content = html.encode("utf-8")
            response.text = html
        return response

    fetcher = CachedFetcher(cache_dir=tmp_path, delay=0.0, get=fake_get)
    chemblink, pubchem, errors = collect_record(fetcher, "75-18-3")
    assert chemblink["flash_point"] == "-36℃"
    assert pubchem == {}
    assert any("pubchem" in error for error in errors)


def test_process_rows_preserves_input_order_with_workers():
    import time

    from backend.tools.enrich_chemical_library import process_rows

    rows = [["id-1", "甲", "1-1-1"], ["id-2", "乙", "2-2-2"],
            ["id-3", "丙", "3-3-3"], ["id-4", "丁", "4-4-4"]]

    def fake_collect(cas):
        if cas == "2-2-2":
            time.sleep(0.05)  # 让慢的排在中间，验证结果仍按输入顺序
        if cas == "4-4-4":
            return {}, {}, ["pubchem: HTTP 404"]
        return {"flash_point": f"{cas}℃"}, {}, []

    results, failed, partial, conflicts = process_rows(rows, fake_collect, workers=4)
    assert [r["id"] for r in results] == ["id-1", "id-2", "id-3"]
    assert results[1]["values"]["flash_point"] == "2-2-2℃"
    assert [f["id"] for f in failed] == ["id-4"]
    assert failed[0]["error"] == "pubchem: HTTP 404"


def test_parse_rows_payload_handles_newline_in_cas():
    from backend.tools.enrich_chemical_library import parse_rows_payload

    payload = ('[{"id": "a-1", "name": "焦磷酸", "cas": "77287-29-7"}, '
               '{"id": "a-2", "name": "多硫化铵", "cas": "7632-04-4\\n12259-92-6"}]')
    rows = parse_rows_payload(payload)
    assert rows == [["a-1", "焦磷酸", "77287-29-7"],
                    ["a-2", "多硫化铵", "7632-04-4\n12259-92-6"]]


def test_sql_uses_coalesce_nullif_and_only_present_fields():
    from backend.tools.chemical_enrichment.sqlgen import render_update_sql

    row = {"id": "11111111-1111-1111-1111-111111111111",
           "values": {"un_no": "1230", "flash_point": "12℃", "boiling_point": ""}}
    sql = render_update_sql([row])
    assert "COALESCE(NULLIF(un_no,''), '1230')" in sql
    assert "flash_point" in sql
    assert "boiling_point" not in sql
    assert sql.strip().endswith(";")


def test_sql_skips_rows_without_any_value():
    from backend.tools.chemical_enrichment.sqlgen import render_update_sql

    row = {"id": "22222222-2222-2222-2222-222222222222",
           "values": {"un_no": "", "flash_point": "  "}}
    assert render_update_sql([row]).strip() == ""


def test_sql_escapes_single_quotes():
    from backend.tools.chemical_enrichment.sqlgen import render_update_sql

    row = {"id": "33333333-3333-3333-3333-333333333333",
           "values": {"health_hazard": "眼刺激；3,3'-二甲基"}}
    assert "3,3''-二甲基" in render_update_sql([row])
