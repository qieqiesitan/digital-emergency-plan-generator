"""surrounding_ai 高德接口：未配置 key 时返回未配置错误、不抛异常；端点单次取 key。"""

import pytest
from fastapi import HTTPException

import app.routers.surrounding_ai as sa


@pytest.fixture
def no_amap_key(monkeypatch):
    async def no_key(_config_key):
        return None

    monkeypatch.setattr(sa, "get_third_party_config", no_key)


@pytest.mark.asyncio
async def test_geocode_amap_empty_key_returns_none():
    assert await sa._geocode_amap("上海市浦东新区XX路1号", "") is None


@pytest.mark.asyncio
async def test_regeocode_amap_empty_key_returns_empty():
    assert await sa._regeocode_amap(121.5, 31.2, "") == ""


@pytest.mark.asyncio
async def test_amap_poi_search_empty_key_returns_unconfigured():
    data = await sa._amap_poi_search(121.5, 31.2, "消防站", "")
    assert data.get("status") != "1"
    assert "未配置高德 Key" in data.get("info", "")


@pytest.mark.asyncio
async def test_amap_search_endpoint_400_when_no_key(no_amap_key):
    with pytest.raises(HTTPException) as exc:
        await sa.amap_search_surrounding(
            enterprise_id="e1",
            body=sa.AmapSearchRequest(),
            current_user=_FakeUser(),
            db=None,
        )
    assert exc.value.status_code == 400


class _FakeUser:
    id = "u1"


class _FakeEnterprise:
    id = "e1"
    user_id = "u1"
    name = "测试企业"
    industry = None
    business_scope = None
    building_overview = None
    employee_count = None
    address = "上海市浦东新区XX路1号"
    hazardous_chemicals = None
    main_products = None
    surrounding_info = {}
    gis_lat = 31.2
    gis_lng = 121.5


class _FakeResult:
    def scalar_one_or_none(self):
        return _FakeEnterprise()


class _FakeDb:
    async def execute(self, stmt):
        return _FakeResult()


class _FakeAmapResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeAmapClient:
    """捕获所有高德请求的 params，验证 key 透传与单次取 key。"""

    def __init__(self):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None):
        self.calls.append({"url": url, "params": params or {}})
        if "place/around" in url:
            return _FakeAmapResponse({"status": "1", "pois": []})
        return _FakeAmapResponse({"status": "1", "regeocode": {"formatted_address": "测试地址"}})


@pytest.mark.asyncio
async def test_amap_search_endpoint_sends_key_and_fetches_once(monkeypatch):
    config_reads = []

    async def fake_config(config_key):
        config_reads.append(config_key)
        if config_key == "third_party.amap.api_key":
            return "amap-test-key"
        return None

    fake_client = _FakeAmapClient()
    monkeypatch.setattr(sa, "get_third_party_config", fake_config)
    monkeypatch.setattr(sa.httpx, "AsyncClient", lambda *a, **k: fake_client)

    resp = await sa.amap_search_surrounding(
        enterprise_id="e1",
        body=sa.AmapSearchRequest(),
        current_user=_FakeUser(),
        db=_FakeDb(),
    )

    assert resp.data.searched_address == "上海市浦东新区XX路1号"
    assert fake_client.calls, "endpoint should call Amap at least once"
    for call in fake_client.calls:
        assert call["params"]["key"] == "amap-test-key", f"params missing key: {call}"
    # 单次取 key：端点预检取一次后透传，helper 不再自行取 key
    assert config_reads == ["third_party.amap.api_key"]
