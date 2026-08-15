"""隐患排查治理任务 5 测试：隐患登记（Web/移动端三渠道）+ AI 摘要分类。

测试风格与 tests/test_hazard_plan_api.py / test_hazard_template_api.py 一致：
无 db fixture，端点用 FastAPI TestClient + dependency_overrides + SQL 文本分发
mock；async 服务函数用 @pytest.mark.asyncio。

覆盖：
- 登记成功（source_type 五渠道 inspection/report/regulatory/accident/manual）
- 字段校验：source_type 枚举 / title / description / 长度
- hazard_type 数据字典码值校验（合法通过、非法 422）
- object_id / measure_id 企业归属校验（422）
- source_task_id / source_item_id 回填归属校验（422）
- 权限：企业主 / 启用管理员 / 普通启用成员 201（登记面向全员），
  非成员 / 禁用成员 404（读归属分层，无 403——取舍见端点 docstring）
- AI record-assist：成功 / 空描述 422 / 未配置降级 / 非成员 404
- record_assist 服务层：成功解析 / 非法返回降级 / 异常降级 / 无配置不调 LLM
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.data_dict import DataDict
from app.models.enterprise import Enterprise
from app.models.enterprise_org import EnterpriseMember
from app.models.hazard_management import HazardRecord
from app.models.user import User
from app.routers import hazard_management
from app.services.data_dict_service import invalidate_dict_cache
from app.services.hazard_ai_service import record_assist


# ── mock 工具 ──

def _scalar(value):
    res = MagicMock()
    res.scalar_one_or_none.return_value = value
    return res


def _scalars(values):
    res = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = list(values)
    res.scalars.return_value = scalars_mock
    return res


def _first(value):
    res = MagicMock()
    res.first.return_value = value
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


def _dict_row(code, label):
    return DataDict(dict_type="hazard_type", code=code, label=label,
                    value={}, scope="system", enabled=True, is_system=True)


def _hazard_type_rows(*codes):
    return [_dict_row(c, f"类型{c}") for c in codes]


def _record_db(ent, *, member=None, dict_rows=None, object_hit=None,
               measure_hit=None, source_task_hit=None, source_item_hit=None,
               record_count=0):
    """按 SQL 文本特征分发（参照 tests/test_hazard_plan_api.py 的 _hazard_db）。"""
    db = AsyncMock()
    db.added = []

    def fake_add(obj):
        if isinstance(obj, HazardRecord) and not getattr(obj, "id", None):
            obj.id = "r1"
        db.added.append(obj)

    db.add = MagicMock(side_effect=fake_add)

    def fake_execute(stmt, *params):
        text = str(stmt)
        if "FROM enterprises" in text:
            return _scalar(ent)
        if "FROM enterprise_members" in text:
            return _first(member if member and getattr(member, "enabled", True) else None)
        if "FROM data_dicts" in text:
            return _scalars(dict_rows or [])
        if "FROM risk_objects" in text:
            return _first(object_hit)
        if "FROM risk_measures" in text:
            return _first(measure_hit)
        if "FROM hazard_inspection_tasks" in text:
            return _first(source_task_hit)
        if "FROM hazard_inspection_items" in text:
            return _first(source_item_hit)
        if "FROM hazard_records" in text:
            return _count(record_count)
        return _scalar(None)

    db.execute.side_effect = fake_execute
    return db


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(hazard_management.router)

    def _override_user():
        return User(id="u1", email="a@b.c", name="A", role="user")

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = lambda: _record_db(_ent())
    with TestClient(app) as test_client:
        yield test_client


_RECORD_BODY = {
    "source_type": "report",
    "title": "配电箱门破损",
    "description": "配电箱门变形无法闭合，存在触电风险",
    "photo_urls": ["/uploads/a.jpg"],
    "location": "3 号车间东侧",
}


# ── 登记成功（各 source_type） ──

@pytest.mark.parametrize("source_type", ["inspection", "report", "regulatory", "accident", "manual"])
def test_record_create_success_each_source_type(client, source_type):
    db = _record_db(_ent(), record_count=0)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_RECORD_BODY, "source_type": source_type}
    resp = client.post("/enterprises/e1/hazard-inspection/records", json=body)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert resp.json()["code"] == 0
    assert data["source_type"] == source_type
    assert data["code"] == "HD-001"
    assert data["status"] == "registered"
    assert data["created_by"] == "u1"
    assert data["title"] == "配电箱门破损"
    assert data["location"] == "3 号车间东侧"
    assert data["photo_urls"] == ["/uploads/a.jpg"]
    record = db.added[0]
    assert isinstance(record, HazardRecord)
    assert record.enterprise_id == "e1"
    assert record.created_by == "u1"
    db.commit.assert_awaited()


def test_record_create_keeps_optional_refs(client):
    db = _record_db(_ent(), object_hit=MagicMock(), measure_hit=MagicMock(),
                    source_task_hit=MagicMock(), source_item_hit=MagicMock(),
                    dict_rows=_hazard_type_rows("equipment"), record_count=2)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_RECORD_BODY, "source_type": "inspection", "hazard_type": "equipment",
            "object_id": "o1", "measure_id": "m1", "source_task_id": "t1", "source_item_id": "i1"}
    resp = client.post("/enterprises/e1/hazard-inspection/records", json=body)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["code"] == "HD-003"
    assert data["object_id"] == "o1"
    assert data["measure_id"] == "m1"
    assert data["source_task_id"] == "t1"
    assert data["source_item_id"] == "i1"
    assert data["hazard_type"] == "equipment"
    record = db.added[0]
    assert record.object_id == "o1"
    assert record.source_type == "inspection"


# ── 字段校验 ──

def test_record_create_rejects_invalid_source_type(client):
    db = _record_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_RECORD_BODY, "source_type": "wechat"}
    resp = client.post("/enterprises/e1/hazard-inspection/records", json=body)
    assert resp.status_code == 422
    assert "source_type 非法" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_record_create_missing_title_422(client):
    db = _record_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    body = {k: v for k, v in _RECORD_BODY.items() if k != "title"}
    resp = client.post("/enterprises/e1/hazard-inspection/records", json=body)
    assert resp.status_code == 422  # pydantic 必填校验
    db.commit.assert_not_awaited()


def test_record_create_blank_title_422(client):
    db = _record_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_RECORD_BODY, "title": "   "}
    resp = client.post("/enterprises/e1/hazard-inspection/records", json=body)
    assert resp.status_code == 422
    assert "title 不能为空" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_record_create_blank_description_422(client):
    db = _record_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_RECORD_BODY, "description": "   "}
    resp = client.post("/enterprises/e1/hazard-inspection/records", json=body)
    assert resp.status_code == 422
    assert "description 不能为空" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_record_create_title_too_long_422(client):
    db = _record_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_RECORD_BODY, "title": "长" * 256}
    resp = client.post("/enterprises/e1/hazard-inspection/records", json=body)
    assert resp.status_code == 422  # pydantic max_length=255
    db.commit.assert_not_awaited()


# ── hazard_type 数据字典校验 ──

def test_record_create_hazard_type_from_dict_ok(client):
    invalidate_dict_cache("e1", "hazard_type")
    db = _record_db(_ent(), dict_rows=_hazard_type_rows("equipment", "fire"))
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_RECORD_BODY, "hazard_type": "fire"}
    resp = client.post("/enterprises/e1/hazard-inspection/records", json=body)
    assert resp.status_code == 201
    assert resp.json()["data"]["hazard_type"] == "fire"


def test_record_create_hazard_type_not_in_dict_422(client):
    invalidate_dict_cache("e1", "hazard_type")
    db = _record_db(_ent(), dict_rows=_hazard_type_rows("equipment", "fire"))
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_RECORD_BODY, "hazard_type": "mechanical"}
    resp = client.post("/enterprises/e1/hazard-inspection/records", json=body)
    assert resp.status_code == 422
    assert "hazard_type 非法" in resp.json()["detail"]
    db.commit.assert_not_awaited()


# ── object / measure 归属校验 ──

def test_record_create_object_not_in_enterprise_422(client):
    db = _record_db(_ent(), object_hit=None)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_RECORD_BODY, "object_id": "o9"}
    resp = client.post("/enterprises/e1/hazard-inspection/records", json=body)
    assert resp.status_code == 422
    assert "风险点不属于该企业" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_record_create_measure_not_in_enterprise_422(client):
    db = _record_db(_ent(), measure_hit=None)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_RECORD_BODY, "measure_id": "m9"}
    resp = client.post("/enterprises/e1/hazard-inspection/records", json=body)
    assert resp.status_code == 422
    assert "管控措施不属于该企业" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_record_create_source_task_not_in_enterprise_422(client):
    db = _record_db(_ent(), source_task_hit=None)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_RECORD_BODY, "source_task_id": "t9"}
    resp = client.post("/enterprises/e1/hazard-inspection/records", json=body)
    assert resp.status_code == 422
    assert "排查任务不属于该企业" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_record_create_source_item_not_in_enterprise_422(client):
    db = _record_db(_ent(), source_item_hit=None)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_RECORD_BODY, "source_item_id": "i9"}
    resp = client.post("/enterprises/e1/hazard-inspection/records", json=body)
    assert resp.status_code == 422
    assert "排查项不属于该企业" in resp.json()["detail"]
    db.commit.assert_not_awaited()


# ── 权限：登记面向全员（企业主 / 启用管理员 / 启用成员 201；非归属 404） ──

def test_record_create_owner_allowed(client):
    db = _record_db(_ent(user_id="u1"))
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records", json=_RECORD_BODY)
    assert resp.status_code == 201


def test_record_create_admin_member_allowed(client):
    member = EnterpriseMember(id="m2", enterprise_id="e1", user_id="u1",
                              role="enterprise_admin", enabled=True)
    db = _record_db(_ent(user_id="u2"), member=member)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records", json=_RECORD_BODY)
    assert resp.status_code == 201
    assert resp.json()["data"]["created_by"] == "u1"


def test_record_create_plain_member_allowed(client):
    """角色取舍：登记面向全员——普通启用成员也可登记（任务 3 写权限 403 不适用）。"""
    member = EnterpriseMember(id="m1", enterprise_id="e1", user_id="u1",
                              role="member", enabled=True)
    db = _record_db(_ent(user_id="u2"), member=member)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records", json=_RECORD_BODY)
    assert resp.status_code == 201


def test_record_create_non_member_404(client):
    db = _record_db(_ent(user_id="u2"), member=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records", json=_RECORD_BODY)
    assert resp.status_code == 404
    assert "企业不存在" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_record_create_disabled_member_404(client):
    disabled = EnterpriseMember(id="m1", enterprise_id="e1", user_id="u1", enabled=False)
    db = _record_db(_ent(user_id="u2"), member=disabled)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records", json=_RECORD_BODY)
    assert resp.status_code == 404
    db.commit.assert_not_awaited()


# ── AI record-assist：端点 ──

def test_ai_record_assist_success(client):
    db = _record_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    fake = {"available": True, "title": "配电箱门破损", "hazard_type": "equipment",
            "suggested_level": "一般", "reason": "设施缺陷", "note": ""}
    with patch("app.routers.hazard_management._get_ai_config", AsyncMock(return_value=MagicMock())), \
         patch("app.routers.hazard_management.record_assist", AsyncMock(return_value=fake)) as mock_assist:
        resp = client.post("/enterprises/e1/hazard-inspection/ai/record-assist",
                           json={"description": "配电箱门破损", "object_id": "o1"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["available"] is True
    assert data["title"] == "配电箱门破损"
    assert data["hazard_type"] == "equipment"
    assert data["suggested_level"] == "一般"
    assert mock_assist.await_count == 1
    assert mock_assist.await_args.args[0] == "配电箱门破损"
    assert mock_assist.await_args.kwargs == {"object_id": "o1", "measure_id": None}


def test_ai_record_assist_blank_description_422(client):
    db = _record_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/ai/record-assist",
                       json={"description": "   "})
    assert resp.status_code == 422
    assert "description 不能为空" in resp.json()["detail"]


def test_ai_record_assist_no_config_degrades_200(client):
    db = _record_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    fallback = {"available": False, "title": "", "hazard_type": "", "suggested_level": "",
                "reason": "", "note": "AI 不可用，请手动填写隐患摘要与分类"}
    with patch("app.routers.hazard_management._get_ai_config",
               AsyncMock(side_effect=HTTPException(400, "系统未配置 AI 模型，请联系管理员"))), \
         patch("app.routers.hazard_management.record_assist",
               AsyncMock(return_value=fallback)) as mock_assist:
        resp = client.post("/enterprises/e1/hazard-inspection/ai/record-assist",
                           json={"description": "配电箱门破损"})
    assert resp.status_code == 200
    assert resp.json()["data"] == fallback
    assert mock_assist.await_count == 1
    assert mock_assist.await_args.args[1] is None  # 未配置 → ai_config=None 走服务兜底


def test_ai_record_assist_non_member_404(client):
    db = _record_db(_ent(user_id="u2"), member=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/ai/record-assist",
                       json={"description": "配电箱门破损"})
    assert resp.status_code == 404


# ── record_assist 服务层 ──

@pytest.mark.asyncio
async def test_record_assist_success_parses_fence():
    payload = {"title": "配电箱门破损", "hazard_type": "equipment",
               "suggested_level": "一般", "reason": "门体变形无法闭合"}
    raw = "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"
    with patch("app.services.hazard_ai_service.llm_text_completion", AsyncMock(return_value=raw)):
        out = await record_assist("配电箱门破损", MagicMock())
    assert out["available"] is True
    assert out["title"] == "配电箱门破损"
    assert out["hazard_type"] == "equipment"
    assert out["suggested_level"] == "一般"
    assert out["reason"]


@pytest.mark.asyncio
async def test_record_assist_title_capped_at_255():
    payload = {"title": "长" * 300, "hazard_type": "fire",
               "suggested_level": "重大", "reason": "原因"}
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))):
        out = await record_assist("描述", MagicMock())
    assert out["available"] is True
    assert len(out["title"]) == 255


@pytest.mark.asyncio
async def test_record_assist_invalid_hazard_type_degrades():
    payload = {"title": "摘要", "hazard_type": "mechanical",
               "suggested_level": "一般", "reason": "原因"}
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))):
        out = await record_assist("描述", MagicMock())
    assert out["available"] is False
    assert out["title"] == ""
    assert out["hazard_type"] == ""


@pytest.mark.asyncio
async def test_record_assist_invalid_level_degrades():
    payload = {"title": "摘要", "hazard_type": "fire",
               "suggested_level": "特别重大", "reason": "原因"}
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))):
        out = await record_assist("描述", MagicMock())
    assert out["available"] is False
    assert out["suggested_level"] == ""


@pytest.mark.asyncio
async def test_record_assist_empty_title_degrades():
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value='{"title": "", "hazard_type": "fire", '
                                      '"suggested_level": "一般", "reason": "原因"}')):
        out = await record_assist("描述", MagicMock())
    assert out["available"] is False


@pytest.mark.asyncio
async def test_record_assist_failure_degrades():
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(side_effect=Exception("timeout"))):
        out = await record_assist("描述", MagicMock())
    assert out["available"] is False
    assert out["note"]


@pytest.mark.asyncio
async def test_record_assist_invalid_json_degrades():
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value="not a json")):
        out = await record_assist("描述", MagicMock())
    assert out["available"] is False


@pytest.mark.asyncio
async def test_record_assist_no_config_skips_llm():
    with patch("app.services.hazard_ai_service.llm_text_completion", AsyncMock()) as mock_llm:
        out = await record_assist("描述", None)
    assert out["available"] is False
    assert out["title"] == ""
    mock_llm.assert_not_awaited()
