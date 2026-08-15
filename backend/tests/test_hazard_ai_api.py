"""隐患排查治理任务 12 测试：AI 排查计划一键生成/排程建议/清单补全/智能引导。

测试风格与 tests/test_hazard_template_api.py / test_hazard_grade_api.py 一致：
无 db fixture，端点用 FastAPI TestClient + dependency_overrides + SQL 文本分发
mock；async 服务函数用 @pytest.mark.asyncio。

覆盖（四端点各：ok 结构断言 / LLM 异常降级 / 未配置降级跳过 LLM / 输入为空
422 / 返回结构非法降级；setup-wizard 三块结构断言 + 部分块失败整体仍可用）。
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.user import User
from app.routers import hazard_management
from app.services.hazard_ai_service import (
    build_inspection_plans,
    run_setup_wizard,
    suggest_checklist_items,
    suggest_schedule,
)


# ── mock 工具 ──

def _scalar(value):
    res = MagicMock()
    res.scalar_one_or_none.return_value = value
    return res


def _first(value):
    res = MagicMock()
    res.first.return_value = value
    return res


def _ent(**kw):
    e = Enterprise(id="e1", user_id="u1", name="甲公司", hazard_closure_mode="standard")
    for k, v in kw.items():
        setattr(e, k, v)
    return e


def _ai_db(ent, *, member=None):
    """AI 端点仅走 _get_ent（enterprises + enterprise_members），按 SQL 文本分发。"""
    db = AsyncMock()

    def fake_execute(stmt, *params):
        text = str(stmt)
        if "FROM enterprises" in text:
            return _scalar(ent)
        if "FROM enterprise_members" in text:
            return _first(member if member and getattr(member, "enabled", True) else None)
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
    app.dependency_overrides[get_db] = lambda: _ai_db(_ent())
    with TestClient(app) as test_client:
        yield test_client


# ── /ai/plan-builder：端点 ──

def test_plan_builder_success(client):
    db = _ai_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    fake = {
        "available": True,
        "plans": [{
            "name": "生产车间日排查", "category": "daily", "frequency": "daily",
            "responsible_user_name": "张三", "zone_names": ["生产车间"],
        }],
        "note": "",
    }
    with patch("app.routers.hazard_management._get_ai_config",
               AsyncMock(return_value=MagicMock())), \
         patch("app.routers.hazard_management.build_inspection_plans",
               AsyncMock(return_value=fake)) as mock_builder:
        resp = client.post("/enterprises/e1/hazard-inspection/ai/plan-builder",
                           json={"areas": "生产车间、储罐区", "frequency_preference": "每周一次"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["available"] is True
    assert data["plans"][0]["name"] == "生产车间日排查"
    assert data["plans"][0]["category"] == "daily"
    assert data["plans"][0]["responsible_user_name"] == "张三"
    assert mock_builder.await_count == 1
    assert mock_builder.await_args.args[:2] == ("生产车间、储罐区", "每周一次")


def test_plan_builder_blank_input_422(client):
    db = _ai_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/ai/plan-builder",
                       json={"areas": "   ", "frequency_preference": ""})
    assert resp.status_code == 422
    assert "不能为空" in resp.json()["detail"]


def test_plan_builder_no_config_degrades_200(client):
    db = _ai_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    fallback = {"available": False, "plans": [], "note": "AI 不可用，请手动创建排查计划"}
    with patch("app.routers.hazard_management._get_ai_config",
               AsyncMock(side_effect=HTTPException(400, "系统未配置 AI 模型，请联系管理员"))), \
         patch("app.routers.hazard_management.build_inspection_plans",
               AsyncMock(return_value=fallback)) as mock_builder:
        resp = client.post("/enterprises/e1/hazard-inspection/ai/plan-builder",
                           json={"areas": "生产车间", "frequency_preference": "每周"})
    assert resp.status_code == 200
    assert resp.json()["data"] == fallback
    assert mock_builder.await_count == 1
    assert mock_builder.await_args.args[2] is None  # 未配置 → ai_config=None 走服务兜底


def test_plan_builder_non_member_404(client):
    ent = _ent(user_id="u2")
    db = _ai_db(ent, member=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/ai/plan-builder",
                       json={"areas": "生产车间", "frequency_preference": "每周"})
    assert resp.status_code == 404


# ── /ai/plan-builder：服务层 ──

@pytest.mark.asyncio
async def test_build_inspection_plans_success_covers_categories():
    payload = {"plans": [
        {"name": "生产车间日排查", "category": "daily", "frequency": "daily",
         "responsible_user_name": "张三", "zone_names": ["生产车间"]},
        {"name": "月度综合大排查", "category": "comprehensive", "frequency": "monthly"},
        {"name": "节假日安全专项", "category": "holiday", "frequency": "custom",
         "weekdays": [6, 7], "zone_names": "全厂"},
    ]}
    raw = "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=raw)):
        out = await build_inspection_plans("生产车间、储罐区", "每周", MagicMock())
    assert out["available"] is True
    assert len(out["plans"]) == 3
    first = out["plans"][0]
    assert first["name"] == "生产车间日排查"
    assert first["category"] == "daily"
    assert first["frequency"] == "daily"
    assert first["responsible_user_name"] == "张三"
    assert first["zone_names"] == ["生产车间"]
    # 非 list 的 zone_names（"全厂"）类型非法 → 置空不降级
    assert out["plans"][2]["zone_names"] is None
    assert out["plans"][2]["weekdays"] == [6, 7]
    assert out["note"] == ""


@pytest.mark.asyncio
async def test_build_inspection_plans_caps_at_6():
    payload = {"plans": [
        {"name": f"计划{i}", "category": "daily", "frequency": "daily"} for i in range(8)
    ]}
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))):
        out = await build_inspection_plans("区域", "每周", MagicMock())
    assert out["available"] is True
    assert len(out["plans"]) == 6


@pytest.mark.asyncio
async def test_build_inspection_plans_too_few_degrades():
    payload = {"plans": [{"name": "唯一计划", "category": "daily", "frequency": "daily"}]}
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))):
        out = await build_inspection_plans("区域", "每周", MagicMock())
    assert out["available"] is False
    assert out["plans"] == []
    assert out["note"]


@pytest.mark.asyncio
async def test_build_inspection_plans_invalid_structure_degrades():
    # 字段缺（无 name）+ 类型错（category 非法码值）混合 → 全部无效 → 降级
    payload = {"plans": [
        {"category": "daily", "frequency": "daily"},
        {"name": "非法类别", "category": "boss", "frequency": "daily"},
    ]}
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))):
        out = await build_inspection_plans("区域", "每周", MagicMock())
    assert out["available"] is False
    assert out["plans"] == []


@pytest.mark.asyncio
async def test_build_inspection_plans_failure_degrades():
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(side_effect=Exception("timeout"))):
        out = await build_inspection_plans("区域", "每周", MagicMock())
    assert out["available"] is False
    assert out["plans"] == []
    assert out["note"]


@pytest.mark.asyncio
async def test_build_inspection_plans_invalid_json_degrades():
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value="not a json")):
        out = await build_inspection_plans("区域", "每周", MagicMock())
    assert out["available"] is False


@pytest.mark.asyncio
async def test_build_inspection_plans_no_config_skips_llm():
    with patch("app.services.hazard_ai_service.llm_text_completion", AsyncMock()) as mock_llm:
        out = await build_inspection_plans("区域", "每周", None)
    assert out["available"] is False
    assert out["plans"] == []
    mock_llm.assert_not_awaited()


# ── /ai/schedule-suggestion：端点 ──

def test_schedule_suggestion_success(client):
    db = _ai_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    fake = {"available": True, "suggested_frequency": "weekly",
            "suggested_responsible_user_id": "u-001", "reason": "风险高发", "note": ""}
    with patch("app.routers.hazard_management._get_ai_config",
               AsyncMock(return_value=MagicMock())), \
         patch("app.routers.hazard_management.suggest_schedule",
               AsyncMock(return_value=fake)) as mock_schedule:
        resp = client.post("/enterprises/e1/hazard-inspection/ai/schedule-suggestion",
                           json={"plan_draft": "生产车间周排查", "zone_risk_hints": "高风险",
                                 "history_hints": "近三月 5 起"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["available"] is True
    assert data["suggested_frequency"] == "weekly"
    assert data["suggested_responsible_user_id"] == "u-001"
    assert data["reason"]
    assert mock_schedule.await_count == 1
    assert mock_schedule.await_args.args[0] == "生产车间周排查"
    assert mock_schedule.await_args.kwargs == {"zone_risk_hints": "高风险", "history_hints": "近三月 5 起"}


def test_schedule_suggestion_blank_plan_draft_422(client):
    db = _ai_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/ai/schedule-suggestion",
                       json={"plan_draft": "   "})
    assert resp.status_code == 422
    assert "plan_draft 不能为空" in resp.json()["detail"]


def test_schedule_suggestion_no_config_degrades_200(client):
    db = _ai_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    fallback = {"available": False, "suggested_frequency": "",
                "suggested_responsible_user_id": None, "reason": "",
                "note": "AI 不可用，请手动设置排程"}
    with patch("app.routers.hazard_management._get_ai_config",
               AsyncMock(side_effect=HTTPException(400, "系统未配置 AI 模型，请联系管理员"))), \
         patch("app.routers.hazard_management.suggest_schedule",
               AsyncMock(return_value=fallback)) as mock_schedule:
        resp = client.post("/enterprises/e1/hazard-inspection/ai/schedule-suggestion",
                           json={"plan_draft": "生产车间周排查"})
    assert resp.status_code == 200
    assert resp.json()["data"] == fallback
    assert mock_schedule.await_count == 1
    assert mock_schedule.await_args.args[1] is None


def test_schedule_suggestion_non_member_404(client):
    ent = _ent(user_id="u2")
    db = _ai_db(ent, member=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/ai/schedule-suggestion",
                       json={"plan_draft": "生产车间周排查"})
    assert resp.status_code == 404


# ── /ai/schedule-suggestion：服务层 ──

@pytest.mark.asyncio
async def test_suggest_schedule_success_with_user():
    payload = {"suggested_frequency": "weekly", "suggested_responsible_user_id": "u-001",
               "reason": "分区高风险且历史隐患集中"}
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))) as mock_llm:
        out = await suggest_schedule("生产车间周排查", MagicMock(),
                                     zone_risk_hints="高风险", history_hints="月均 2 起")
    assert out["available"] is True
    assert out["suggested_frequency"] == "weekly"
    assert out["suggested_responsible_user_id"] == "u-001"
    assert out["reason"] == "分区高风险且历史隐患集中"
    assert out["note"] == ""
    prompt = mock_llm.await_args.args[0][1]["content"]
    assert "高风险" in prompt
    assert "月均 2 起" in prompt


@pytest.mark.asyncio
async def test_suggest_schedule_null_user_with_reason():
    payload = {"suggested_frequency": "monthly", "suggested_responsible_user_id": None,
               "reason": "草稿未指定责任人，请确认后指派"}
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))):
        out = await suggest_schedule("生产车间月排查", MagicMock())
    assert out["available"] is True
    assert out["suggested_frequency"] == "monthly"
    assert out["suggested_responsible_user_id"] is None
    assert out["reason"]


@pytest.mark.asyncio
async def test_suggest_schedule_invalid_frequency_degrades():
    payload = {"suggested_frequency": "annually", "suggested_responsible_user_id": "u-001",
               "reason": "每年一次"}
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))):
        out = await suggest_schedule("计划草稿", MagicMock())
    assert out["available"] is False
    assert out["suggested_frequency"] == ""
    assert out["reason"] == ""


@pytest.mark.asyncio
async def test_suggest_schedule_missing_reason_degrades():
    payload = {"suggested_frequency": "daily", "suggested_responsible_user_id": None,
               "reason": "   "}
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))):
        out = await suggest_schedule("计划草稿", MagicMock())
    assert out["available"] is False
    assert out["suggested_responsible_user_id"] is None


@pytest.mark.asyncio
async def test_suggest_schedule_failure_degrades():
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(side_effect=Exception("timeout"))):
        out = await suggest_schedule("计划草稿", MagicMock())
    assert out["available"] is False
    assert out["note"]


@pytest.mark.asyncio
async def test_suggest_schedule_no_config_skips_llm():
    with patch("app.services.hazard_ai_service.llm_text_completion", AsyncMock()) as mock_llm:
        out = await suggest_schedule("计划草稿", None)
    assert out["available"] is False
    assert out["suggested_frequency"] == ""
    mock_llm.assert_not_awaited()


# ── /ai/checklist：端点 ──

def test_checklist_success(client):
    db = _ai_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    fake = {"available": True, "items": [{"content": "检查消防通道", "expected_note": "畅通"}],
            "note": ""}
    with patch("app.routers.hazard_management._get_ai_config",
               AsyncMock(return_value=MagicMock())), \
         patch("app.routers.hazard_management.suggest_checklist_items",
               AsyncMock(return_value=fake)) as mock_checklist:
        resp = client.post("/enterprises/e1/hazard-inspection/ai/checklist",
                           json={"task_context": "生产车间日排查：通道/灭火器"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["available"] is True
    assert data["items"] == [{"content": "检查消防通道", "expected_note": "畅通"}]
    assert mock_checklist.await_count == 1
    assert mock_checklist.await_args.args[0] == "生产车间日排查：通道/灭火器"


def test_checklist_blank_context_422(client):
    db = _ai_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/ai/checklist",
                       json={"task_context": "  "})
    assert resp.status_code == 422
    assert "task_context 不能为空" in resp.json()["detail"]


def test_checklist_no_config_degrades_200(client):
    db = _ai_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    fallback = {"available": False, "items": [], "note": "AI 不可用，请使用既有检查项"}
    with patch("app.routers.hazard_management._get_ai_config",
               AsyncMock(side_effect=HTTPException(400, "系统未配置 AI 模型，请联系管理员"))), \
         patch("app.routers.hazard_management.suggest_checklist_items",
               AsyncMock(return_value=fallback)) as mock_checklist:
        resp = client.post("/enterprises/e1/hazard-inspection/ai/checklist",
                           json={"task_context": "生产车间日排查"})
    assert resp.status_code == 200
    assert resp.json()["data"] == fallback
    assert mock_checklist.await_count == 1
    assert mock_checklist.await_args.args[1] is None


def test_checklist_non_member_404(client):
    ent = _ent(user_id="u2")
    db = _ai_db(ent, member=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/ai/checklist",
                       json={"task_context": "生产车间日排查"})
    assert resp.status_code == 404


# ── /ai/checklist：服务层 ──

@pytest.mark.asyncio
async def test_suggest_checklist_items_success():
    payload = {"items": [{"content": "检查灭火器压力", "expected_note": "指针在绿区"},
                         {"content": "无标准项"}]}
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))):
        out = await suggest_checklist_items("生产车间日排查", MagicMock())
    assert out["available"] is True
    assert len(out["items"]) == 2
    assert out["items"][0] == {"content": "检查灭火器压力", "expected_note": "指针在绿区"}
    assert out["items"][1]["expected_note"] is None
    assert out["note"] == ""


@pytest.mark.asyncio
async def test_suggest_checklist_items_caps_at_8():
    payload = {"items": [{"content": f"检查项{i}", "expected_note": ""} for i in range(12)]}
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))):
        out = await suggest_checklist_items("任务上下文", MagicMock())
    assert out["available"] is True
    assert len(out["items"]) == 8


@pytest.mark.asyncio
async def test_suggest_checklist_items_empty_degrades():
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value='{"items": []}')):
        out = await suggest_checklist_items("任务上下文", MagicMock())
    assert out["available"] is False
    assert out["items"] == []
    assert out["note"]


@pytest.mark.asyncio
async def test_suggest_checklist_items_failure_degrades():
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(side_effect=Exception("timeout"))):
        out = await suggest_checklist_items("任务上下文", MagicMock())
    assert out["available"] is False
    assert out["items"] == []


@pytest.mark.asyncio
async def test_suggest_checklist_items_no_config_skips_llm():
    with patch("app.services.hazard_ai_service.llm_text_completion", AsyncMock()) as mock_llm:
        out = await suggest_checklist_items("任务上下文", None)
    assert out["available"] is False
    assert out["items"] == []
    mock_llm.assert_not_awaited()


# ── /ai/setup-wizard：端点 ──

def test_setup_wizard_success_three_blocks(client):
    db = _ai_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    fake = {
        "available": True,
        "org_suggestion": {"available": True, "nodes": [
            {"id": "n1", "type": "dept", "name": "生产部", "parent_id": None, "members": []}]},
        "plans_suggestion": {"available": True, "plans": [
            {"name": "生产车间日排查", "category": "daily", "frequency": "daily"}]},
        "checklist_suggestion": {"available": True, "items": [
            {"content": "检查通道", "expected_note": "畅通"}]},
        "note": "",
    }
    with patch("app.routers.hazard_management._get_ai_config",
               AsyncMock(return_value=MagicMock())), \
         patch("app.routers.hazard_management.run_setup_wizard",
               AsyncMock(return_value=fake)) as mock_wizard:
        resp = client.post("/enterprises/e1/hazard-inspection/ai/setup-wizard",
                           json={"industry": "化工", "areas": "生产车间、储罐区",
                                 "employee_count": "200", "frequency_preference": "每周"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["available"] is True
    assert data["org_suggestion"]["available"] is True
    assert data["org_suggestion"]["nodes"][0]["name"] == "生产部"
    assert data["plans_suggestion"]["available"] is True
    assert data["plans_suggestion"]["plans"][0]["category"] == "daily"
    assert data["checklist_suggestion"]["available"] is True
    assert data["checklist_suggestion"]["items"][0]["content"] == "检查通道"
    assert mock_wizard.await_count == 1
    assert mock_wizard.await_args.args[:2] == ("化工", "生产车间、储罐区")
    assert mock_wizard.await_args.args[2] == "200"  # 空串归一化为 None 后传参


def test_setup_wizard_blank_industry_or_areas_422(client):
    db = _ai_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/ai/setup-wizard",
                       json={"industry": "  ", "areas": ""})
    assert resp.status_code == 422
    assert "不能为空" in resp.json()["detail"]


def test_setup_wizard_no_config_degrades_200(client):
    db = _ai_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    fallback = {"available": False,
                "org_suggestion": {"available": False, "note": "AI 不可用，请手动维护组织架构"},
                "plans_suggestion": {"available": False, "plans": [],
                                     "note": "AI 不可用，请手动创建排查计划"},
                "checklist_suggestion": {"available": False, "items": [],
                                         "note": "AI 不可用，请使用既有检查项"},
                "note": "AI 不可用，请手动完成初始配置"}
    with patch("app.routers.hazard_management._get_ai_config",
               AsyncMock(side_effect=HTTPException(400, "系统未配置 AI 模型，请联系管理员"))), \
         patch("app.routers.hazard_management.run_setup_wizard",
               AsyncMock(return_value=fallback)) as mock_wizard:
        resp = client.post("/enterprises/e1/hazard-inspection/ai/setup-wizard",
                           json={"industry": "化工", "areas": "生产车间"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["available"] is False
    assert data["org_suggestion"]["available"] is False
    assert data["plans_suggestion"]["plans"] == []
    assert data["checklist_suggestion"]["items"] == []
    assert mock_wizard.await_count == 1
    assert mock_wizard.await_args.args[4] is None


def test_setup_wizard_non_member_404(client):
    ent = _ent(user_id="u2")
    db = _ai_db(ent, member=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/ai/setup-wizard",
                       json={"industry": "化工", "areas": "生产车间"})
    assert resp.status_code == 404


# ── /ai/setup-wizard：服务层（三块复用既有服务函数） ──

def _org_block():
    return {"available": True, "nodes": [
        {"id": "n1", "type": "dept", "name": "生产部", "parent_id": None, "members": []}]}


def _plans_block():
    return {"available": True, "plans": [
        {"name": "生产车间日排查", "category": "daily", "frequency": "daily"}]}


def _checklist_block():
    return {"available": True, "items": [{"content": "检查通道", "expected_note": "畅通"}]}


@pytest.mark.asyncio
async def test_run_setup_wizard_success_three_blocks():
    with patch("app.services.hazard_ai_service.suggest_org_tree",
               AsyncMock(return_value=_org_block())) as mock_org, \
         patch("app.services.hazard_ai_service.build_inspection_plans",
               AsyncMock(return_value=_plans_block())) as mock_plans, \
         patch("app.services.hazard_ai_service.generate_checklist_template",
               AsyncMock(return_value=_checklist_block())) as mock_tpl:
        out = await run_setup_wizard("化工", "生产车间、储罐区", "200", "每周", MagicMock())
    assert out["available"] is True
    assert out["org_suggestion"] == _org_block()
    assert out["plans_suggestion"] == _plans_block()
    assert out["checklist_suggestion"] == _checklist_block()
    assert out["note"] == ""
    # 直接复用既有服务函数：三个都被调用一次
    assert mock_org.await_count == 1
    assert mock_plans.await_count == 1
    assert mock_tpl.await_count == 1
    assert mock_org.await_args.args[0] == {"industry": "化工", "employee_count": "200"}
    assert mock_plans.await_args.args[:2] == ("生产车间、储罐区", "每周")
    assert mock_tpl.await_args.args[:2] == ("化工", "生产车间、储罐区")


@pytest.mark.asyncio
async def test_run_setup_wizard_partial_block_failure_still_available():
    with patch("app.services.hazard_ai_service.suggest_org_tree",
               AsyncMock(return_value=_org_block())), \
         patch("app.services.hazard_ai_service.build_inspection_plans",
               AsyncMock(return_value={"available": False, "plans": [], "note": "AI 不可用"})), \
         patch("app.services.hazard_ai_service.generate_checklist_template",
               AsyncMock(side_effect=Exception("timeout"))):
        out = await run_setup_wizard("化工", "生产车间", None, None, MagicMock())
    assert out["available"] is True  # 组织块可用 → 向导整体可用，前端分块显示
    assert out["org_suggestion"]["available"] is True
    assert out["plans_suggestion"]["available"] is False
    assert out["checklist_suggestion"]["available"] is False


@pytest.mark.asyncio
async def test_run_setup_wizard_all_blocks_fail_degrades():
    with patch("app.services.hazard_ai_service.suggest_org_tree",
               AsyncMock(return_value={"available": False, "note": "AI 不可用"})), \
         patch("app.services.hazard_ai_service.build_inspection_plans",
               AsyncMock(return_value={"available": False, "plans": [], "note": "AI 不可用"})), \
         patch("app.services.hazard_ai_service.generate_checklist_template",
               AsyncMock(return_value={"available": False, "items": [], "note": "AI 不可用"})):
        out = await run_setup_wizard("化工", "生产车间", None, None, MagicMock())
    assert out["available"] is False
    assert out["org_suggestion"]["available"] is False
    assert out["plans_suggestion"]["plans"] == []
    assert out["checklist_suggestion"]["items"] == []
    assert out["note"]


@pytest.mark.asyncio
async def test_run_setup_wizard_no_config_skips_llm():
    with patch("app.services.hazard_ai_service.suggest_org_tree", AsyncMock()) as mock_org, \
         patch("app.services.hazard_ai_service.build_inspection_plans", AsyncMock()) as mock_plans, \
         patch("app.services.hazard_ai_service.generate_checklist_template", AsyncMock()) as mock_tpl:
        out = await run_setup_wizard("化工", "生产车间", None, None, None)
    assert out["available"] is False
    assert out["org_suggestion"]["available"] is False
    assert out["plans_suggestion"]["available"] is False
    assert out["checklist_suggestion"]["available"] is False
    mock_org.assert_not_awaited()
    mock_plans.assert_not_awaited()
    mock_tpl.assert_not_awaited()
