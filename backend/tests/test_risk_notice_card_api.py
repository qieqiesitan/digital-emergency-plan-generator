"""风险告知卡列表/详情 API 端点级测试。

独立 FastAPI 应用挂载 router，用 dependency_overrides 替换鉴权与 DB 依赖；
DB mock 按 SQL 文本特征分发查询结果（参考 test_onboarding_routes.py）。
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.risk_management import RiskEvent, RiskObject
from app.routers import risk_notice_card


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


def _count_result(value):
    res = MagicMock()
    res.scalar.return_value = value
    return res


def _risk_card_db(ent, objs, detail_obj=None, events_obj=None, snapshots=None, snapshot=None):
    """按 SQL 文本特征分发：
    FROM enterprises → 企业（scalar_one_or_none）；
    risk_notice_cards + enterprise_id → 企业全部快照列表（all）；
    risk_notice_cards（无 enterprise_id）→ 单对象快照（first，详情路径）；
    FROM risk_objects + enterprise_id + ORDER BY → 企业全部对象列表；
    FROM risk_objects + enterprise_id（无 ORDER BY）→ 详情归属对象；
    """
    db = AsyncMock()
    db.add = MagicMock()

    def fake_execute(stmt, *params):
        text = str(stmt)
        if "FROM enterprises" in text:
            return _scalar_result(ent)
        if "FROM hazard_records" in text:
            # 未闭环隐患派生计数（详情/导出走 build_card_data 内查询）
            return _count_result(0)
        if "risk_notice_cards" in text:
            res = MagicMock()
            if "WHERE risk_notice_cards.enterprise_id" in text:
                res.scalars.return_value.all.return_value = snapshots or []
            else:
                res.scalars.return_value.first.return_value = snapshot
            return res
        if "FROM risk_objects" in text:
            if "enterprise_id =" in text:
                if "ORDER BY" in text:
                    return _rows_result(objs)
                return _scalar_result(detail_obj)
            return _scalar_result(events_obj)
        return _rows_result([])

    db.execute.side_effect = fake_execute
    return db


@pytest.fixture()
def client():
    from app.models.user import User

    app = FastAPI()
    app.include_router(risk_notice_card.router)

    current_user = User(id="u1", email="a@b.c", name="A", role="admin")

    def _override_user():
        return current_user

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = lambda: _risk_card_db(None, [])
    with TestClient(app) as test_client:
        yield test_client


def test_list_enterprise_not_found_404(client):
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(None, [])
    resp = client.get("/enterprises/not-exist/risk-notice-cards")
    assert resp.status_code == 404
    assert "企业不存在" in resp.json()["detail"]


def test_list_returns_card_summaries(client):
    ent = _enterprise()
    zone = MagicMock()
    zone.name = "A区"
    obj = _risk_object()
    obj.zone = zone
    obj.events.append(_fire_event())
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(ent, [obj])

    resp = client.get("/enterprises/e1/risk-notice-cards")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert len(data) == 1
    item = data[0]
    assert item["object_id"] == "o1"
    assert item["name"] == "配电室"
    assert item["zone_name"] == "A区"
    assert item["level"] == "重大"
    assert item["level_color"]
    assert item["accident_types"] == ["火灾"]
    assert item["responsible_unit"] == "动力车间"
    assert item["public_url"] == "/r/tok1"
    assert item["snapshot"] is None
    assert item["stale"] is False
    categories = {s["category"] for s in item["signs"]}
    assert "warning" in categories and "prohibition" in categories


def test_list_includes_snapshot_metadata_not_stale(client):
    from datetime import datetime, timezone

    from app.models.risk_notice_card import RiskNoticeCard

    ent = _enterprise()
    zone = MagicMock()
    zone.name = "A区"
    obj = _risk_object()
    obj.zone = zone
    ev = _fire_event()
    obj.events.append(ev)
    obj.updated_at = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    ev.updated_at = datetime(2026, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
    snap = RiskNoticeCard(
        enterprise_id="e1",
        object_id="o1",
        version=3,
        source="ai",
        content={"hazard_description": "快照文案"},
        updated_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [obj], snapshots=[snap]
    )

    resp = client.get("/enterprises/e1/risk-notice-cards")
    assert resp.status_code == 200
    item = resp.json()["data"][0]
    assert item["snapshot"] == {"version": 3, "source": "ai"}
    assert item["stale"] is False


def test_list_marks_stale_when_snapshot_older_than_source(client):
    from datetime import datetime, timezone

    from app.models.risk_notice_card import RiskNoticeCard

    ent = _enterprise()
    zone = MagicMock()
    zone.name = "A区"
    obj = _risk_object()
    obj.zone = zone
    ev = _fire_event()
    obj.events.append(ev)
    obj.updated_at = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    ev.updated_at = datetime(2026, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
    snap = RiskNoticeCard(
        enterprise_id="e1",
        object_id="o1",
        version=1,
        source="ai",
        content={"hazard_description": "旧快照"},
        updated_at=datetime(2026, 1, 1, 9, 0, 0, tzinfo=timezone.utc),
    )
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [obj], snapshots=[snap]
    )

    resp = client.get("/enterprises/e1/risk-notice-cards")
    assert resp.status_code == 200
    item = resp.json()["data"][0]
    assert item["snapshot"] == {"version": 1, "source": "ai"}
    assert item["stale"] is True


def test_list_filters_by_level_zone_keyword(client):
    ent = _enterprise()
    obj1 = _risk_object()
    zone1 = MagicMock()
    zone1.name = "A区"
    obj1.zone = zone1
    obj1.events.append(_fire_event())
    obj2 = _risk_object(id="o2", name="储罐区", responsible_unit=None, responsible_person=None,
                        contact_phone=None, public_token="tok2")
    obj2.events.append(RiskEvent(accident_type="火灾", risk_level="一般", method_type="LS"))
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(ent, [obj1, obj2])

    resp = client.get("/enterprises/e1/risk-notice-cards", params={"level": "重大"})
    assert [i["object_id"] for i in resp.json()["data"]] == ["o1"]

    resp = client.get("/enterprises/e1/risk-notice-cards", params={"keyword": "储罐"})
    assert [i["object_id"] for i in resp.json()["data"]] == ["o2"]

    resp = client.get("/enterprises/e1/risk-notice-cards", params={"zone_id": "z-other"})
    assert resp.json()["data"] == []


def test_detail_object_not_found_404(client):
    ent = _enterprise()
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(ent, [], detail_obj=None)
    resp = client.get("/enterprises/e1/risk-notice-cards/not-exist")
    assert resp.status_code == 404
    assert "风险点不存在" in resp.json()["detail"]


def test_detail_returns_complete_card_data(client):
    ent = _enterprise()
    obj = _risk_object()
    obj.events.append(_fire_event())
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [obj], detail_obj=obj, events_obj=obj
    )

    resp = client.get("/enterprises/e1/risk-notice-cards/o1")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["object_id"] == "o1"
    assert data["enterprise_name"] == "甲公司"
    assert data["name"] == "配电室"
    assert data["code"] == "FX-001"
    assert data["level"] == "重大"
    assert data["responsible_unit"] == "动力车间"
    assert data["responsible_person"] == "王五"
    assert data["contact_phone"] == "13800000000"
    assert data["fallback_used"] is False
    assert data["accident_types"] == ["火灾"]
    assert data["hazard_description"] == "泄漏遇明火；火灾爆炸"
    assert data["control_measures"] == []
    assert data["emergency_measures"]
    assert data["snapshot"] is None
    assert data["stale"] is False
    assert data["public_url"] == "/r/tok1"
    assert data["generated_at"]


def test_detail_missing_enterprise_404(client):
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(None, [])
    resp = client.get("/enterprises/not-exist/risk-notice-cards/o1")
    assert resp.status_code == 404
    assert "企业不存在" in resp.json()["detail"]


def test_detail_fallback_responsible_uses_enterprise_values(client):
    ent = _enterprise()
    obj = _risk_object(responsible_unit=None, responsible_person=None, contact_phone=None)
    obj.events.append(_fire_event())
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [obj], detail_obj=obj, events_obj=obj
    )

    resp = client.get("/enterprises/e1/risk-notice-cards/o1")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["fallback_used"] is True
    assert data["responsible_unit"] == "甲公司"
    assert data["responsible_person"] == "李四"
    assert data["contact_phone"] == "13900000000"


def test_detail_empty_object_uses_fallback_template(client):
    ent = _enterprise()
    obj = _risk_object()
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [obj], detail_obj=obj
    )

    resp = client.get("/enterprises/e1/risk-notice-cards/o1")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["level"] == "未评估"
    assert data["signs"] == []
    assert data["accident_types"] == []
    assert data["hazard_description"] == ""
    assert data["emergency_measures"] == [
        "1. 立即停止作业，保护现场",
        "2. 拨打 119/120 报警",
        "3. 组织人员疏散，报告企业应急管理部门",
    ]


def test_list_rejects_invalid_level(client):
    resp = client.get("/enterprises/e1/risk-notice-cards", params={"level": "极高"})
    assert resp.status_code == 422
    assert "非法的 level 参数" in resp.json()["detail"]


def test_auth_required_without_override():
    app = FastAPI()
    app.include_router(risk_notice_card.router)
    app.dependency_overrides[get_db] = lambda: _risk_card_db(None, [])
    with TestClient(app) as test_client:
        resp = test_client.get("/enterprises/e1/risk-notice-cards")
    assert resp.status_code == 401


def test_ai_optimize_returns_optimized_right_column(client, monkeypatch):
    import json

    from app.services import risk_notice_card_ai

    ent = _enterprise()
    obj = _risk_object()
    obj.events.append(_fire_event())
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [obj], detail_obj=obj, events_obj=obj
    )

    payload = {
        "hazard_description": "优化：配电室高温短路",
        "control_measures": ["① 安装漏电保护", "② 定期检测"],
        "emergency_measures": ["① 立即断电", "② 拨打 120"],
    }

    async def fake_llm(messages, ai_config, timeout=120):
        assert timeout == 60
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "你是安全生产专家。"
        user_content = messages[1]["content"]
        assert "甲公司" in user_content
        assert "配电室" in user_content
        assert "泄漏遇明火" in user_content  # 原版文本传入
        return json.dumps(payload, ensure_ascii=False)

    monkeypatch.setattr(risk_notice_card_ai, "llm_text_completion", fake_llm)

    resp = client.post("/enterprises/e1/risk-notice-cards/o1/ai-optimize")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["original"]["accident_types"] == ["火灾"]
    assert data["optimized"]["hazard_description"] == payload["hazard_description"]
    assert data["optimized"]["control_measures"] == payload["control_measures"]
    assert data["optimized"]["emergency_measures"] == payload["emergency_measures"]
    assert data["optimized"]["accident_types"] == ["火灾"]


def test_ai_optimize_missing_fields_fall_back_to_original(client, monkeypatch):
    import json

    from app.services import risk_notice_card_ai

    ent = _enterprise()
    obj = _risk_object()
    obj.events.append(_fire_event())
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [obj], detail_obj=obj, events_obj=obj
    )

    async def fake_llm(messages, ai_config, timeout=120):
        # 缺 hazard_description、control_measures 为字符串、emergency_measures 为 None
        return json.dumps(
            {"control_measures": "不是列表", "emergency_measures": None},
            ensure_ascii=False,
        )

    monkeypatch.setattr(risk_notice_card_ai, "llm_text_completion", fake_llm)

    resp = client.post("/enterprises/e1/risk-notice-cards/o1/ai-optimize")
    assert resp.status_code == 200
    optimized = resp.json()["data"]["optimized"]
    original = resp.json()["data"]["original"]
    assert optimized["hazard_description"] == original["hazard_description"]
    assert optimized["control_measures"] == original["control_measures"]
    assert optimized["emergency_measures"] == original["emergency_measures"]
    assert optimized["accident_types"] == ["火灾"]


def test_ai_optimize_invalid_json_returns_502(client, monkeypatch):
    from app.services import risk_notice_card_ai

    ent = _enterprise()
    obj = _risk_object()
    obj.events.append(_fire_event())
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [obj], detail_obj=obj, events_obj=obj
    )

    async def fake_llm(messages, ai_config, timeout=120):
        return "这不是 JSON"

    monkeypatch.setattr(risk_notice_card_ai, "llm_text_completion", fake_llm)

    resp = client.post("/enterprises/e1/risk-notice-cards/o1/ai-optimize")
    assert resp.status_code == 502
    assert "AI 返回格式异常" in resp.json()["detail"]


def test_ai_optimize_code_block_wrapped_json_parses(client, monkeypatch):
    import json

    from app.services import risk_notice_card_ai

    ent = _enterprise()
    obj = _risk_object()
    obj.events.append(_fire_event())
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [obj], detail_obj=obj, events_obj=obj
    )

    payload = {
        "hazard_description": "优化后描述",
        "control_measures": ["① 新措施"],
        "emergency_measures": ["① 新应急"],
    }

    async def fake_llm(messages, ai_config, timeout=120):
        return "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"

    monkeypatch.setattr(risk_notice_card_ai, "llm_text_completion", fake_llm)

    resp = client.post("/enterprises/e1/risk-notice-cards/o1/ai-optimize")
    assert resp.status_code == 200
    optimized = resp.json()["data"]["optimized"]
    assert optimized["hazard_description"] == "优化后描述"
    assert optimized["control_measures"] == ["① 新措施"]
    assert optimized["emergency_measures"] == ["① 新应急"]


def test_ai_optimize_not_configured_returns_400(client, monkeypatch):
    from app.services import risk_notice_card_ai

    ent = _enterprise()
    obj = _risk_object()
    obj.events.append(_fire_event())
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [obj], detail_obj=obj, events_obj=obj
    )

    async def no_config(user_id, db):
        raise HTTPException(400, "系统未配置 AI 模型，请联系管理员")

    monkeypatch.setattr(risk_notice_card_ai, "_get_ai_config", no_config)

    resp = client.post("/enterprises/e1/risk-notice-cards/o1/ai-optimize")
    assert resp.status_code == 400
    assert "系统未配置" in resp.json()["detail"]


def test_ai_optimize_failure_returns_502(client, monkeypatch):
    from app.services import risk_notice_card_ai

    ent = _enterprise()
    obj = _risk_object()
    obj.events.append(_fire_event())
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [obj], detail_obj=obj, events_obj=obj
    )

    async def broken_llm(messages, ai_config, timeout=120):
        raise ValueError("llm boom")

    monkeypatch.setattr(risk_notice_card_ai, "llm_text_completion", broken_llm)

    resp = client.post("/enterprises/e1/risk-notice-cards/o1/ai-optimize")
    assert resp.status_code == 502
    assert "AI 优化失败" in resp.json()["detail"]


def test_save_snapshot_creates_version_one(client):
    ent = _enterprise()
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [], detail_obj=_risk_object()
    )

    resp = client.put(
        "/enterprises/e1/risk-notice-cards/o1/snapshot",
        json={
            "content": {
                "hazard_description": "手动保存文案",
                "accident_types": ["火灾"],
                "control_measures": ["① 措施"],
                "emergency_measures": ["① 应急"],
            }
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["version"] == 1
    assert data["source"] == "ai"


def test_save_snapshot_cross_enterprise_object_404(client):
    ent = _enterprise()
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [], detail_obj=None
    )

    resp = client.put(
        "/enterprises/e1/risk-notice-cards/o-other/snapshot",
        json={
            "content": {
                "hazard_description": "越权写入",
                "accident_types": ["火灾"],
                "control_measures": ["① 措施"],
                "emergency_measures": ["① 应急"],
            }
        },
    )
    assert resp.status_code == 404
    assert "风险点不存在" in resp.json()["detail"]


def test_reset_token_returns_new_public_url(client):
    ent = _enterprise()
    obj = _risk_object(public_token="old-token")
    db = _risk_card_db(ent, [], detail_obj=obj)
    client.app.dependency_overrides[get_db] = lambda: db

    resp = client.post("/enterprises/e1/risk-notice-cards/o1/token/reset")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["public_url"].startswith("/r/")
    assert data["public_url"] != "/r/old-token"
    assert len(data["public_url"].removeprefix("/r/")) == 64
    update_stmts = [
        c.args[0]
        for c in db.execute.await_args_list
        if "UPDATE risk_objects" in str(c.args[0]) and "public_token" in str(c.args[0])
    ]
    assert len(update_stmts) == 1
    # Core UPDATE 不携带 updated_at，绕过 ORM onupdate，避免误标「数据已变更」
    assert "updated_at" not in str(update_stmts[0])
    db.commit.assert_awaited_once()


def test_reset_token_object_not_found_404(client):
    ent = _enterprise()
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [], detail_obj=None
    )

    resp = client.post("/enterprises/e1/risk-notice-cards/not-exist/token/reset")
    assert resp.status_code == 404
    assert "风险点不存在" in resp.json()["detail"]


def test_review_signs_parses_suggestion(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    from app.services import risk_notice_card_ai

    captured_messages = []

    async def fake_completion(messages, config, timeout=60):
        captured_messages.append(messages)
        return (
            '{"remove": ["instruction-helmet"], "add": ["warning-fall"], '
            '"reasons": [{"sign_name": "必须戴安全帽", "reason": "会议室为非生产区域"}, '
            '{"sign_name": "当心滑倒", "reason": "存在滑倒风险"}]}'
        )

    async def run():
        monkeypatch.setattr(risk_notice_card_ai, "llm_text_completion", fake_completion)
        db = AsyncMock()
        db.execute.return_value = MagicMock()  # 避免 _get_ai_config 产生未 await 的 coroutine
        result = await risk_notice_card_ai.review_signs(
            db, "u1", "测试公司", "会议室", "工作场所", "三楼",
            [{"accident_type": "火灾"}, {"accident_type": "人员滑倒/摔伤"}],
            [{"category": "instruction", "name": "必须戴安全帽", "svg_name": "instruction-helmet"}],
            [{"category": "warning", "name": "当心滑倒", "svg_name": "warning-fall"}],
        )
        assert result["remove"] == ["instruction-helmet"]
        assert result["add"] == ["warning-fall"]
        assert len(result["reasons"]) == 2
        prompt = captured_messages[0][1]["content"]
        assert "只能从这里选" in prompt
        assert "每类" in prompt

    asyncio.run(run())


def test_ai_review_signs_endpoint_returns_suggestion(client, monkeypatch):
    from app.services import risk_notice_card_ai

    ent = _enterprise()
    obj = _risk_object()
    obj.events.append(_fire_event())
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [obj], detail_obj=obj, events_obj=obj
    )

    async def fake_review(*args, **kwargs):
        return {
            "remove": [],
            "add": ["warning-fall"],
            "reasons": [{"sign_name": "当心滑倒", "reason": "有滑倒风险"}],
        }

    monkeypatch.setattr(risk_notice_card_ai, "review_signs", fake_review)

    resp = client.post("/enterprises/e1/risk-notice-cards/o1/ai-review-signs")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["suggestion"]["add"] == ["warning-fall"]
    assert data["original_signs"]
    assert "warning-fire" in [s["svg_name"] for s in data["original_signs"]]
    # 候选库：全量去重返回，供前端人工微调/中文名映射
    catalog = data["catalog"]
    assert catalog
    catalog_names = [s["svg_name"] for s in catalog]
    assert "warning-fire" in catalog_names
    assert "prohibition-smoking" in catalog_names
    assert "notice-exit" in catalog_names
    assert len(catalog_names) == len(set(catalog_names))
    assert all(set(s) == {"category", "name", "svg_name"} for s in catalog)
    assert (
        next(s for s in catalog if s["svg_name"] == "warning-fire")["category"]
        == "warning"
    )


def test_ai_review_signs_object_not_found_404(client):
    ent = _enterprise()
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [], detail_obj=None
    )

    resp = client.post("/enterprises/e1/risk-notice-cards/not-exist/ai-review-signs")
    assert resp.status_code == 404
    assert "风险点不存在" in resp.json()["detail"]


def test_ai_review_signs_failure_returns_502(client, monkeypatch):
    from app.services import risk_notice_card_ai

    ent = _enterprise()
    obj = _risk_object()
    obj.events.append(_fire_event())
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [obj], detail_obj=obj, events_obj=obj
    )

    async def broken_review(*args, **kwargs):
        raise ValueError("llm boom")

    monkeypatch.setattr(risk_notice_card_ai, "review_signs", broken_review)

    resp = client.post("/enterprises/e1/risk-notice-cards/o1/ai-review-signs")
    assert resp.status_code == 502
    assert "AI 审查失败，已保留原版" in resp.json()["detail"]


def test_ai_review_signs_http_exception_passthrough(client, monkeypatch):
    from fastapi import HTTPException
    from app.services import risk_notice_card_ai

    ent = _enterprise()
    obj = _risk_object()
    obj.events.append(_fire_event())
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [obj], detail_obj=obj, events_obj=obj
    )

    async def no_config(user_id, db):
        raise HTTPException(400, "系统未配置 AI 模型，请联系管理员")

    monkeypatch.setattr(risk_notice_card_ai, "_get_ai_config", no_config)

    resp = client.post("/enterprises/e1/risk-notice-cards/o1/ai-review-signs")
    assert resp.status_code == 400
    assert "系统未配置" in resp.json()["detail"]


def test_ai_review_signs_prefers_snapshot_signs(client, monkeypatch):
    from app.models.risk_notice_card import RiskNoticeCard
    from app.services import risk_notice_card_ai

    ent = _enterprise()
    obj = _risk_object()
    obj.events.append(_fire_event())
    snap = RiskNoticeCard(
        enterprise_id="e1",
        object_id="o1",
        version=2,
        source="ai",
        content={
            "signs": [
                {"category": "warning", "name": "当心坠落", "svg_name": "warning-fall"}
            ]
        },
    )
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [obj], detail_obj=obj, events_obj=obj, snapshot=snap
    )

    async def fake_review(*args, **kwargs):
        return {"remove": [], "add": [], "reasons": []}

    monkeypatch.setattr(risk_notice_card_ai, "review_signs", fake_review)

    resp = client.post("/enterprises/e1/risk-notice-cards/o1/ai-review-signs")
    assert resp.status_code == 200
    assert resp.json()["data"]["original_signs"] == [
        {"category": "warning", "name": "当心坠落", "svg_name": "warning-fall"}
    ]


def test_ai_review_signs_old_snapshot_uses_snapshot_accident_types(client, monkeypatch):
    from app.models.risk_notice_card import RiskNoticeCard
    from app.services import risk_notice_card_ai

    ent = _enterprise()
    obj = _risk_object()
    obj.events.append(_fire_event())  # 源数据事故类型：火灾
    snap = RiskNoticeCard(
        enterprise_id="e1",
        object_id="o1",
        version=1,
        source="ai",
        content={"accident_types": ["高处坠落"]},  # 旧快照无 signs，回退按快照事故类型
    )
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [obj], detail_obj=obj, events_obj=obj, snapshot=snap
    )

    async def fake_review(*args, **kwargs):
        return {"remove": [], "add": [], "reasons": []}

    monkeypatch.setattr(risk_notice_card_ai, "review_signs", fake_review)

    resp = client.post("/enterprises/e1/risk-notice-cards/o1/ai-review-signs")
    assert resp.status_code == 200
    svg_names = [s["svg_name"] for s in resp.json()["data"]["original_signs"]]
    assert "warning-fall" in svg_names
    assert "warning-fire" not in svg_names


def test_ai_review_signs_malformed_suggestion_returns_502(client, monkeypatch):
    from app.services import risk_notice_card_ai

    ent = _enterprise()
    obj = _risk_object()
    obj.events.append(_fire_event())
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [obj], detail_obj=obj, events_obj=obj
    )

    async def fake_review(*args, **kwargs):
        return {"remove": [], "add": [123], "reasons": []}

    monkeypatch.setattr(risk_notice_card_ai, "review_signs", fake_review)

    resp = client.post("/enterprises/e1/risk-notice-cards/o1/ai-review-signs")
    assert resp.status_code == 502
    assert "AI 审查失败，已保留原版" in resp.json()["detail"]


def test_ai_review_signs_drops_malformed_snapshot_signs(client, monkeypatch):
    from app.models.risk_notice_card import RiskNoticeCard
    from app.services import risk_notice_card_ai

    ent = _enterprise()
    obj = _risk_object()
    obj.events.append(_fire_event())
    snap = RiskNoticeCard(
        enterprise_id="e1",
        object_id="o1",
        version=2,
        source="ai",
        content={
            "signs": [
                {"category": "warning", "name": "当心火灾"}  # 缺 svg_name，非法元素静默丢弃
            ]
        },
    )
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [obj], detail_obj=obj, events_obj=obj, snapshot=snap
    )

    async def fake_review(*args, **kwargs):
        return {"remove": [], "add": [], "reasons": []}

    monkeypatch.setattr(risk_notice_card_ai, "review_signs", fake_review)

    resp = client.post("/enterprises/e1/risk-notice-cards/o1/ai-review-signs")
    assert resp.status_code == 200
    assert resp.json()["data"]["original_signs"] == []


def test_review_signs_invalid_json_raises_502(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock

    import pytest
    from fastapi import HTTPException
    from app.services import risk_notice_card_ai

    async def fake_completion(messages, config, timeout=60):
        return "这不是 JSON"

    async def run():
        monkeypatch.setattr(risk_notice_card_ai, "llm_text_completion", fake_completion)
        db = AsyncMock()
        db.execute.return_value = MagicMock()
        with pytest.raises(HTTPException) as exc:
            await risk_notice_card_ai.review_signs(
                db, "u1", "测试公司", "会议室", "工作场所", "三楼",
                [{"accident_type": "火灾"}],
                [],
                [],
            )
        assert exc.value.status_code == 502
        assert "AI 返回格式异常" in exc.value.detail

    asyncio.run(run())


def test_review_signs_non_list_fields_fall_back(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    from app.services import risk_notice_card_ai

    async def fake_completion(messages, config, timeout=60):
        return '{"remove": "instruction-helmet", "add": null, "reasons": {}}'

    async def run():
        monkeypatch.setattr(risk_notice_card_ai, "llm_text_completion", fake_completion)
        db = AsyncMock()
        db.execute.return_value = MagicMock()
        result = await risk_notice_card_ai.review_signs(
            db, "u1", "测试公司", "会议室", "工作场所", "三楼",
            [{"accident_type": "火灾"}],
            [],
            [],
        )
        assert result["remove"] == []
        assert result["add"] == []
        assert result["reasons"] == []

    asyncio.run(run())


def test_snapshot_save_with_signs(client):
    """PUT /snapshot 的 content 含 signs 时，服务端按规则库规范化后持久化，
    signs_source 原样保留；库外 svg_name 被丢弃、按类别顺序重排。
    """
    ent = _enterprise()
    db = _risk_card_db(ent, [], detail_obj=_risk_object())
    client.app.dependency_overrides[get_db] = lambda: db

    resp = client.put(
        "/enterprises/e1/risk-notice-cards/o1/snapshot",
        json={
            "content": {
                "hazard_description": "x",
                "accident_types": ["火灾"],
                "control_measures": [],
                "emergency_measures": [],
                "signs": [
                    {"category": "prohibition", "name": "禁止烟火", "svg_name": "prohibition-smoking"},
                    {"category": "warning", "name": "当心火灾", "svg_name": "warning-fire"},
                    {"category": "warning", "name": "自造标志", "svg_name": "not-in-library"},
                ],
                "signs_source": "manual",
            }
        },
    )
    assert resp.status_code == 200
    saved = db.add.call_args.args[0]
    assert saved.content["signs"] == [
        {"category": "warning", "name": "当心火灾", "svg_name": "warning-fire"},
        {"category": "prohibition", "name": "禁止烟火", "svg_name": "prohibition-smoking"},
    ]
    assert saved.content["signs_source"] == "manual"


def test_snapshot_save_persists_explicit_empty_signs(client):
    """PUT /snapshot 的 content 含 signs: [] + signs_source=manual 时，显式空列表
    作为合法最终状态持久化（不回退规则标志、来源保持 manual）。"""
    ent = _enterprise()
    db = _risk_card_db(ent, [], detail_obj=_risk_object())
    client.app.dependency_overrides[get_db] = lambda: db

    resp = client.put(
        "/enterprises/e1/risk-notice-cards/o1/snapshot",
        json={
            "content": {
                "hazard_description": "x",
                "accident_types": ["火灾"],
                "control_measures": [],
                "emergency_measures": [],
                "signs": [],
                "signs_source": "manual",
            }
        },
    )
    assert resp.status_code == 200
    saved = db.add.call_args.args[0]
    assert saved.content["signs"] == []
    assert saved.content["signs_source"] == "manual"


def test_snapshot_save_invalid_sign_category_422(client):
    """写端点经 pydantic SignItem 严格校验：非法 category → 422。"""
    ent = _enterprise()
    client.app.dependency_overrides[get_db] = lambda: _risk_card_db(
        ent, [], detail_obj=_risk_object()
    )

    resp = client.put(
        "/enterprises/e1/risk-notice-cards/o1/snapshot",
        json={
            "content": {
                "hazard_description": "x",
                "accident_types": ["火灾"],
                "control_measures": [],
                "emergency_measures": [],
                "signs": [
                    {"category": "bogus", "name": "自造标志", "svg_name": "not-in-library"}
                ],
            }
        },
    )
    assert resp.status_code == 422


def test_snapshot_save_invalid_signs_source_falls_back_rule(client):
    """API 层非法 signs_source → 端到端回退 rule。"""
    ent = _enterprise()
    db = _risk_card_db(ent, [], detail_obj=_risk_object())
    client.app.dependency_overrides[get_db] = lambda: db

    resp = client.put(
        "/enterprises/e1/risk-notice-cards/o1/snapshot",
        json={
            "content": {
                "hazard_description": "x",
                "accident_types": ["火灾"],
                "control_measures": [],
                "emergency_measures": [],
                "signs": [
                    {"category": "warning", "name": "当心火灾", "svg_name": "warning-fire"}
                ],
                "signs_source": "not-a-valid-source",
            }
        },
    )
    assert resp.status_code == 200
    saved = db.add.call_args.args[0]
    assert saved.content["signs_source"] == "rule"
