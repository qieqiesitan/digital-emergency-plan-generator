"""隐患排查治理任务 5 测试：扫码公开上报（免登录，token + nonce 防重）。

测试风格与 tests/test_hazard_plan_api.py 一致：无 db fixture，端点用
FastAPI TestClient + dependency_overrides + SQL 文本分发 mock。

覆盖：
- 风险点 token 上报（object_id 自动带，enterprise 由风险点归属推导）
- 企业通用 token 上报（location 必填取舍：无风险点关联时 location 422）
- token 无效 404「链接已失效」
- nonce 缺失 422 / 重复提交 409 / TTL 过期后允许再次提交
- 落库 source_type=report、created_by=NULL、status=registered、code=HD-{序号}
- 响应不暴露内部信息（仅「已提交，待企业管理员确认」）
"""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.models.enterprise import Enterprise
from app.models.hazard_management import HazardRecord
from app.models.risk_management import RiskObject
from app.routers import public_hazard


# ── mock 工具 ──

def _scalar(value):
    res = MagicMock()
    res.scalar_one_or_none.return_value = value
    return res


def _count(value):
    res = MagicMock()
    res.scalar.return_value = value
    return res


def _ent(**kw):
    e = Enterprise(id="e1", user_id="u1", name="甲公司", hazard_closure_mode="standard")
    for k, v in kw.items():
        setattr(e, k, v)
    return e


def _obj(**kw):
    o = RiskObject(id="o1", enterprise_id="e1", name="配电室", public_token="obj-token-1")
    for k, v in kw.items():
        setattr(o, k, v)
    return o


def _public_db(ent=None, obj=None, record_count=0):
    """按 SQL 文本特征分发：risk_objects / enterprises / hazard_records。"""
    db = AsyncMock()
    db.added = []

    def fake_add(record):
        if isinstance(record, HazardRecord) and not getattr(record, "id", None):
            record.id = "r1"
        db.added.append(record)

    db.add = MagicMock(side_effect=fake_add)

    def fake_execute(stmt, *params):
        text = str(stmt)
        if "FROM risk_objects" in text:
            return _scalar(obj)
        if "FROM enterprises" in text:
            return _scalar(ent)
        if "FROM hazard_records" in text:
            return _count(record_count)
        return _scalar(None)

    db.execute.side_effect = fake_execute
    return db


@pytest.fixture()
def client():
    # 每个用例前清空 nonce 缓存，避免跨用例污染
    public_hazard._nonce_cache.clear()
    app = FastAPI()
    app.include_router(public_hazard.router)
    app.dependency_overrides[get_db] = lambda: _public_db()
    with TestClient(app) as test_client:
        yield test_client


_BODY = {
    "description": "配电箱门破损，存在触电风险",
    "photo_urls": ["/uploads/x.jpg"],
    "location": "3 号车间东侧",
    "nonce": "nonce-001",
}


# ── 风险点 token 上报 ──

def test_public_report_risk_object_token(client):
    ent = _ent()
    obj = _obj(public_token="obj-token-1")
    db = _public_db(ent=ent, obj=obj, record_count=0)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/public/hazard/report/obj-token-1", json=_BODY)
    assert resp.status_code == 200
    assert resp.json()["code"] == 0
    data = resp.json()["data"]
    # 响应不暴露内部信息（§8「已提交，待企业管理员确认」风格）
    assert data == {"message": "已提交，待企业管理员确认"}
    assert "id" not in data and "code" not in data and "enterprise_id" not in data
    record = db.added[0]
    assert isinstance(record, HazardRecord)
    assert record.enterprise_id == "e1"
    assert record.code == "HD-001"
    assert record.source_type == "report"
    assert record.created_by is None
    assert record.status == "registered"
    assert record.object_id == "o1"  # 风险点 token 自动带 object_id
    assert record.title == "配电箱门破损，存在触电风险"
    assert record.photo_urls == ["/uploads/x.jpg"]
    assert record.location == "3 号车间东侧"  # 风险点 token：location 可选
    db.commit.assert_awaited()


def test_public_report_risk_object_token_location_optional(client):
    ent = _ent()
    obj = _obj()
    db = _public_db(ent=ent, obj=obj)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {k: v for k, v in _BODY.items() if k != "location"}
    resp = client.post("/public/hazard/report/obj-token-1", json=body)
    assert resp.status_code == 200
    assert db.added[0].location is None


# ── 企业通用 token 上报（location 必填取舍） ──

def test_public_report_enterprise_token_requires_location(client):
    ent = _ent(hazard_report_token="ent-token-1")
    db = _public_db(ent=ent, obj=None)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {k: v for k, v in _BODY.items() if k != "location"}
    resp = client.post("/public/hazard/report/ent-token-1", json=body)
    assert resp.status_code == 422
    assert "location 必填" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_public_report_enterprise_token_with_location_ok(client):
    ent = _ent(hazard_report_token="ent-token-1")
    db = _public_db(ent=ent, obj=None, record_count=3)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_BODY, "nonce": "nonce-ent-1", "title": "车间通道堆放易燃物"}
    resp = client.post("/public/hazard/report/ent-token-1", json=body)
    assert resp.status_code == 200
    assert resp.json()["message"] == "已提交，待企业管理员确认"
    record = db.added[0]
    assert record.code == "HD-004"
    assert record.source_type == "report"
    assert record.created_by is None
    assert record.object_id is None  # 企业通用 token 无自动关联
    assert record.location == "3 号车间东侧"
    assert record.title == "车间通道堆放易燃物"
    db.commit.assert_awaited()


# ── token 404 / 字段校验 ──

def test_public_report_invalid_token_404(client):
    db = _public_db(ent=None, obj=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/public/hazard/report/bad-token", json=_BODY)
    assert resp.status_code == 404
    assert "链接已失效" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_public_report_missing_nonce_422(client):
    ent = _ent(hazard_report_token="ent-token-1")
    db = _public_db(ent=ent, obj=None)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {k: v for k, v in _BODY.items() if k != "nonce"}
    resp = client.post("/public/hazard/report/ent-token-1", json=body)
    assert resp.status_code == 422  # pydantic nonce 必填
    db.commit.assert_not_awaited()


def test_public_report_blank_description_422(client):
    ent = _ent(hazard_report_token="ent-token-1")
    db = _public_db(ent=ent, obj=None)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_BODY, "description": "   "}
    resp = client.post("/public/hazard/report/ent-token-1", json=body)
    assert resp.status_code == 422
    assert "description 不能为空" in resp.json()["detail"]
    db.commit.assert_not_awaited()


# ── nonce 防重 ──

def test_public_report_duplicate_nonce_409(client):
    ent = _ent(hazard_report_token="ent-token-1")
    db = _public_db(ent=ent, obj=None)
    client.app.dependency_overrides[get_db] = lambda: db
    first = client.post("/public/hazard/report/ent-token-1", json=_BODY)
    assert first.status_code == 200
    second = client.post("/public/hazard/report/ent-token-1", json=_BODY)
    assert second.status_code == 409
    assert "请勿重复提交" in second.json()["detail"]
    assert len(db.added) == 1  # 仅第一次落库


def test_public_report_nonce_expired_allows_resubmit(client):
    """nonce TTL 过期后惰性清理，允许再次提交（5 分钟防重窗口）。"""
    ent = _ent(hazard_report_token="ent-token-1")
    db = _public_db(ent=ent, obj=None)
    client.app.dependency_overrides[get_db] = lambda: db
    first = client.post("/public/hazard/report/ent-token-1", json=_BODY)
    assert first.status_code == 200
    # 把防重窗口时间拨到 TTL 之前，模拟 5 分钟过期
    key = f"hazard_report:{_BODY['nonce']}"
    assert key in public_hazard._nonce_cache
    public_hazard._nonce_cache[key] = time.monotonic() - public_hazard.NONCE_TTL_SECONDS - 1
    second = client.post("/public/hazard/report/ent-token-1", json=_BODY)
    assert second.status_code == 200
    assert len(db.added) == 2


# ── title 默认值 ──

def test_public_report_default_title_from_description(client):
    ent = _ent(hazard_report_token="ent-token-1")
    db = _public_db(ent=ent, obj=None)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {k: v for k, v in _BODY.items() if k != "title"}
    resp = client.post("/public/hazard/report/ent-token-1", json=body)
    assert resp.status_code == 200
    assert db.added[0].title == _BODY["description"]


def test_public_report_default_title_truncated_to_255(client):
    ent = _ent(hazard_report_token="ent-token-1")
    db = _public_db(ent=ent, obj=None)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_BODY, "description": "长" * 400, "title": "   "}
    resp = client.post("/public/hazard/report/ent-token-1", json=body)
    assert resp.status_code == 200
    record = db.added[0]
    assert record.title == "长" * 255
    assert record.description == "长" * 400
