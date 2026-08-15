"""隐患排查治理任务 6 测试：分级确认 / 重大挂牌审批 / AI 分级建议 / AI 治理方案草稿。

测试风格与 tests/test_hazard_record_api.py / test_hazard_plan_api.py 一致：
无 db fixture，端点用 FastAPI TestClient + dependency_overrides + SQL 文本分发
mock；async 服务函数用 @pytest.mark.asyncio。

覆盖：
- grade 成功（一般→rectifying / 重大→pending_approval）、level 非法 422、
  重大缺 grading_basis/治理方案 422、rectification_user_id 非启用成员 422、
  非 admin 403、非本企业 404、deadline 按字典天数计算、level_source 落库
- approve 成功（写 HazardApproval+audit、状态 rectifying、可设置整改责任人、
  已设可省略）、非 pending_approval 409、非 admin 403；reject 可选实现
  （任务 6 顺手实现：pending_approval→grading，写 reject 审批记录）
- AI grade 成功（建议等级/依据/confidence）与降级（未配置/异常/非法返回）
- AI governance-plan 成功五键与降级
"""

import json
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.data_dict import DataDict
from app.models.enterprise import Enterprise
from app.models.enterprise_org import EnterpriseMember
from app.models.hazard_management import HazardApproval, HazardAuditLog, HazardRecord
from app.models.user import User
from app.routers import hazard_management
from app.services.data_dict_service import invalidate_dict_cache
from app.services.hazard_ai_service import JUDGMENT_POINTS, ai_grade, ai_governance_plan


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


def _ent(**kw):
    e = Enterprise(id="e1", user_id="u1", name="甲公司", hazard_closure_mode="standard")
    for k, v in kw.items():
        setattr(e, k, v)
    return e


def _record(**kw):
    r = HazardRecord(
        id=kw.pop("id", "r1"),
        enterprise_id=kw.pop("enterprise_id", "e1"),
        code=kw.pop("code", "HD-001"),
        source_type=kw.pop("source_type", "report"),
        title=kw.pop("title", "配电箱门破损"),
        description=kw.pop("description", "配电箱门变形无法闭合"),
        status=kw.pop("status", "registered"),
    )
    for k, v in kw.items():
        setattr(r, k, v)
    return r


def _deadline_row(code, days):
    return DataDict(dict_type="deadline_rules", code=code, label=f"{code}期限",
                    value={"days": days}, scope="system", enabled=True, is_system=True)


def _hazard_type_row(code):
    return DataDict(dict_type="hazard_type", code=code, label=f"类型{code}",
                    value={}, scope="system", enabled=True, is_system=True)


def _grade_db(ent, *, admin_member=None, member=None, record=None, dict_rows=None):
    """按 SQL 文本特征分发（参照 test_hazard_record_api.py 的 _record_db）。"""
    db = AsyncMock()
    db.added = []

    def fake_add(obj):
        db.added.append(obj)

    db.add = MagicMock(side_effect=fake_add)

    def fake_execute(stmt, *params):
        text = str(stmt)
        if "FROM enterprises" in text:
            return _scalar(ent)
        if "FROM enterprise_members" in text:
            if "enterprise_members.role" in text:
                return _first(admin_member if admin_member and getattr(admin_member, "enabled", True) else None)
            return _first(member if member and getattr(member, "enabled", True) else None)
        if "FROM data_dicts" in text:
            return _scalars(dict_rows or [])
        if "FROM hazard_records" in text:
            return _scalar(record)
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
    app.dependency_overrides[get_db] = lambda: _grade_db(_ent(), record=_record())
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _clear_dict_cache():
    """每个测试结束后清空数据字典进程内缓存，避免污染同进程其他测试模块。"""
    yield
    invalidate_dict_cache()


_PLAN = {
    "goal": "消除配电箱触电隐患",
    "measures": "更换箱门并加锁",
    "budget": "2000元",
    "emergency_measures": "临时隔离并设置警示",
    "acceptance_criteria": "门体完好、锁具正常、绝缘测试合格",
}


# ── grade：成功路径 ──

def test_grade_general_success_deadline_from_dict(client):
    invalidate_dict_cache("e1", "deadline_rules")
    rec = _record()
    db = _grade_db(_ent(), record=rec,
                   dict_rows=[_deadline_row("major", 15), _deadline_row("general", 7)])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/grade",
                       json={"level": "general", "grading_basis": "一般设施缺陷"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert resp.json()["code"] == 0
    assert data["status"] == "rectifying"
    assert data["level"] == "general"
    assert data["level_source"] == "manual"  # 缺省默认 manual
    assert data["deadline"] == (date.today() + timedelta(days=7)).isoformat()
    assert rec.rectification_plan == {}
    db.commit.assert_awaited()


def test_grade_major_success_pending_approval(client):
    invalidate_dict_cache("e1", "deadline_rules")
    invalidate_dict_cache("e1", "hazard_type")
    rec = _record()
    db = _grade_db(_ent(), member=MagicMock(), record=rec,
                   dict_rows=[_deadline_row("major", 15), _deadline_row("general", 7),
                              _hazard_type_row("fire"), _hazard_type_row("equipment")])
    client.app.dependency_overrides[get_db] = lambda: db
    body = {"level": "major", "grading_basis": "符合危化品储运判定要点",
            "hazard_type": "fire", "rectification_plan": _PLAN,
            "rectification_user_id": "u7", "level_source": "ai"}
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/grade", json=body)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "pending_approval"
    assert data["level"] == "major"
    assert data["level_source"] == "ai"  # level_source 落库
    assert data["hazard_type"] == "fire"
    assert data["deadline"] == (date.today() + timedelta(days=15)).isoformat()
    assert rec.grading_basis == "符合危化品储运判定要点"
    assert rec.rectification_user_id == "u7"
    assert rec.rectification_plan == _PLAN
    db.commit.assert_awaited()


def test_grade_admin_member_allowed(client):
    invalidate_dict_cache("e1", "deadline_rules")
    ent = _ent(user_id="u2")
    admin = EnterpriseMember(id="m2", enterprise_id="e1", user_id="u1",
                             role="enterprise_admin", enabled=True)
    rec = _record()
    db = _grade_db(ent, admin_member=admin, record=rec,
                   dict_rows=[_deadline_row("general", 7)])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/grade",
                       json={"level": "general"})
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "rectifying"


# ── grade：字段/权限/归属校验 ──

def test_grade_invalid_level_422(client):
    invalidate_dict_cache("e1", "deadline_rules")
    db = _grade_db(_ent(), record=_record(), dict_rows=[_deadline_row("general", 7)])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/grade",
                       json={"level": "huge"})
    assert resp.status_code == 422
    assert "level" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_grade_major_missing_grading_basis_422(client):
    invalidate_dict_cache("e1", "deadline_rules")
    db = _grade_db(_ent(), record=_record(), dict_rows=[_deadline_row("major", 15)])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/grade",
                       json={"level": "major", "grading_basis": "   "})
    assert resp.status_code == 422
    assert "判定依据" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_grade_major_missing_rectification_plan_422(client):
    invalidate_dict_cache("e1", "deadline_rules")
    db = _grade_db(_ent(), record=_record(), dict_rows=[_deadline_row("major", 15)])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/grade",
                       json={"level": "major", "grading_basis": "依据 A"})
    assert resp.status_code == 422
    assert "治理方案" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_grade_major_incomplete_plan_422(client):
    invalidate_dict_cache("e1", "deadline_rules")
    db = _grade_db(_ent(), record=_record(), dict_rows=[_deadline_row("major", 15)])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/grade",
                       json={"level": "major", "grading_basis": "依据 A",
                             "rectification_plan": {"goal": "目标"}})
    assert resp.status_code == 422
    assert "治理方案" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_grade_rectification_user_not_enabled_member_422(client):
    invalidate_dict_cache("e1", "deadline_rules")
    db = _grade_db(_ent(), member=None, record=_record(), dict_rows=[_deadline_row("general", 7)])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/grade",
                       json={"level": "general", "rectification_user_id": "u7"})
    assert resp.status_code == 422
    assert "启用成员" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_grade_hazard_type_not_in_dict_422(client):
    invalidate_dict_cache("e1", "deadline_rules")
    invalidate_dict_cache("e1", "hazard_type")
    db = _grade_db(_ent(), record=_record(),
                   dict_rows=[_deadline_row("general", 7), _hazard_type_row("fire")])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/grade",
                       json={"level": "general", "hazard_type": "mechanical"})
    assert resp.status_code == 422
    assert "hazard_type 非法" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_grade_invalid_level_source_422(client):
    invalidate_dict_cache("e1", "deadline_rules")
    db = _grade_db(_ent(), record=_record(), dict_rows=[_deadline_row("general", 7)])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/grade",
                       json={"level": "general", "level_source": "auto"})
    assert resp.status_code == 422
    assert "level_source" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_grade_non_admin_403(client):
    invalidate_dict_cache("e1", "deadline_rules")
    ent = _ent(user_id="u2")
    plain = EnterpriseMember(id="m1", enterprise_id="e1", user_id="u1",
                             role="member", enabled=True)
    db = _grade_db(ent, admin_member=None, member=plain, record=_record(),
                   dict_rows=[_deadline_row("general", 7)])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/grade",
                       json={"level": "general"})
    assert resp.status_code == 403
    db.commit.assert_not_awaited()


def test_grade_non_member_403(client):
    invalidate_dict_cache("e1", "deadline_rules")
    ent = _ent(user_id="u2")
    db = _grade_db(ent, admin_member=None, member=None, record=_record(),
                   dict_rows=[_deadline_row("general", 7)])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/grade",
                       json={"level": "general"})
    assert resp.status_code == 403
    db.commit.assert_not_awaited()


def test_grade_record_not_in_enterprise_404(client):
    invalidate_dict_cache("e1", "deadline_rules")
    db = _grade_db(_ent(), record=None, dict_rows=[_deadline_row("general", 7)])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r9/grade",
                       json={"level": "general"})
    assert resp.status_code == 404
    assert "隐患记录不存在" in resp.json()["detail"]
    db.commit.assert_not_awaited()


# ── approve：成功路径 ──

def test_approve_success_writes_approval_and_audit(client):
    rec = _record(status="pending_approval", level="major")
    db = _grade_db(_ent(), member=MagicMock(), record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/approve",
                       json={"comment": "同意挂牌", "rectification_user_id": "u7"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "rectifying"
    assert rec.rectification_user_id == "u7"
    added = db.added
    assert any(isinstance(x, HazardApproval) and x.action == "approve"
               and x.comment == "同意挂牌" for x in added)
    assert any(isinstance(x, HazardAuditLog) and x.action == "approve" for x in added)
    db.commit.assert_awaited()


def test_approve_keeps_grade_rectifier_when_omitted(client):
    rec = _record(status="pending_approval", level="major", rectification_user_id="u7")
    db = _grade_db(_ent(), record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/approve",
                       json={"comment": "同意挂牌"})
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "rectifying"
    assert rec.rectification_user_id == "u7"  # grade 已设，approve 可省略


def test_approve_admin_member_allowed(client):
    ent = _ent(user_id="u2")
    admin = EnterpriseMember(id="m2", enterprise_id="e1", user_id="u1",
                             role="enterprise_admin", enabled=True)
    rec = _record(status="pending_approval", level="major")
    db = _grade_db(ent, admin_member=admin, record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/approve",
                       json={"comment": "同意挂牌"})
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "rectifying"


# ── approve：状态/权限校验 ──

def test_approve_not_pending_approval_409(client):
    rec = _record(status="rectifying", level="major")
    db = _grade_db(_ent(), record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/approve",
                       json={"comment": "同意挂牌"})
    assert resp.status_code == 409
    assert "pending_approval" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_approve_non_admin_403(client):
    ent = _ent(user_id="u2")
    rec = _record(status="pending_approval", level="major")
    db = _grade_db(ent, admin_member=None, member=None, record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/approve",
                       json={"comment": "同意挂牌"})
    assert resp.status_code == 403
    db.commit.assert_not_awaited()


def test_approve_invalid_rectification_user_422(client):
    rec = _record(status="pending_approval", level="major")
    db = _grade_db(_ent(), member=None, record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/approve",
                       json={"rectification_user_id": "u9"})
    assert resp.status_code == 422
    assert "启用成员" in resp.json()["detail"]
    db.commit.assert_not_awaited()


# ── reject（任务 6 顺手实现，契约允许并说明） ──

def test_reject_goes_grading_and_writes_approval(client):
    rec = _record(status="pending_approval", level="major")
    db = _grade_db(_ent(), record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/reject",
                       json={"comment": "治理方案不完整"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "grading"
    added = db.added
    assert any(isinstance(x, HazardApproval) and x.action == "reject"
               and x.comment == "治理方案不完整" for x in added)
    assert any(isinstance(x, HazardAuditLog) and x.action == "reject" for x in added)
    db.commit.assert_awaited()


def test_reject_not_pending_approval_409(client):
    rec = _record(status="registered", level=None)
    db = _grade_db(_ent(), record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/reject",
                       json={"comment": "驳回"})
    assert resp.status_code == 409
    db.commit.assert_not_awaited()


# ── AI grade：端点 ──

def test_ai_grade_success(client):
    db = _grade_db(_ent(), record=None)
    client.app.dependency_overrides[get_db] = lambda: db
    fake = {"available": True, "suggested_level": "major", "basis": "符合危化品储运要点",
            "confidence": 85, "note": ""}
    with patch("app.routers.hazard_management._get_ai_config",
               AsyncMock(return_value=MagicMock())), \
         patch("app.routers.hazard_management.ai_grade",
               AsyncMock(return_value=fake)) as mock_grade:
        resp = client.post("/enterprises/e1/hazard-inspection/ai/grade",
                           json={"description": "储罐超压运行", "judgment_points": "自定义要点",
                                 "measures_text": "无联锁"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["available"] is True
    assert data["suggested_level"] == "major"
    assert data["basis"]
    assert data["confidence"] == 85
    assert mock_grade.await_count == 1
    assert mock_grade.await_args.args[0] == "储罐超压运行"
    assert mock_grade.await_args.kwargs == {"judgment_points": "自定义要点", "measures_text": "无联锁"}


def test_ai_grade_blank_description_422(client):
    db = _grade_db(_ent(), record=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/ai/grade",
                       json={"description": "   "})
    assert resp.status_code == 422
    assert "description 不能为空" in resp.json()["detail"]


def test_ai_grade_no_config_degrades_200(client):
    db = _grade_db(_ent(), record=None)
    client.app.dependency_overrides[get_db] = lambda: db
    fallback = {"available": False, "suggested_level": "", "basis": "",
                "confidence": 0, "note": "AI 不可用，请手动判定隐患等级"}
    with patch("app.routers.hazard_management._get_ai_config",
               AsyncMock(side_effect=HTTPException(400, "系统未配置 AI 模型，请联系管理员"))), \
         patch("app.routers.hazard_management.ai_grade",
               AsyncMock(return_value=fallback)) as mock_grade:
        resp = client.post("/enterprises/e1/hazard-inspection/ai/grade",
                           json={"description": "储罐超压运行"})
    assert resp.status_code == 200
    assert resp.json()["data"] == fallback
    assert mock_grade.await_count == 1
    assert mock_grade.await_args.args[1] is None  # 未配置 → ai_config=None 走服务兜底


def test_ai_grade_non_member_404(client):
    ent = _ent(user_id="u2")
    db = _grade_db(ent, member=None, record=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/ai/grade",
                       json={"description": "储罐超压运行"})
    assert resp.status_code == 404


# ── AI grade：服务层 ──

@pytest.mark.asyncio
async def test_ai_grade_success_parses_fence_and_uses_default_points():
    payload = {"suggested_level": "major", "basis": "符合危化品储运判定要点", "confidence": 88}
    raw = "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=raw)) as mock_llm:
        out = await ai_grade("储罐超压运行", MagicMock())
    assert out["available"] is True
    assert out["suggested_level"] == "major"
    assert out["basis"] == "符合危化品储运判定要点"
    assert out["confidence"] == 88
    assert out["note"] == ""
    # 未传判定要点时 prompt 使用内置 JUDGMENT_POINTS 常量
    prompt = mock_llm.await_args.args[0][1]["content"]
    assert JUDGMENT_POINTS in prompt


@pytest.mark.asyncio
async def test_ai_grade_uses_custom_judgment_points_and_measures():
    payload = {"suggested_level": "general", "basis": "未达重大情形", "confidence": 60}
    custom = "自定义企业判定要点"
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))) as mock_llm:
        out = await ai_grade("描述", MagicMock(), judgment_points=custom, measures_text="措施A")
    assert out["available"] is True
    prompt = mock_llm.await_args.args[0][1]["content"]
    assert custom in prompt
    assert "措施A" in prompt
    assert JUDGMENT_POINTS not in prompt  # 自定义要点覆盖内置默认


@pytest.mark.asyncio
async def test_ai_grade_invalid_level_degrades():
    payload = {"suggested_level": "特别重大", "basis": "依据", "confidence": 90}
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))):
        out = await ai_grade("描述", MagicMock())
    assert out["available"] is False
    assert out["suggested_level"] == ""
    assert out["basis"] == ""


@pytest.mark.asyncio
async def test_ai_grade_empty_basis_degrades():
    payload = {"suggested_level": "major", "basis": "  ", "confidence": 90}
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))):
        out = await ai_grade("描述", MagicMock())
    assert out["available"] is False
    assert out["basis"] == ""


@pytest.mark.asyncio
async def test_ai_grade_failure_degrades():
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(side_effect=Exception("timeout"))):
        out = await ai_grade("描述", MagicMock())
    assert out["available"] is False
    assert out["note"]


@pytest.mark.asyncio
async def test_ai_grade_invalid_json_degrades():
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value="not a json")):
        out = await ai_grade("描述", MagicMock())
    assert out["available"] is False


@pytest.mark.asyncio
async def test_ai_grade_confidence_clamped_and_defaulted():
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(
                   {"suggested_level": "general", "basis": "依据", "confidence": 150},
                   ensure_ascii=False))):
        out = await ai_grade("描述", MagicMock())
    assert out["confidence"] == 100
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(
                   {"suggested_level": "general", "basis": "依据"},
                   ensure_ascii=False))):
        out = await ai_grade("描述", MagicMock())
    assert out["available"] is True
    assert out["confidence"] == 0


@pytest.mark.asyncio
async def test_ai_grade_no_config_skips_llm():
    with patch("app.services.hazard_ai_service.llm_text_completion", AsyncMock()) as mock_llm:
        out = await ai_grade("描述", None)
    assert out["available"] is False
    assert out["suggested_level"] == ""
    mock_llm.assert_not_awaited()


# ── AI governance-plan：端点 ──

def test_ai_governance_plan_success(client):
    db = _grade_db(_ent(), record=None)
    client.app.dependency_overrides[get_db] = lambda: db
    fake = {"available": True,
            "plan": {"goal": "消除隐患", "measures": "更换设备", "budget": "2万元",
                     "emergency_measures": "临时停用", "acceptance_criteria": "复测合格"},
            "note": ""}
    with patch("app.routers.hazard_management._get_ai_config",
               AsyncMock(return_value=MagicMock())), \
         patch("app.routers.hazard_management.ai_governance_plan",
               AsyncMock(return_value=fake)) as mock_plan:
        resp = client.post("/enterprises/e1/hazard-inspection/ai/governance-plan",
                           json={"description": "储罐超压运行", "measures_text": "无联锁"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["available"] is True
    assert set(data["plan"].keys()) == {"goal", "measures", "budget",
                                        "emergency_measures", "acceptance_criteria"}
    assert all(data["plan"].values())
    assert mock_plan.await_count == 1
    assert mock_plan.await_args.args[0] == "储罐超压运行"
    assert mock_plan.await_args.kwargs == {"judgment_points": None, "measures_text": "无联锁"}


def test_ai_governance_plan_blank_description_422(client):
    db = _grade_db(_ent(), record=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/ai/governance-plan",
                       json={"description": "   "})
    assert resp.status_code == 422
    assert "description 不能为空" in resp.json()["detail"]


def test_ai_governance_plan_no_config_degrades_200(client):
    db = _grade_db(_ent(), record=None)
    client.app.dependency_overrides[get_db] = lambda: db
    fallback = {"available": False, "plan": {}, "note": "AI 不可用，请手动填写治理方案"}
    with patch("app.routers.hazard_management._get_ai_config",
               AsyncMock(side_effect=HTTPException(400, "系统未配置 AI 模型，请联系管理员"))), \
         patch("app.routers.hazard_management.ai_governance_plan",
               AsyncMock(return_value=fallback)) as mock_plan:
        resp = client.post("/enterprises/e1/hazard-inspection/ai/governance-plan",
                           json={"description": "储罐超压运行"})
    assert resp.status_code == 200
    assert resp.json()["data"] == fallback
    assert mock_plan.await_args.args[1] is None


def test_ai_governance_plan_non_member_404(client):
    ent = _ent(user_id="u2")
    db = _grade_db(ent, member=None, record=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/ai/governance-plan",
                       json={"description": "储罐超压运行"})
    assert resp.status_code == 404


# ── AI governance-plan：服务层 ──

@pytest.mark.asyncio
async def test_ai_governance_plan_success_five_keys():
    plan = {"goal": "消除隐患", "measures": "更换设备并加联锁", "budget": "2万元",
            "emergency_measures": "整改期间临时停用", "acceptance_criteria": "复测联锁动作正常"}
    raw = "```json\n" + json.dumps({"plan": plan}, ensure_ascii=False) + "\n```"
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=raw)) as mock_llm:
        out = await ai_governance_plan("储罐超压运行", MagicMock())
    assert out["available"] is True
    assert set(out["plan"].keys()) == {"goal", "measures", "budget",
                                       "emergency_measures", "acceptance_criteria"}
    assert all(v for v in out["plan"].values())
    prompt = mock_llm.await_args.args[0][1]["content"]
    assert JUDGMENT_POINTS in prompt


@pytest.mark.asyncio
async def test_ai_governance_plan_missing_keys_degrades():
    plan = {"goal": "目标", "measures": "措施"}
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps({"plan": plan}, ensure_ascii=False))):
        out = await ai_governance_plan("描述", MagicMock())
    assert out["available"] is False
    assert out["plan"] == {}


@pytest.mark.asyncio
async def test_ai_governance_plan_blank_value_degrades():
    plan = {"goal": "目标", "measures": "措施", "budget": "", "emergency_measures": "应急",
            "acceptance_criteria": "标准"}
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps({"plan": plan}, ensure_ascii=False))):
        out = await ai_governance_plan("描述", MagicMock())
    assert out["available"] is False


@pytest.mark.asyncio
async def test_ai_governance_plan_failure_degrades():
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(side_effect=Exception("timeout"))):
        out = await ai_governance_plan("描述", MagicMock())
    assert out["available"] is False
    assert out["note"]


@pytest.mark.asyncio
async def test_ai_governance_plan_invalid_json_degrades():
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value="not a json")):
        out = await ai_governance_plan("描述", MagicMock())
    assert out["available"] is False


@pytest.mark.asyncio
async def test_ai_governance_plan_no_config_skips_llm():
    with patch("app.services.hazard_ai_service.llm_text_completion", AsyncMock()) as mock_llm:
        out = await ai_governance_plan("描述", None)
    assert out["available"] is False
    assert out["plan"] == {}
    mock_llm.assert_not_awaited()
