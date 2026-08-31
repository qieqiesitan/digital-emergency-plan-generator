"""surrounding_ai 高德接口：未配置 key 时返回未配置错误、不抛异常。"""

import pytest

import app.routers.surrounding_ai as sa


@pytest.fixture
def no_amap_key(monkeypatch):
    async def no_key(_config_key):
        return None

    monkeypatch.setattr(sa, "get_third_party_config", no_key)


@pytest.mark.asyncio
async def test_geocode_amap_no_key_returns_none(no_amap_key):
    assert await sa._geocode_amap("上海市浦东新区XX路1号") is None


@pytest.mark.asyncio
async def test_regeocode_amap_no_key_returns_empty(no_amap_key):
    assert await sa._regeocode_amap(121.5, 31.2) == ""


@pytest.mark.asyncio
async def test_amap_poi_search_no_key_returns_unconfigured(no_amap_key):
    data = await sa._amap_poi_search(121.5, 31.2, "消防站")
    assert data.get("status") != "1"
    assert "未配置高德 Key" in data.get("info", "")
