"""公开只读风险告知卡 API 端点测试（无鉴权，token 校验）。

独立 FastAPI 应用挂载 public_risk_notice.router，用 dependency_overrides
替换 DB 依赖；DB mock 按 SQL 文本特征分发查询结果（参考 test_risk_notice_card_api.py）。
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.models.enterprise import Enterprise
from app.models.risk_management import RiskEvent, RiskObject
from app.routers import public_risk_notice


def _enterprise(**overrides):
    ent = Enterprise(
        id="e1",
        user_id="u1",
        name="甲公司",
        safety_officer="李四",
        safety_officer_phone="13900000000",
    )
    for key, value in overrides.items():
        setattr(ent, key, value)
    return ent


def _risk_object(**overrides):
    obj = RiskObject(
        id="o1",
        enterprise_id="e1",
        zone_id="z1",
        name="配电室",
        responsible_unit="动力车间",
        responsible_person="王五",
        contact_phone="13800000000",
        public_token="tok1",
    )
    for key, value in overrides.items():
        setattr(obj, key, value)
    return obj


def _fire_event():
    return RiskEvent(
        accident_type="火灾",
        risk_level="重大",
        trigger_conditions="泄漏遇明火",
        consequences="火灾爆炸",
        method_type="LS",
    )


def _rows_result(rows):
    res = MagicMock()
    res.scalars.return_value.all.return_value = rows
    return res


def _scalar_result(value):
    res = MagicMock()
    res.scalar_one_or_none.return_value = value
    return res


def _public_db(ent, obj, objects=None):
    """按 SQL 文本特征分发：
    FROM enterprises → 企业（scalar_one_or_none）；
    risk_notice_cards → 快照（first，测试中恒为 None）；
    FROM risk_objects + public_token → 公开 token 目标对象；
    FROM risk_objects + enterprise_id + ORDER BY → 企业全部对象投影行。
    """
    db = AsyncMock()
    db.add = MagicMock()

    def fake_execute(stmt):
        text = str(stmt)
        if "FROM enterprises" in text:
            return _scalar_result(ent)
        if "risk_notice_cards" in text:
            res = MagicMock()
            res.scalars.return_value.first.return_value = None
            return res
        if "FROM risk_objects" in text:
            if "public_token" in text:
                return _scalar_result(obj)
            if "enterprise_id =" in text and "ORDER BY" in text:
                return _rows_result(objects or [])
            return _scalar_result(obj)
        return _rows_result([])

    db.execute.side_effect = fake_execute
    return db


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(public_risk_notice.router)
    app.dependency_overrides[get_db] = lambda: _public_db(None, None)
    with TestClient(app) as test_client:
        yield test_client


def test_public_unknown_token_404(client):
    client.app.dependency_overrides[get_db] = lambda: _public_db(None, None)
    resp = client.get("/public/risk-notice-cards/not-a-token")
    assert resp.status_code == 404
    assert "卡片不存在或链接已失效" in resp.json()["detail"]


def test_public_valid_token_returns_complete_card_data(client):
    ent = _enterprise()
    obj = _risk_object()
    obj.events.append(_fire_event())
    client.app.dependency_overrides[get_db] = lambda: _public_db(ent, obj, [obj])

    resp = client.get("/public/risk-notice-cards/tok1")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "public, max-age=300"
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["object_id"] == "o1"
    assert data["enterprise_name"] == "甲公司"
    assert data["name"] == "配电室"
    assert data["code"] == "FX-001"
    assert data["level"] == "重大"
    assert data["level_color"]
    assert data["responsible_unit"] == "动力车间"
    assert data["responsible_person"] == "王五"
    assert data["contact_phone"] == "13800000000"
    assert data["fallback_used"] is False
    assert data["accident_types"] == ["火灾"]
    assert data["hazard_description"] == "泄漏遇明火；火灾爆炸"
    assert data["emergency_measures"]
    assert data["snapshot"] is None
    assert data["stale"] is False
    assert data["public_url"] == "/r/tok1"
    assert data["generated_at"]


def test_public_token_but_enterprise_deleted_404(client):
    obj = _risk_object()
    obj.events.append(_fire_event())
    client.app.dependency_overrides[get_db] = lambda: _public_db(None, obj, [obj])

    resp = client.get("/public/risk-notice-cards/tok1")
    assert resp.status_code == 404
    assert "卡片不存在或链接已失效" in resp.json()["detail"]
